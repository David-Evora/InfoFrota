"""Agente multi-etapas do InfoFrota com Tool Calling nativo quando disponível.

O caminho principal para endpoints OpenAI-compatíveis usa chamadas de ferramenta
nativas. A execução de SQL continua passando pela guarda somente leitura de db.py.
Clientes sem suporte a Tool Calling mantêm o protocolo textual de compatibilidade.
"""
import argparse
import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from . import prompts
from .db import DB_PATH, SQLBloqueado, SQLErro, executar
from .llm import LLMErro, llm_do_ambiente
from .rag import Indice

MAX_LINHAS_OBS = 30
MAX_CHARS_OBS = 3000
MAX_ERROS_FORMATO = 3

FORMATO = (
    'Responda SOMENTE com um objeto JSON válido, sem texto fora dele:\n'
    '{"pensamento": "<uma frase curta>", "ferramenta": "esquema|sql|responder", "entrada": "<texto>"}'
)

FERRAMENTAS_NATIVAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_esquema",
            "description": "Recupera tabelas, colunas, valores categóricos e regras do banco InfoFrota. Use antes de SQL quando precisar descobrir estrutura ou valores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {"type": "string", "description": "O que deseja descobrir no esquema."}
                },
                "required": ["consulta"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "executar_sql",
            "description": "Executa uma única consulta SELECT em SQLite no banco experimental InfoFrota. Escritas são bloqueadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "Uma única consulta SELECT ou WITH ... SELECT em SQLite."}
                },
                "required": ["sql"],
                "additionalProperties": False,
            },
        },
    },
]


def montar_system(db_path=DB_PATH) -> str:
    ini, fim, _ = prompts._periodo(db_path)
    return f"""Você é o agente de dados do InfoFrota, sistema experimental de lotação de ônibus da Grande Vitória (Transcol). Responda perguntas em português usando as ferramentas disponíveis. Perguntas podem exigir várias consultas sequenciais; use o resultado de uma consulta para decidir a próxima.

FERRAMENTAS
- consultar_esquema(consulta): recupera tabelas, colunas, valores categóricos e regras relevantes.
- executar_sql(sql): executa UMA consulta SELECT em SQLite.
- Faça no máximo UMA chamada de ferramenta por turno. Não tente chamadas paralelas nem escreva JSON para simular ferramentas.
- Quando tiver evidências suficientes, responda diretamente em português, em até 4 frases. Não chame uma ferramenta para redigir a resposta final.

ESQUEMA (tabela(colunas))
{prompts._esquema_compacto(db_path)}

REGRAS DO DOMÍNIO
- Dados de {ini} a {fim}; {fim} é o último dia disponível. Sem datas na pergunta, não filtre por data.
- Datas e horas em alertas.criado_em, viagens.data_inicio/data_fim e registros_ocupacao.momento são TEXT 'AAAA-MM-DD HH:MM:SS'. Para filtrar dias inteiros use date(coluna) = 'AAAA-MM-DD'; em intervalo inclusivo use date(coluna) BETWEEN 'AAAA-MM-DD' AND 'AAAA-MM-DD'. Evite BETWEEN com datas sem hora diretamente em timestamps, pois o último dia pode ser cortado.
- calendario.data e resumos_dia.data já armazenam apenas a data e não precisam de date().
- linhas.numero é TEXT, por exemplo '562'.
- onibus.status usa exatamente 'ativo', 'manutencao' ou 'inativo'. Use 'manutencao' em minúsculas.
- Alertas: ATENCAO >= 75% e < 90%; CRITICO >= 90%. calendario.tipo_dia: util, sabado, domingo, feriado.
- resumos_hora com parada_id NULL é o resumo da linha inteira. Por linha/dia use resumos_dia; por parada, município ou viagem use registros_ocupacao e alertas.
- Se uma consulta retornar vazio ou zero, confira os filtros, valores categóricos e datas antes de concluir que não há registros. Se a consulta estiver correta, zero pode ser legítimo.
- Decomponha perguntas compostas em consultas sequenciais: primeiro descubra o valor ou entidade principal; depois consulte os detalhes relacionados.
- Somente leitura. Pedidos de alterar dados e assuntos que o banco não contém devem receber uma explicação clara de que não podem ser respondidos com essa base.
- Nunca invente números, datas, nomes, placas ou resultados. Diferencie ausência de dados de falha na consulta.
"""


def _interpretar(bruto: str) -> Optional[dict]:
    achado = re.search(r"\{.*\}", bruto or "", re.S)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(dados, dict) or dados.get("ferramenta") not in ("esquema", "sql", "responder"):
        return None
    return {"ferramenta": dados["ferramenta"], "entrada": str(dados.get("entrada") or "").strip()}


class LimiteDiario(LLMErro):
    """Cota diária esgotada: esperar minutos não adianta."""


class ComEspera:
    """Repete chamadas quando o provedor devolve HTTP 429."""
    def __init__(self, llm, tentativas=8):
        self.llm, self.nome, self.tentativas = llm, llm.nome, tentativas
        self.supports_tool_calling = getattr(llm, "supports_tool_calling", callable(getattr(llm, "complete_with_tools", None)))

    def _chamar(self, metodo, *args, **kwargs):
        for i in range(self.tentativas):
            try:
                return metodo(*args, **kwargs)
            except LLMErro as erro:
                if "HTTP 429" in str(erro) and ("per day" in str(erro) or "(TPD)" in str(erro) or "(RPD)" in str(erro)):
                    raise LimiteDiario(str(erro)) from erro
                if "HTTP 429" not in str(erro) or i == self.tentativas - 1:
                    raise
                espera = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(erro))
                segundos = int(espera.group(1) or 0) * 60 + float(espera.group(2)) + 1 if espera else 10
                time.sleep(segundos)

    def complete(self, system, messages):
        return self._chamar(self.llm.complete, system, messages)

    def complete_with_tools(self, system, messages, tools, tool_choice="auto", parallel_tool_calls=False):
        metodo = getattr(self.llm, "complete_with_tools", None)
        if metodo is None:
            raise LLMErro("O cliente configurado não oferece Tool Calling nativo.")
        return self._chamar(metodo, system, messages, tools, tool_choice, parallel_tool_calls)


@dataclass
class RespostaAgente:
    pergunta: str
    texto: Optional[str] = None
    passos: list = field(default_factory=list)
    erro: Optional[str] = None
    nota: str = prompts.NOTA_DADOS


class Agente:
    def __init__(self, llm, db_path=DB_PATH, max_passos=8):
        self.llm, self.db_path, self.max_passos = llm, db_path, max_passos
        self.system, self.indice = montar_system(db_path), Indice(db_path)

    def _usar(self, ferramenta: str, entrada: str) -> dict:
        if ferramenta == "esquema":
            return {"contexto": self.indice.contexto(entrada)}
        try:
            resultado = executar(entrada, self.db_path, MAX_LINHAS_OBS)
        except SQLBloqueado as erro:
            return {"erro": f"bloqueado: {erro}"}
        except SQLErro as erro:
            return {"erro": str(erro)}
        return {"colunas": resultado.colunas, "linhas": resultado.linhas, "truncado": resultado.truncado}

    @staticmethod
    def _resultado_vazio_ou_zero(dados: dict) -> bool:
        linhas = dados.get("linhas") or []
        if not linhas:
            return True
        return all(
            all(valor is None or (isinstance(valor, (int, float)) and valor == 0) for valor in linha)
            for linha in linhas
        )

    def _executar_chamada_nativa(self, chamada: dict) -> tuple[dict, dict]:
        funcao = chamada.get("function") or {}
        nome = funcao.get("name")
        try:
            argumentos = json.loads(funcao.get("arguments") or "{}")
            if not isinstance(argumentos, dict):
                raise ValueError("os argumentos precisam ser um objeto JSON")
        except (json.JSONDecodeError, ValueError) as erro:
            return {"erro": f"argumentos inválidos: {erro}"}, {"ferramenta": nome, "entrada": "", "observacao": str(erro)}

        if nome == "consultar_esquema":
            entrada = str(argumentos.get("consulta") or "").strip()
            ferramenta = "esquema"
        elif nome == "executar_sql":
            entrada = str(argumentos.get("sql") or "").strip()
            ferramenta = "sql"
        else:
            erro = f"ferramenta desconhecida: {nome}"
            return {"erro": erro}, {"ferramenta": nome, "entrada": "", "observacao": erro}

        if not entrada:
            erro = "argumento obrigatório vazio"
            return {"erro": erro}, {"ferramenta": ferramenta, "entrada": entrada, "observacao": erro}

        dados = self._usar(ferramenta, entrada)
        if ferramenta == "sql" and not dados.get("erro") and self._resultado_vazio_ou_zero(dados):
            dados["aviso"] = (
                "Resultado vazio ou zerado: confira valores categóricos e filtros de data antes de concluir que não há registros. "
                "Use date(coluna) para filtrar dias inteiros em timestamps. Se o filtro estiver correto, o zero pode ser legítimo."
            )
        observacao = json.dumps(dados, ensure_ascii=False, default=str)
        if len(observacao) > MAX_CHARS_OBS:
            observacao = observacao[:MAX_CHARS_OBS] + "...(cortado)"
        return dados, {"ferramenta": ferramenta, "entrada": entrada, "observacao": observacao}

    def _perguntar_nativo(self, pergunta: str, llm) -> RespostaAgente:
        resposta = RespostaAgente(pergunta=pergunta)
        mensagens = [{"role": "user", "content": pergunta}]
        acoes = 0

        # Cada iteração é um turno do modelo. parallel_tool_calls=False pede uma ação por turno.
        while acoes < self.max_passos:
            retorno = llm.complete_with_tools(
                self.system, mensagens, FERRAMENTAS_NATIVAS,
                tool_choice="auto", parallel_tool_calls=False,
            )
            mensagem = retorno.get("message", retorno) if isinstance(retorno, dict) else None
            if not isinstance(mensagem, dict):
                resposta.erro = "resposta inválida do provedor durante Tool Calling"
                return resposta

            chamadas = mensagem.get("tool_calls") or []
            mensagem_assistente = {k: mensagem[k] for k in ("role", "content", "tool_calls") if k in mensagem}
            if not chamadas:
                resposta.texto = str(mensagem.get("content") or mensagem.get("refusal") or "").strip() or None
                if resposta.texto is None:
                    resposta.erro = "o modelo não retornou texto nem chamada de ferramenta"
                return resposta

            mensagens.append(mensagem_assistente)
            for chamada in chamadas:
                if acoes >= self.max_passos:
                    dados = {"erro": "limite de ações atingido; não executei esta chamada"}
                    funcao = chamada.get("function") or {}
                    nome = funcao.get("name", "desconhecida")
                    mensagens.append({
                        "role": "tool", "tool_call_id": chamada.get("id", "sem-id"),
                        "name": nome, "content": json.dumps(dados, ensure_ascii=False),
                    })
                    continue

                dados, passo = self._executar_chamada_nativa(chamada)
                resposta.passos.append(passo)
                acoes += 1
                funcao = chamada.get("function") or {}
                mensagens.append({
                    "role": "tool",
                    "tool_call_id": chamada.get("id", f"call-{acoes}"),
                    "name": funcao.get("name", "desconhecida"),
                    "content": json.dumps(dados, ensure_ascii=False, default=str),
                })

        # Ao atingir o limite, faz uma última chamada sem ferramentas para exigir uma conclusão.
        mensagens.append({
            "role": "user",
            "content": (
                "LIMITE DE AÇÕES ATINGIDO (limite de passos). Não execute novas consultas. "
                "Responda com o que foi efetivamente confirmado pelas observações; "
                "declare explicitamente o que não conseguiu confirmar. Não invente dados."
            ),
        })
        final = llm.complete(self.system, mensagens)
        resposta.texto = str(final or "").strip() or None
        if resposta.texto is None:
            resposta.erro = "sem resposta final após atingir o limite de ações"
        return resposta

    def _perguntar_textual(self, pergunta: str, llm) -> RespostaAgente:
        """Compatibilidade para clientes/fakes sem método complete_with_tools."""
        resposta = RespostaAgente(pergunta=pergunta)
        system = self.system + "\n\nPROTOCOLO DE COMPATIBILIDADE: use o JSON textual exatamente neste formato:\n" + FORMATO
        mensagens = [{"role": "user", "content": pergunta}]
        passos_validos = 0
        erros_formato = 0
        max_tentativas = (self.max_passos + 1) * (MAX_ERROS_FORMATO + 1)

        for _ in range(max_tentativas):
            if passos_validos >= self.max_passos:
                mensagens.append({"role": "user", "content": (
                    "LIMITE DE PASSOS / AÇÕES ATINGIDO. Não execute novas consultas. "
                    "Use responder com o que já foi apurado e declare o que não conseguiu confirmar."
                )})
                final = llm.complete(system, mensagens)
                acao_final = _interpretar(final)
                resposta.texto = acao_final["entrada"] if acao_final and acao_final["ferramenta"] == "responder" else None
                if not resposta.texto:
                    resposta.erro = "sem resposta final dentro do limite de ações"
                return resposta

            try:
                bruto = llm.complete(system, mensagens)
            except LLMErro as erro:
                if "tool_use_failed" not in str(erro):
                    raise
                bruto = ""

            acao = _interpretar(bruto)
            if acao is None or not acao["entrada"]:
                observacao = f"Formato inválido ou entrada vazia. {FORMATO}"
                resposta.passos.append({"ferramenta": None, "entrada": (bruto or "")[:200], "observacao": observacao})
                if bruto:
                    mensagens.append({"role": "assistant", "content": bruto})
                    mensagens.append({"role": "user", "content": observacao})
                elif mensagens and mensagens[-1]["role"] == "user":
                    mensagens[-1]["content"] += "\n" + observacao
                erros_formato += 1
                if erros_formato >= MAX_ERROS_FORMATO:
                    resposta.erro = "formato inválido repetidamente; limite de correções atingido"
                    return resposta
                continue

            erros_formato = 0
            mensagens.append({"role": "assistant", "content": bruto})
            if acao["ferramenta"] == "responder":
                resposta.passos.append({"ferramenta": "responder", "entrada": acao["entrada"], "observacao": None})
                resposta.texto = acao["entrada"]
                return resposta

            dados = self._usar(acao["ferramenta"], acao["entrada"])
            observacao = json.dumps(dados, ensure_ascii=False, default=str)
            if acao["ferramenta"] == "sql" and not dados.get("erro") and self._resultado_vazio_ou_zero(dados):
                observacao += "\nREVISÃO NECESSÁRIA: confira os valores categóricos e os filtros de data antes de concluir que não há registros."
            if len(observacao) > MAX_CHARS_OBS:
                observacao = observacao[:MAX_CHARS_OBS] + "...(cortado)"
            resposta.passos.append({"ferramenta": acao["ferramenta"], "entrada": acao["entrada"], "observacao": observacao})
            passos_validos += 1
            mensagens.append({"role": "user", "content": f"OBSERVAÇÃO: {observacao}"})

        resposta.erro = "sem resposta final dentro do limite de tentativas"
        return resposta

    def perguntar(self, pergunta: str) -> RespostaAgente:
        suporta_tools = getattr(
            self.llm, "supports_tool_calling", callable(getattr(self.llm, "complete_with_tools", None))
        )
        if suporta_tools:
            return self._perguntar_nativo(pergunta, self.llm)
        return self._perguntar_textual(pergunta, self.llm)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("pergunta", nargs="+")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--max-passos", type=int, default=8)
    ap.add_argument("--verbose", action="store_true", help="mostra cada ação do agente")
    args = ap.parse_args()
    llm = ComEspera(llm_do_ambiente(args.provider, args.model, args.base_url))
    resultado = Agente(llm, max_passos=args.max_passos).perguntar(" ".join(args.pergunta))
    if args.verbose:
        for indice, passo in enumerate(resultado.passos, 1):
            print(f"[{indice}] {passo['ferramenta']}: {passo['entrada']}")
            if passo["observacao"]:
                print(f"    -> {passo['observacao'][:300]}")
    print(resultado.texto or f"Sem resposta: {resultado.erro}")
    print(f"({resultado.nota})")


if __name__ == "__main__":
    main()
