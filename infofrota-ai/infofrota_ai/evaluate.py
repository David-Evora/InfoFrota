"""Avalia um modelo no conjunto evaluation/questions.json.

Uso:
    python -m infofrota_ai.evaluate --provider anthropic --model claude-sonnet-5-5
    python -m infofrota_ai.evaluate --provider openai --model meu-modelo --base-url http://localhost:8000/v1
    python -m infofrota_ai.evaluate --provider oracle     # autoteste: deve dar 100%
    python -m infofrota_ai.evaluate --provider naive      # autoteste: deve dar nota baixa
    opções: --shots 0..3  --only F01,M02  --no-cache  --sem-relatorio
"""
import argparse
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .assistant import Assistente
from .compare import DIFERENTE, EXTRAS, OK, comparar
from .db import DB_PATH
from .fakes import EscritaLLM, NaiveLLM, OracleLLM
from .llm import CachedLLM, llm_do_ambiente
from .prompts import MODOS, PROMPT_VERSAO

ROOT = Path(__file__).resolve().parent.parent
QUESTOES = ROOT / "evaluation" / "questions.json"
RUNS = ROOT / "evaluation" / "runs"
NIVEIS = ["facil", "medio", "dificil", "limite"]


def versao_avaliacao():
    return (ROOT / "evaluation" / "VERSION").read_text().strip()


def avaliar_questao(assistente, q):
    resp = assistente.perguntar(q["pergunta"], responder_em_texto=False)
    saida = {"id": q["id"], "dificuldade": q["dificuldade"], "categoria": q["categoria"],
             "pergunta": q["pergunta"], "sql_gerado": resp.sql, "erro": resp.erro,
             "motivo_modelo": resp.motivo, "tentativas": resp.tentativas}

    if q["tipo"] == "fora_do_escopo":
        if not resp.pode_responder and not resp.erro:
            status = "ok"
        elif resp.bloqueado:
            status = "ok_guarda"          # o modelo tentou, a guarda barrou
        else:
            status = "respondeu"          # precisa de revisão manual
        saida.update(status=status, sucesso=status in ("ok", "ok_guarda"),
                     sucesso_exato=status in ("ok", "ok_guarda"),
                     comportamento_esperado=q.get("comportamento_esperado"))
        return saida

    if resp.bloqueado:
        status, detalhe = "bloqueado", resp.erro
    elif resp.erro:
        status, detalhe = "erro_sql", resp.erro
    elif not resp.pode_responder:
        status, detalhe = "recusou", resp.motivo
    else:
        status, detalhe = comparar(q["resultado_esperado"], resp.linhas, q["ordenada"])
    saida.update(status=status, detalhe=detalhe, sucesso=status in (OK, EXTRAS),
                 sucesso_exato=status == OK, sql_referencia=q["sql"],
                 obtido=resp.linhas[:6], esperado=q["resultado_esperado"][:6])
    return saida


def resumir(resultados):
    por = defaultdict(lambda: [0, 0, 0])  # n, contém o esperado, resultado exato
    for r in resultados:
        for chave in (r["dificuldade"], "TOTAL"):
            por[chave][0] += 1
            por[chave][1] += r["sucesso"]
            por[chave][2] += r["sucesso_exato"]
    return {k: {"n": v[0], "acertos": v[1], "acertos_exatos": v[2],
                "acuracia": round(v[1] / v[0], 4), "acuracia_exata": round(v[2] / v[0], 4)}
            for k, v in por.items()}


def relatorio_md(modelo, shots, resumo, resultados, modo="completo"):
    linhas = [f"# Avaliação: {modelo} ({shots} exemplos) | perguntas v{versao_avaliacao()} | prompt v{PROMPT_VERSAO} ({modo})\n",
              "Acurácia = o resultado contém o esperado (colunas extras não contam como erro). "
              "Exata = resultado idêntico, sem colunas a mais.\n",
              "| Nível | Perguntas | Acertos | Acurácia | Exata |", "|---|---|---|---|---|"]
    for k in NIVEIS + ["TOTAL"]:
        if k in resumo:
            s = resumo[k]
            linhas.append(f"| {k} | {s['n']} | {s['acertos']} | {s['acuracia']:.1%} | "
                          f"{s['acuracia_exata']:.1%} |")
    falhas = [r for r in resultados if not r["sucesso"]]
    linhas.append(f"\n## Falhas ({len(falhas)})\n")
    for r in falhas:
        linhas.append(f"### {r['id']} [{r['status']}] {r['pergunta']}")
        if r.get("detalhe"):
            linhas.append(f"- detalhe: {r['detalhe']}")
        if r.get("comportamento_esperado"):
            linhas.append(f"- esperado: {r['comportamento_esperado']}")
        if r.get("sql_gerado"):
            linhas.append(f"- SQL gerado: `{r['sql_gerado']}`")
        if r.get("sql_referencia"):
            linhas.append(f"- SQL de referência: `{r['sql_referencia']}`")
        if "obtido" in r:
            linhas.append(f"- obtido: {r['obtido']}  |  esperado: {r['esperado']}")
        linhas.append("")
    return "\n".join(linhas)


def executar_avaliacao(llm, shots=3, apenas=None, db_path=DB_PATH, questoes_path=QUESTOES,
                       compacto=False):
    questoes = json.loads(Path(questoes_path).read_text(encoding="utf-8"))
    if apenas:
        questoes = [q for q in questoes if q["id"] in apenas]
    assistente = Assistente(llm, db_path=db_path, shots=shots, compacto=compacto)
    resultados = []
    for q in questoes:
        t0 = time.monotonic()
        r = avaliar_questao(assistente, q)
        r["segundos"] = round(time.monotonic() - t0, 2)
        resultados.append(r)
    return resultados, resumir(resultados)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--shots", type=int, default=3, choices=[0, 1, 2, 3])
    ap.add_argument("--only", default=None, help="ids separados por vírgula")
    ap.add_argument("--prompt", choices=list(MODOS), default="completo",
                    help="compacto = só nomes de colunas + glossário; ultra = esquema + 5 regras (LoRA)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--sem-relatorio", action="store_true")
    a = ap.parse_args()

    questoes = json.loads(QUESTOES.read_text(encoding="utf-8"))
    if a.provider == "oracle":
        llm = OracleLLM(questoes)
    elif a.provider == "naive":
        llm = NaiveLLM()
    elif a.provider == "escrita":
        llm = EscritaLLM()
    else:
        llm = llm_do_ambiente(a.provider, a.model, a.base_url)
        if not a.no_cache and a.provider != "hf":  # hf: adaptador muda, cache ficaria velho
            llm = CachedLLM(llm)

    apenas = set(a.only.split(",")) if a.only else None
    resultados, resumo = executar_avaliacao(llm, a.shots, apenas, compacto=MODOS[a.prompt])
    md = relatorio_md(llm.nome, a.shots, resumo, resultados, a.prompt)
    print(md)
    if not a.sem_relatorio and a.provider not in ("oracle", "naive", "escrita"):
        RUNS.mkdir(parents=True, exist_ok=True)
        base = RUNS / f"{datetime.now():%Y%m%d-%H%M%S}_{llm.nome}_{a.shots}shot_{a.prompt}"
        base.with_suffix(".json").write_text(json.dumps(
            {"modelo": llm.nome, "shots": a.shots, "versao_perguntas": versao_avaliacao(),
             "versao_prompt": PROMPT_VERSAO, "prompt_modo": a.prompt, "resumo": resumo, "resultados": resultados},
            ensure_ascii=False, indent=1), encoding="utf-8")
        base.with_suffix(".md").write_text(md, encoding="utf-8")
        print(f"\nRelatório salvo em {base}.md")


if __name__ == "__main__":
    main()
