"""Compara, nas perguntas de vários passos (evaluation/agent_questions.json), o assistente de uma
consulta (Text-to-SQL) com o agente de ferramentas, usando o MESMO modelo.

    python -m infofrota_ai.avaliar_agente --provider openai --model openai/gpt-oss-20b --base-url https://api.groq.com/openai/v1
    opções: --only M01,M02  --max-passos 6  --prompt ultra  --sem-rag  --no-cache  --sem-relatorio

Critério: todos os valores de "esperado" aparecem no texto final (acento e caixa ignorados; "a|b" = a ou b).
Para o assistente de uma consulta, conta também as linhas do resultado (critério generoso com ele).
São poucas perguntas: diferenças de uma ou duas são ruído, e os dados são sintéticos.
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


def _norm(t) -> str:
    return unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode()


def contem(texto, esperado) -> bool:
    """Cada item de `esperado` precisa aparecer no texto; 'a|b' aceita qualquer alternativa.
    O valor não pode estar colado em outra letra/dígito nem ser a parte inteira de um decimal."""
    t = _norm(texto)
    return all(any(re.search(rf"(?<!\w){re.escape(_norm(alt))}(?!\w|[.,]\d)", t) for alt in item.split("|"))
               for item in esperado)


class Contador:
    """Conta chamadas ao modelo (inclui as servidas pelo cache)."""
    def __init__(self, llm):
        self.llm, self.nome, self.chamadas = llm, llm.nome, 0

    def complete(self, system, messages):
        self.chamadas += 1
        return self.llm.complete(system, messages)


def avaliar(llm, questoes, db_path=DB_PATH, prompt="ultra", rag=True, max_passos=6):
    unico = Assistente(llm, db_path=db_path, shots=0, compacto=MODOS[prompt], rag=rag)
    agente = Agente(llm, db_path=db_path, max_passos=max_passos)
    out = []
    for q in questoes:
        r = {"id": q["id"], "pergunta": q["pergunta"], "esperado": q["esperado"]}
        t0 = time.monotonic()
        try:
            c0 = llm.chamadas
            u = unico.perguntar(q["pergunta"], responder_em_texto=True)
            r.update(ok_unico=contem(f"{u.texto} {json.dumps(u.linhas, ensure_ascii=False, default=str)}", q["esperado"]),
                     texto_unico=u.texto, sql_unico=u.sql, chamadas_unico=llm.chamadas - c0)
            c0 = llm.chamadas
            a = agente.perguntar(q["pergunta"])
            r.update(ok_agente=bool(a.texto) and contem(a.texto, q["esperado"]), texto_agente=a.texto,
                     erro_agente=a.erro, passos=a.passos, consultas_agente=sum(p["ferramenta"] == "sql" for p in a.passos),
                     chamadas_agente=llm.chamadas - c0)
        except Exception as e:      # limite de taxa, chave inválida, modelo indisponível
            r.setdefault("ok_unico", False)
            r.update(ok_agente=False, erro_agente=f"{type(e).__name__}: {e}")
        r["segundos"] = round(time.monotonic() - t0, 1)
        out.append(r)
    return out


def resumo(resultados) -> dict:
    n = len(resultados)
    com = [r for r in resultados if "chamadas_agente" in r]
    media = lambda k: round(sum(r[k] for r in com) / len(com), 2) if com else None
    return {"n": n, "acertos_unico": sum(r["ok_unico"] for r in resultados),
            "acertos_agente": sum(r["ok_agente"] for r in resultados),
            "consultas_medias_agente": media("consultas_agente"), "chamadas_medias_agente": media("chamadas_agente"),
            "chamadas_medias_unico": media("chamadas_unico")}


def relatorio_md(modelo, s, resultados) -> str:
    linhas = [f"# Agente x consulta única: {modelo} | {s['n']} perguntas de vários passos\n",
              "Mesmo modelo nos dois. Acerto = todos os valores esperados aparecem no texto final. "
              "Dados sintéticos; poucas perguntas, então diferenças pequenas são ruído.\n",
              "| | Acertos | Chamadas ao modelo (média) |", "|---|---|---|",
              f"| Consulta única | {s['acertos_unico']}/{s['n']} | {s['chamadas_medias_unico']} |",
              f"| Agente | {s['acertos_agente']}/{s['n']} | {s['chamadas_medias_agente']} "
              f"({s['consultas_medias_agente']} consultas SQL) |", ""]
    falhas = [r for r in resultados if not (r["ok_unico"] and r["ok_agente"])]
    linhas.append(f"## Perguntas com falha em pelo menos um modo ({len(falhas)})\n")
    for r in falhas:
        linhas += [f"### {r['id']} {r['pergunta']}", f"- esperado: {r['esperado']}",
                   f"- consulta única: {'ok' if r['ok_unico'] else 'falhou'} | agente: {'ok' if r['ok_agente'] else 'falhou'}"]
        if not r["ok_agente"]:
            linhas.append(f"- agente: {r.get('texto_agente') or r.get('erro_agente')}")
        if not r["ok_unico"]:
            linhas.append(f"- consulta única: {r.get('texto_unico')}")
        linhas.append("")
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--only")
    ap.add_argument("--max-passos", type=int, default=6)
    ap.add_argument("--prompt", choices=list(MODOS), default="ultra")
    ap.add_argument("--sem-rag", action="store_true", help="tira o RAG de esquema do modo consulta única")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--sem-relatorio", action="store_true")
    a = ap.parse_args()

    questoes = json.loads(QUESTOES.read_text(encoding="utf-8"))
    if a.only:
        questoes = [q for q in questoes if q["id"] in set(a.only.split(","))]
    llm = ComEspera(llm_do_ambiente(a.provider, a.model, a.base_url))
    llm = Contador(llm if a.no_cache else CachedLLM(llm))
    resultados = avaliar(llm, questoes, prompt=a.prompt, rag=not a.sem_rag, max_passos=a.max_passos)
    s = resumo(resultados)
    md = relatorio_md(llm.nome, s, resultados)
    print(md)
    if not a.sem_relatorio:
        RUNS.mkdir(parents=True, exist_ok=True)
        base = RUNS / f"{datetime.now():%Y%m%d-%H%M%S}_agente_{llm.nome.replace('/', '-')}"
        Path(f"{base}.json").write_text(json.dumps({"modelo": llm.nome, "resumo": s, "resultados": resultados},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
        Path(f"{base}.md").write_text(md, encoding="utf-8")
        print(f"\nRelatório salvo em {base}.md")


if __name__ == "__main__":
    main()
