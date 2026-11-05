"""CLI do assistente.

    python -m infofrota_ai "Quais linhas têm mais alertas críticos?"
    python -m infofrota_ai                      # modo conversa
    opções: --provider anthropic|openai  --model NOME  --base-url URL  --sql (só mostra o SQL)
"""
import argparse

from . import prompts
from .assistant import Assistente
from .llm import llm_do_ambiente


def _tabela(colunas, linhas, limite=15):
    if not colunas:
        return ""
    largura = [max(len(str(c)), *(len(str(l[i])) for l in linhas[:limite]), 0) if linhas
               else len(str(c)) for i, c in enumerate(colunas)]
    fmt = lambda vals: " | ".join(str(v).ljust(w) for v, w in zip(vals, largura))
    saida = [fmt(colunas), "-+-".join("-" * w for w in largura)]
    saida += [fmt(l) for l in linhas[:limite]]
    if len(linhas) > limite:
        saida.append(f"... (+{len(linhas) - limite} linhas)")
    return "\n".join(saida)


def mostrar(r, so_sql=False):
    if r.sql:
        print(f"SQL: {r.sql}")
    if not r.pode_responder:
        print(f"Não consigo responder: {r.motivo or r.erro}")
    elif r.bloqueado:
        print(f"Consulta bloqueada: {r.erro}")
    elif r.erro:
        print(f"Erro ao executar: {r.erro}")
    elif not so_sql:
        print(_tabela(r.colunas, r.linhas))
        if r.texto:
            print(f"\n{r.texto}")
    print(f"({r.nota})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("pergunta", nargs="*")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--sql", action="store_true", help="mostrar só o SQL e o resultado bruto")
    ap.add_argument("--prompt", choices=list(prompts.MODOS), default="completo")
    ap.add_argument("--shots", type=int, default=3, choices=[0, 1, 2, 3])
    a = ap.parse_args()
    bot = Assistente(llm_do_ambiente(a.provider, a.model, a.base_url), shots=a.shots,
                     compacto=prompts.MODOS[a.prompt])

    if a.pergunta:
        mostrar(bot.perguntar(" ".join(a.pergunta), responder_em_texto=not a.sql), a.sql)
        return
    print("InfoFrota AI. Pergunte sobre lotação, linhas, alertas... (Enter vazio sai)")
    while True:
        try:
            p = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not p:
            break
        mostrar(bot.perguntar(p, responder_em_texto=not a.sql), a.sql)


if __name__ == "__main__":
    main()
