"""Gera docs/site/assets/data/snapshot.js a partir do banco SINTÉTICO do repositório.

O site público é estático. Para que os gráficos e a demonstração do assistente mostrem números
reais do banco experimental (e não valores inventados à mão), este script consulta o SQLite com a
mesma guarda somente leitura do assistente e grava um instantâneo pequeno.

O que é real no instantâneo: os números (do banco sintético), o contexto recuperado pelo RAG e o
resultado do SQL. O que é roteirizado: a pergunta, o SQL e o texto da resposta, escritos aqui; o
modelo de linguagem NÃO é chamado. O site rotula isso como simulação.

Uso:  python scripts/generate_data.py && python scripts/build_site_snapshot.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infofrota_ai.db import DB_PATH, SQLBloqueado, conectar, executar
from infofrota_ai.rag import Indice

SAIDA = Path(__file__).resolve().parent.parent / "docs" / "site" / "assets" / "data" / "snapshot.js"
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def consulta(con, sql, *args):
    return [list(r) for r in con.execute(sql, args).fetchall()]


def r1(x):
    return None if x is None else round(float(x), 1)


def cenarios(db):
    idx = Indice(db)

    def rodar(pergunta, sql):
        ctx = idx.recuperar(pergunta)
        rag = {
            "tabelas": [d.id for d in ctx["tabelas"]],
            "valores": [d.texto.lstrip("- ")[:150] for d in ctx["valores"][:3]],
            "regras": [d.texto[:190] for d in ctx["regras"][:2]],
        }
        item = {"pergunta": pergunta, "rag": rag, "sql": sql}
        try:
            res = executar(sql, db)
            item.update(pode_responder=True, bloqueado=False, colunas=res.colunas,
                        linhas=[[r1(v) if isinstance(v, float) else v for v in l] for l in res.linhas])
        except SQLBloqueado as e:
            item.update(pode_responder=True, bloqueado=True, erro=str(e), colunas=[], linhas=[])
        return item

    c1 = rodar("Quais linhas têm mais alertas críticos?",
               "SELECT l.numero AS linha, COUNT(*) AS alertas_criticos FROM alertas a "
               "JOIN linhas l ON l.id = a.linha_id WHERE a.tipo = 'CRITICO' "
               "GROUP BY l.numero ORDER BY alertas_criticos DESC LIMIT 5")
    top = c1["linhas"]
    c1["texto"] = (f"A linha {top[0][0]} lidera, com {top[0][1]} alertas críticos no período, seguida pelas "
                   f"linhas {top[1][0]} ({top[1][1]}) e {top[2][0]} ({top[2][1]}).")

    c2 = rodar("Em que horário a linha 562 costuma lotar mais?",
               "SELECT strftime('%H', h.data_hora) AS hora, ROUND(AVG(h.media_percentual), 1) AS ocupacao_media "
               "FROM resumos_hora h JOIN linhas l ON l.id = h.linha_id "
               "WHERE l.numero = '562' AND h.parada_id IS NULL "
               "GROUP BY hora ORDER BY ocupacao_media DESC LIMIT 3")
    h = c2["linhas"]
    c2["texto"] = (f"Os picos da linha 562 ficam às {h[0][0]}h ({h[0][1]}% em média), às {h[1][0]}h "
                   f"({h[1][1]}%) e às {h[2][0]}h ({h[2][1]}%).")

    c3 = rodar("A chuva aumenta a lotação?",
               "SELECT CASE WHEN chuva_mm > 0 THEN 'com chuva' ELSE 'sem chuva' END AS clima, "
               "ROUND(AVG(media_percentual), 1) AS ocupacao_media, COUNT(*) AS leituras_horarias "
               "FROM v_lotacao_clima GROUP BY clima")
    m = {l[0]: l for l in c3["linhas"]}
    c3["texto"] = (f"No banco sintético, a ocupação média é {m['com chuva'][1]}% nas horas com chuva e "
                   f"{m['sem chuva'][1]}% sem chuva. É uma diferença entre médias de dados simulados, "
                   f"não uma relação causal.")

    c4 = {"pergunta": "Qual é o salário dos motoristas?", "pode_responder": False, "bloqueado": False,
          "rag": {"tabelas": [d.id for d in idx.recuperar("salário dos motoristas")["tabelas"]],
                  "valores": [], "regras": []},
          "sql": "", "colunas": [], "linhas": [],
          "texto": "Não consigo responder: o banco não tem dados de salário nem de motoristas."}

    c5 = rodar("Apague todos os alertas críticos.", "DELETE FROM alertas WHERE tipo = 'CRITICO'")
    c5["texto"] = "A consulta foi bloqueada antes de tocar no banco. O assistente só executa leituras."

    for c, rotulo in ((c1, "Ranking"), (c2, "Horário de pico"), (c3, "Clima"),
                      (c4, "Fora do escopo"), (c5, "Proteção")):
        c["rotulo"] = rotulo
    return [c1, c2, c3, c4, c5]


def main():
    con = conectar(DB_PATH)
    periodo = consulta(con, "SELECT MIN(data), MAX(data) FROM resumos_dia")[0]
    n_linhas = consulta(con, "SELECT COUNT(*) FROM linhas WHERE monitorada = 1")[0][0]

    linhas = []
    for lid, num, nome, tipo in consulta(con, "SELECT id, numero, nome, tipo FROM linhas "
                                              "WHERE monitorada = 1 ORDER BY numero"):
        horas = {int(h): m for h, m in consulta(con,
                 "SELECT CAST(strftime('%H', data_hora) AS INTEGER), AVG(media_percentual) FROM resumos_hora "
                 "WHERE linha_id = ? AND parada_id IS NULL GROUP BY 1", lid)}
        picos = {int(h): m for h, m in consulta(con,
                 "SELECT CAST(strftime('%H', data_hora) AS INTEGER), MAX(max_percentual) FROM resumos_hora "
                 "WHERE linha_id = ? AND parada_id IS NULL GROUP BY 1", lid)}
        dia = consulta(con, "SELECT AVG(media_percentual), MAX(max_percentual), SUM(total_alertas_atencao), "
                            "SUM(total_alertas_critico) FROM resumos_dia WHERE linha_id = ?", lid)[0]
        linhas.append({"numero": num, "nome": nome, "tipo": tipo,
                       "horas": [r1(horas.get(h)) for h in range(24)],
                       "picos": [r1(picos.get(h)) for h in range(24)],
                       "media": r1(dia[0]), "maximo": r1(dia[1]),
                       "atencao": int(dia[2] or 0), "critico": int(dia[3] or 0)})

    cal = {d: i for i, d in enumerate(DIAS)}
    calor = [[[0.0, 0] for _ in range(24)] for _ in range(7)]
    for ds, h, m in consulta(con, "SELECT c.dia_semana, CAST(strftime('%H', r.data_hora) AS INTEGER), r.media_percentual "
                                  "FROM resumos_hora r JOIN calendario c ON c.data = date(r.data_hora) "
                                  "WHERE r.parada_id IS NULL"):
        calor[cal[ds]][h][0] += m
        calor[cal[ds]][h][1] += 1
    mapa = [[r1(s / n) if n else None for s, n in linha] for linha in calor]

    por_dia = consulta(con, "SELECT date(criado_em) d, SUM(tipo = 'ATENCAO'), SUM(tipo = 'CRITICO') "
                            "FROM alertas GROUP BY d ORDER BY d")
    recentes = consulta(con, "SELECT a.id, l.numero, p.nome, a.percentual, a.criado_em, a.mensagem "
                             "FROM alertas a JOIN linhas l ON l.id = a.linha_id "
                             "LEFT JOIN paradas p ON p.id = a.parada_id "
                             "WHERE a.tipo = 'CRITICO' ORDER BY a.criado_em DESC LIMIT 6")
    totais = consulta(con, "SELECT SUM(tipo = 'ATENCAO'), SUM(tipo = 'CRITICO'), COUNT(*) FROM alertas")[0]

    snap = {
        "aviso": "Dados sintéticos gerados por scripts/generate_data.py. Não representam a operação real.",
        "periodo": periodo, "linhas_monitoradas": n_linhas,
        "totais": {"atencao": totais[0], "critico": totais[1], "alertas": totais[2]},
        "linhas": linhas,
        "mapa_calor": {"dias": DIAS, "valores": mapa},
        "alertas_por_dia": [{"data": d, "atencao": a, "critico": c} for d, a, c in por_dia],
        "alertas_recentes": [{"id": i, "linha": n, "parada": p, "percentual": r1(pc), "criado_em": t, "mensagem": m}
                             for i, n, p, pc, t, m in recentes],
        "cenarios": [{**c, "texto": re.sub(r"(\d)\.(\d)", r"\1,\2", c["texto"])} for c in cenarios(DB_PATH)],
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    # .js (e não .json) para o site abrir também por file://, onde fetch() de arquivo local é bloqueado.
    corpo = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
    SAIDA.write_text(f"window.INFOFROTA_SNAPSHOT={corpo};\n", encoding="utf-8")
    print(f"{SAIDA.relative_to(SAIDA.parents[4])}: {SAIDA.stat().st_size / 1024:.1f} KB, {len(linhas)} linhas")


if __name__ == "__main__":
    main()
