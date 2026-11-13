"""Agente do InfoFrota: resolve perguntas de vários passos com ferramentas (esquema, sql, responder).

O assistente de `assistente.py` gera UMA consulta por pergunta. O agente decompõe: consulta, olha o
resultado, consulta de novo e só então responde ("qual a linha mais crítica e a hora de pico dela?").

Usa o mesmo contrato `complete(system, messages) -> str` dos outros clientes: funciona com qualquer
provider (Groq/Gemini via openai-compat, Anthropic, local) e com CachedLLM e os fakes. O protocolo é
JSON no texto, não o tool-calling nativo de cada API. Toda consulta passa pela guarda somente leitura
de db.py; o agente não consegue alterar o banco.

    python -m infofrota_ai.agente "Qual linha tem mais alertas críticos e em que hora?" --verbose
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

FERRAMENTAS = ("esquema", "sql", "responder")
MAX_LINHAS_OBS = 30      # linhas de resultado que o modelo enxerga por consulta
MAX_CHARS_OBS = 3000

FORMATO = ('Responda SOMENTE com um objeto JSON, sem texto fora dele:\n'
           '{"pensamento": "<uma frase curta>", "ferramenta": "esquema|sql|responder", "entrada": "<texto>"}')


def montar_system(db_path=DB_PATH) -> str:
    ini, fim, _ = prompts._periodo(db_path)
    return f"""Você é o agente de dados do InfoFrota, sistema de lotação de ônibus da Grande Vitória (Transcol). Responda perguntas que podem exigir VÁRIAS consultas, usando ações, um passo por turno. As ações NÃO são funções da API: nunca use tool/function calling; escreva o JSON como texto comum.

AÇÕES
- esquema: entrada = o que você procura (ex.: "alertas por parada e município"). Devolve tabelas, valores válidos e regras relevantes.
- sql: entrada = UMA consulta SELECT em SQLite. Devolve colunas e linhas, ou o erro.
- responder: entrada = a resposta final em português, em até 4 frases, só com números vindos das consultas.

ESQUEMA (tabela(colunas))
{prompts._esquema_compacto(db_path)}

REGRAS
- Dados de {ini} a {fim}; {fim} é o "último dia". Sem datas na pergunta, não filtre por data.
- Datas/horas são TEXT 'AAAA-MM-DD HH:MM:SS'. linhas.numero é TEXT ('562').
- Alertas: ATENCAO 75% a menos de 90%, CRITICO 90% ou mais. calendario.tipo_dia: util, sabado, domingo, feriado.
- resumos_hora com parada_id NULL é o resumo da linha inteira. Por linha/dia use resumos_dia; por parada, município ou viagem use registros_ocupacao e alertas.
- Decomponha: descubra primeiro o que a pergunta pede (ex.: a linha líder) e use esse valor na consulta seguinte.
- Consulta com erro ou vazia: corrija e tente de novo. Nunca invente números.
- Somente leitura. Pedido de alterar dados, ou algo que o banco não tem: use responder explicando que não é possível.

{FORMATO}"""


def _interpretar(bruto: str) -> Optional[dict]:
    achado = re.search(r"\{.*\}", bruto or "", re.S)
    if not achado:
        return None
    try:
        d = json.loads(achado.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or d.get("ferramenta") not in FERRAMENTAS:
        return None
    return {"ferramenta": d["ferramenta"], "entrada": str(d.get("entrada") or "").strip()}


class ComEspera:
    """Repete a chamada quando o provedor devolve 429 (limite por minuto), esperando o tempo que ele pede."""
    def __init__(self, llm, tentativas=8):
        self.llm, self.nome, self.tentativas = llm, llm.nome, tentativas

    def complete(self, system, messages):
        for i in range(self.tentativas):
            try:
                return self.llm.complete(system, messages)
            except LLMErro as e:
                if "HTTP 429" not in str(e) or i == self.tentativas - 1:
                    raise
                m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(e))
                time.sleep(int(m.group(1) or 0) * 60 + float(m.group(2)) + 1 if m else 10)


@dataclass
class RespostaAgente:
    pergunta: str
    texto: Optional[str] = None
    passos: list = field(default_factory=list)   # [{ferramenta, entrada, observacao}]
    erro: Optional[str] = None
    nota: str = prompts.NOTA_DADOS


class Agente:
    def __init__(self, llm, db_path=DB_PATH, max_passos=6):
        self.llm, self.db_path, self.max_passos = llm, db_path, max_passos
        self.system, self.indice = montar_system(db_path), Indice(db_path)

    def _usar(self, ferramenta: str, entrada: str) -> dict:
        if ferramenta == "esquema":
            return {"contexto": self.indice.contexto(entrada)}
        try:
            r = executar(entrada, self.db_path, MAX_LINHAS_OBS)
        except SQLBloqueado as e:
            return {"erro": f"bloqueado: {e}"}
        except SQLErro as e:
            return {"erro": str(e)}
        return {"colunas": r.colunas, "linhas": r.linhas, "truncado": r.truncado}

    def perguntar(self, pergunta: str) -> RespostaAgente:
        r = RespostaAgente(pergunta=pergunta)
        msgs = [{"role": "user", "content": pergunta}]
        for n in range(self.max_passos + 1):
            if n == self.max_passos:      # última chance: obriga a responder com o que há
                msgs[-1]["content"] += "\nLIMITE DE PASSOS: use agora a ferramenta responder com o que já obteve."
            try:
                bruto = self.llm.complete(self.system, msgs)
            except LLMErro as e:
                if "tool_use_failed" not in str(e):     # shortcut: só o 400 do gpt-oss na Groq é refeito
                    raise
                bruto = "(chamada de função rejeitada)"
            msgs.append({"role": "assistant", "content": bruto})
            acao = _interpretar(bruto)
            if acao is None:
                obs = f"Formato inválido (não use tool calling). {FORMATO}"
                r.passos.append({"ferramenta": None, "entrada": (bruto or "")[:200], "observacao": obs})
            elif not acao["entrada"]:
                obs = "Entrada vazia."
                r.passos.append({"ferramenta": acao["ferramenta"], "entrada": "", "observacao": obs})
            elif acao["ferramenta"] == "responder":
                r.passos.append({"ferramenta": "responder", "entrada": acao["entrada"], "observacao": None})
                r.texto = acao["entrada"]
                return r
            else:
                obs = json.dumps(self._usar(acao["ferramenta"], acao["entrada"]), ensure_ascii=False, default=str)
                if len(obs) > MAX_CHARS_OBS:
                    obs = obs[:MAX_CHARS_OBS] + "...(cortado)"
                r.passos.append({"ferramenta": acao["ferramenta"], "entrada": acao["entrada"], "observacao": obs})
            msgs.append({"role": "user", "content": f"OBSERVAÇÃO: {obs}"})
        r.erro = "sem resposta final dentro do limite de passos"
        return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("pergunta", nargs="+")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--max-passos", type=int, default=6)
    ap.add_argument("--verbose", action="store_true", help="mostra cada passo do agente")
    a = ap.parse_args()
    r = Agente(ComEspera(llm_do_ambiente(a.provider, a.model, a.base_url)), max_passos=a.max_passos).perguntar(" ".join(a.pergunta))
    if a.verbose:
        for i, p in enumerate(r.passos, 1):
            print(f"[{i}] {p['ferramenta']}: {p['entrada']}")
            if p["observacao"]:
                print(f"    -> {p['observacao'][:300]}")
    print(r.texto or f"Sem resposta: {r.erro}")
    print(f"({r.nota})")


if __name__ == "__main__":
    main()
