"""Compara consulta única e agente nativo nas perguntas multi-etapas.

Uso:
 python -m infofrota_ai.avaliar_agente --provider openai --model openai/gpt-oss-120b --base-url https://api.groq.com/openai/v1
 opções: --only M01,M02 --max-passos 8 --no-cache --questoes caminho.json
"""
import argparse
import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from .agente import Agente, ComEspera
from .assistant import Assistente
from .db import DB_PATH
from .llm import CachedLLM, llm_do_ambiente
from .prompts import MODOS

ROOT = Path(__file__).resolve().parent.parent
QUESTOES = ROOT / "evaluation" / "agent_questions.json"
RUNS = ROOT / "evaluation" / "runs"


def _norm(texto) -> str:
    return unicodedata.normalize("NFKD", str(texto).lower()).encode("ascii", "ignore").decode()


def contem(texto, esperado) -> bool:
    texto_norm = _norm(texto)
    return all(
        any(re.search(rf"(?<!\w){re.escape(_norm(alternativa))}(?!\w|[.,]\d)", texto_norm)
            for alternativa in item.split("|"))
        for item in esperado
    )


class Contador:
    """Conta chamadas lógicas ao modelo, inclusive respostas de cache."""
    def __init__(self, llm):
        self.llm, self.nome, self.chamadas = llm, llm.nome, 0
        self.supports_tool_calling = getattr(llm, "supports_tool_calling", callable(getattr(llm, "complete_with_tools", None)))

    def complete(self, system, messages):
        self.chamadas += 1
        return self.llm.complete(system, messages)

    def complete_with_tools(self, system, messages, tools, tool_choice="auto", parallel_tool_calls=False):
        self.chamadas += 1
        metodo = getattr(self.llm, "complete_with_tools", None)
        if metodo is None:
            raise RuntimeError("cliente sem suporte a Tool Calling nativo")
        return metodo(system, messages, tools, tool_choice, parallel_tool_calls)


def avaliar(llm, questoes, db_path=DB_PATH, prompt="ultra", rag=True, max_passos=8):
    unico = Assistente(llm, db_path=db_path, shots=0, compacto=MODOS[prompt], rag=rag)
    agente = Agente(llm, db_path=db_path, max_passos=max_passos)
    resultados = []
    for questao in questoes:
        item = {"id": questao["id"], "pergunta": questao["pergunta"], "esperado": questao["esperado"]}
        inicio = time.monotonic()
        try:
            antes = llm.chamadas
            resposta_unica = unico.perguntar(questao["pergunta"], responder_em_texto=True)
            item.update(
                ok_unico=contem(
                    f"{resposta_unica.texto} {json.dumps(resposta_unica.linhas, ensure_ascii=False, default=str)}",
                    questao["esperado"],
                ),
                texto_unico=resposta_unica.texto,
                sql_unico=resposta_unica.sql,
                chamadas_unico=llm.chamadas - antes,
            )
            antes = llm.chamadas
            resposta_agente = agente.perguntar(questao["pergunta"])
            item.update(
                ok_agente=bool(resposta_agente.texto) and contem(resposta_agente.texto, questao["esperado"]),
                texto_agente=resposta_agente.texto,
                erro_agente=resposta_agente.erro,
                passos=resposta_agente.passos,
                consultas_agente=sum(p["ferramenta"] == "sql" for p in resposta_agente.passos),
                chamadas_agente=llm.chamadas - antes,
            )
        except Exception as erro:
            item.setdefault("ok_unico", False)
            item.update(ok_agente=False, erro_agente=f"{type(erro).__name__}: {erro}")
        item["segundos"] = round(time.monotonic() - inicio, 1)
        resultados.append(item)
    return resultados


def resumo(resultados) -> dict:
    completos = [item for item in resultados if "chamadas_agente" in item]
    media = lambda chave: round(sum(item[chave] for item in completos) / len(completos), 2) if completos else None
    return {
        "n": len(resultados),
        "acertos_unico": sum(item["ok_unico"] for item in resultados),
        "acertos_agente": sum(item["ok_agente"] for item in resultados),
        "consultas_medias_agente": media("consultas_agente"),
        "chamadas_medias_agente": media("chamadas_agente"),
        "chamadas_medias_unico": media("chamadas_unico"),
    }


def relatorio_md(modelo, resumo_execucao, resultados) -> str:
    linhas = [
        f"# Agente x consulta única: {modelo} | {resumo_execucao['n']} perguntas multi-etapas\n",
        "Mesmo modelo nos dois modos. Acerto = todos os valores esperados aparecem no texto final. "
        "Dados sintéticos; conjuntos pequenos ou selecionados para diagnóstico não são avaliação independente.\n",
        "| | Acertos | Chamadas ao modelo (média) |", "|---|---|---|",
        f"| Consulta única | {resumo_execucao['acertos_unico']}/{resumo_execucao['n']} | {resumo_execucao['chamadas_medias_unico']} |",
        f"| Agente | {resumo_execucao['acertos_agente']}/{resumo_execucao['n']} | {resumo_execucao['chamadas_medias_agente']} "
        f"({resumo_execucao['consultas_medias_agente']} consultas SQL) |", "",
    ]
    falhas = [item for item in resultados if not (item["ok_unico"] and item["ok_agente"])]
    linhas.append(f"## Perguntas com falha em pelo menos um modo ({len(falhas)})\n")
    for item in falhas:
        linhas.extend([
            f"### {item['id']} {item['pergunta']}", f"- esperado: {item['esperado']}",
            f"- consulta única: {'ok' if item['ok_unico'] else 'falhou'} | agente: {'ok' if item['ok_agente'] else 'falhou'}",
        ])
        if not item["ok_agente"]:
            linhas.append(f"- agente: {item.get('texto_agente') or item.get('erro_agente')}")
        if not item["ok_unico"]:
            linhas.append(f"- consulta única: {item.get('texto_unico')}")
        linhas.append("")
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--only")
    parser.add_argument("--max-passos", type=int, default=8)
    parser.add_argument("--prompt", choices=list(MODOS), default="ultra")
    parser.add_argument("--sem-rag", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--sem-relatorio", action="store_true")
    parser.add_argument("--questoes", type=Path, default=QUESTOES,
                        help="arquivo JSON de perguntas; padrão: evaluation/agent_questions.json")
    args = parser.parse_args()

    questoes = json.loads(args.questoes.read_text(encoding="utf-8"))
    if args.only:
        selecionadas = set(args.only.split(","))
        questoes = [questao for questao in questoes if questao["id"] in selecionadas]

    llm = ComEspera(llm_do_ambiente(args.provider, args.model, args.base_url))
    llm = Contador(llm if args.no_cache else CachedLLM(llm))
    resultados = avaliar(llm, questoes, prompt=args.prompt, rag=not args.sem_rag, max_passos=args.max_passos)
    resumo_execucao = resumo(resultados)
    markdown = relatorio_md(llm.nome, resumo_execucao, resultados)
    print(markdown)

    if not args.sem_relatorio:
        RUNS.mkdir(parents=True, exist_ok=True)
        base = RUNS / f"{datetime.now():%Y%m%d-%H%M%S}_agente_{llm.nome.replace('/', '-')}"
        Path(f"{base}.json").write_text(json.dumps(
            {"modelo": llm.nome, "resumo": resumo_execucao, "resultados": resultados},
            ensure_ascii=False, indent=1,
        ), encoding="utf-8")
        Path(f"{base}.md").write_text(markdown, encoding="utf-8")
        print(f"\nRelatório salvo em {base}.md")


if __name__ == "__main__":
    main()
