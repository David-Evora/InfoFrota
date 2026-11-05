"""Comparação de resultados (acerto por execução).

Regras:
  * nomes de coluna não importam; a ordem das colunas também não;
  * a ordem das linhas só importa quando `ordenada` é verdadeiro;
  * inteiros esperados exigem valor exato; decimais aceitam diferença de
    arredondamento (rel 1e-3 ou 0,051 absoluto);
  * resultado vazio e resultado só com NULL são equivalentes;
  * "colunas_extras": o resultado contém o esperado, mas com colunas a mais.
"""
import itertools
import math

OK, EXTRAS, DIFERENTE = "ok", "colunas_extras", "diferente"


def _vazio(linhas) -> bool:
    return not linhas or all(v is None for l in linhas for v in l)


def _iguais(esperado, obtido) -> bool:
    if esperado is None or obtido is None:
        return esperado is None and obtido is None
    if isinstance(esperado, bool) or isinstance(obtido, bool):
        return bool(esperado) == bool(obtido)
    if isinstance(esperado, (int, float)) and isinstance(obtido, (int, float)):
        if isinstance(esperado, int):
            return obtido == esperado
        return math.isclose(esperado, obtido, rel_tol=1e-3, abs_tol=0.051)
    return str(esperado).strip() == str(obtido).strip()


def _linhas_iguais(esperado, obtido, ordenada) -> bool:
    if len(esperado) != len(obtido):
        return False
    if ordenada:
        return all(len(e) == len(o) and all(_iguais(a, b) for a, b in zip(e, o))
                   for e, o in zip(esperado, obtido))
    livres = list(obtido)
    for e in esperado:
        for i, o in enumerate(livres):
            if len(e) == len(o) and all(_iguais(a, b) for a, b in zip(e, o)):
                del livres[i]
                break
        else:
            return False
    return True


def comparar(esperado, obtido, ordenada=False):
    """esperado/obtido: listas de linhas. Retorna (veredito, detalhe)."""
    if _vazio(esperado):
        return (OK, "") if _vazio(obtido) else (DIFERENTE, "esperava resultado vazio")
    if _vazio(obtido):
        return DIFERENTE, "resultado vazio"
    n, m = len(esperado[0]), len(obtido[0])
    if m < n:
        return DIFERENTE, f"{m} coluna(s) em vez de {n}"
    if len(esperado) != len(obtido):
        return DIFERENTE, f"{len(obtido)} linha(s) em vez de {len(esperado)}"
    if m > 8:
        return DIFERENTE, "colunas demais"
    for idx in itertools.permutations(range(m), n):
        proj = [[linha[i] for i in idx] for linha in obtido]
        if _linhas_iguais(esperado, proj, ordenada):
            return (OK if m == n else EXTRAS), ""
    return DIFERENTE, "valores diferentes"
