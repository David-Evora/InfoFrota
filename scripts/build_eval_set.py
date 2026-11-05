#!/usr/bin/env python3
"""Monta e valida o conjunto de avaliação do InfoFrota AI.

Cada pergunta tem um SQL de referência. Este script executa todos no banco
(somente leitura), confere que não há erro nem resultado vazio por engano,
e grava evaluation/questions.json com o resultado esperado.

Uso:
    python scripts/build_eval_set.py          # valida e grava o JSON
    python scripts/build_eval_set.py --show   # imprime os resultados
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "infofrota.db"
OUT = ROOT / "evaluation" / "questions.json"
MAX_LINHAS = 50

Q = []


def q(id_, dif, cat, pergunta, sql, ordenada=False, vazio=False):
    Q.append(dict(id=id_, tipo="sql", dificuldade=dif, categoria=cat,
                  pergunta=pergunta, sql=" ".join(sql.split()),
                  ordenada=ordenada, esperado_vazio=vazio))


def fora(id_, cat, pergunta, comportamento):
    Q.append(dict(id=id_, tipo="fora_do_escopo", dificuldade="limite", categoria=cat,
                  pergunta=pergunta, sql=None, ordenada=False, esperado_vazio=False,
                  comportamento_esperado=comportamento))


# ======================= FÁCIL: uma tabela, filtro ou contagem =======================
F = "facil"
q("F01", F, "cadastro", "Quantas linhas a CETURBES tem cadastradas?",
  "SELECT COUNT(*) FROM linhas")
q("F02", F, "cadastro", "Quais linhas são monitoradas por sensor de lotação?",
  "SELECT numero FROM linhas WHERE monitorada = 1 ORDER BY numero")
q("F03", F, "cadastro", "Quantas linhas são do tipo circular?",
  "SELECT COUNT(*) FROM linhas WHERE tipo = 'circular'")
q("F04", F, "frota", "Quantos ônibus estão em manutenção?",
  "SELECT COUNT(*) FROM onibus WHERE status = 'manutencao'")
q("F05", F, "frota", "Quais modelos de ônibus existem na frota?",
  "SELECT DISTINCT modelo FROM onibus ORDER BY modelo")
q("F06", F, "cadastro", "Qual é o nome da linha 562?",
  "SELECT nome FROM linhas WHERE numero = '562'")
q("F07", F, "paradas", "Quantas paradas cadastradas ficam em Serra?",
  "SELECT COUNT(*) FROM paradas WHERE municipio = 'Serra'")
q("F08", F, "viagens", "Quantas viagens foram canceladas no período?",
  "SELECT COUNT(*) FROM viagens WHERE status = 'cancelada'")
q("F09", F, "alertas", "Quantos alertas críticos foram gerados no período?",
  "SELECT COUNT(*) FROM alertas WHERE tipo = 'CRITICO'")
q("F10", F, "calendario", "Quais feriados aparecem no calendário e em que datas?",
  "SELECT data, feriado_nome FROM calendario WHERE tipo_dia = 'feriado' ORDER BY data")
q("F11", F, "frota", "Qual é a capacidade do ônibus de placa SIN-0001?",
  "SELECT capacidade FROM onibus WHERE placa = 'SIN-0001'")
q("F12", F, "viagens", "Quantas viagens concluídas houve em 20/10/2026?",
  "SELECT COUNT(*) FROM viagens WHERE date(data_inicio) = '2026-10-20' AND status = 'concluida'")
q("F13", F, "lotacao", "Qual foi o maior percentual de lotação já registrado?",
  "SELECT MAX(percentual) FROM registros_ocupacao")
q("F14", F, "frota", "Quantos ônibus ativos tem a linha 531?",
  """SELECT COUNT(*) FROM onibus o JOIN linhas l ON l.id = o.linha_padrao_id
     WHERE l.numero = '531' AND o.status = 'ativo'""")
q("F15", F, "paradas", "Em quais municípios existem paradas cadastradas?",
  "SELECT DISTINCT municipio FROM paradas ORDER BY municipio")

# ======================= MÉDIO: junções, agregações, filtros de tempo ================
M = "medio"
q("M01", M, "lotacao", "Qual a lotação média de cada linha monitorada, da mais para a menos lotada?",
  """SELECT l.numero, ROUND(AVG(d.media_percentual), 1) AS media
     FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
     GROUP BY l.id ORDER BY media DESC, l.numero""", ordenada=True)
q("M02", M, "alertas", "Quais são as 5 linhas com mais alertas críticos?",
  """SELECT l.numero
     FROM alertas a JOIN linhas l ON l.id = a.linha_id
     WHERE a.tipo = 'CRITICO' GROUP BY l.id ORDER BY COUNT(*) DESC, l.numero LIMIT 5""")
q("M03", M, "viagens", "Quantas viagens concluídas cada linha monitorada fez no período?",
  """SELECT l.numero, COUNT(*) AS viagens
     FROM viagens v JOIN linhas l ON l.id = v.linha_id
     WHERE v.status = 'concluida' GROUP BY l.id ORDER BY l.numero""")
q("M04", M, "horario", "Qual hora do dia tem a maior lotação média em dias úteis?",
  """SELECT CAST(strftime('%H', rh.data_hora) AS INTEGER) AS hora
     FROM resumos_hora rh JOIN calendario k ON k.data = date(rh.data_hora)
     WHERE rh.parada_id IS NULL AND k.tipo_dia = 'util'
     GROUP BY hora ORDER BY AVG(rh.media_percentual) DESC LIMIT 1""")
q("M05", M, "calendario", "Qual a lotação média por tipo de dia (útil, sábado, domingo, feriado)?",
  """SELECT k.tipo_dia, ROUND(AVG(d.media_percentual), 1) AS media
     FROM resumos_dia d JOIN calendario k ON k.data = d.data
     GROUP BY k.tipo_dia ORDER BY media DESC""")
q("M06", M, "paradas", "Quais são as 5 paradas com mais leituras críticas (90% ou mais de lotação)?",
  """SELECT p.nome
     FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id
     WHERE r.percentual >= 90 GROUP BY p.id ORDER BY COUNT(*) DESC, p.nome LIMIT 5""")
q("M07", M, "passageiros", "Quais as 5 linhas que mais embarcaram passageiros no período?",
  """SELECT l.numero
     FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
     GROUP BY l.id ORDER BY SUM(d.total_embarcaram) DESC, l.numero LIMIT 5""")
q("M08", M, "alertas", "Quais linhas tiveram mais de 100 alertas de atenção no período?",
  """SELECT l.numero
     FROM alertas a JOIN linhas l ON l.id = a.linha_id
     WHERE a.tipo = 'ATENCAO' GROUP BY l.id HAVING COUNT(*) > 100
     ORDER BY l.numero""")
q("M09", M, "clima", "Em dias úteis, às 7h da manhã, qual a lotação média com chuva e sem chuva (considere chuva quando chuva_mm > 0)? Uma linha para cada caso.",
  """SELECT CASE WHEN v.chuva_mm > 0 THEN 'com_chuva' ELSE 'sem_chuva' END AS clima,
            ROUND(AVG(v.media_percentual), 1) AS media
     FROM v_lotacao_clima v JOIN calendario k ON k.data = date(v.data_hora)
     WHERE k.tipo_dia = 'util' AND strftime('%H', v.data_hora) = '07'
     GROUP BY clima""")
q("M10", M, "clima", "Em quantos dias choveu no período?",
  "SELECT COUNT(DISTINCT date(data_hora)) FROM clima_hora WHERE chuva_mm > 0")
q("M11", M, "alertas", "Quais ações de precaução foram registradas nos alertas e quantas vezes cada uma?",
  """SELECT precaucao_descricao, COUNT(*) AS vezes FROM alertas
     WHERE em_precaucao = 1 GROUP BY precaucao_descricao ORDER BY vezes DESC""")
q("M12", M, "frota", "Quantos ônibus existem de cada modelo?",
  "SELECT modelo, COUNT(*) AS total FROM onibus GROUP BY modelo ORDER BY total DESC, modelo")
q("M13", M, "frota", "Quais são os 3 ônibus que mais fizeram viagens concluídas?",
  """SELECT o.placa
     FROM viagens v JOIN onibus o ON o.id = v.onibus_id
     WHERE v.status = 'concluida' GROUP BY o.id ORDER BY COUNT(*) DESC, o.placa LIMIT 3""")
q("M14", M, "viagens", "Quais linhas têm duração média de viagem acima de 45 minutos?",
  """SELECT l.numero
     FROM viagens v JOIN linhas l ON l.id = v.linha_id
     WHERE v.status = 'concluida' GROUP BY l.id
     HAVING AVG((julianday(v.data_fim) - julianday(v.data_inicio)) * 1440) > 45
     ORDER BY l.numero""")
q("M15", M, "alertas", "Para cada sentido (ida e volta), quantas viagens tiveram alerta crítico?",
  """SELECT v.sentido, COUNT(DISTINCT a.viagem_id) AS viagens
     FROM alertas a JOIN viagens v ON v.id = a.viagem_id
     WHERE a.tipo = 'CRITICO' GROUP BY v.sentido""")
q("M16", M, "calendario", "Qual linha é a mais lotada aos sábados?",
  """SELECT l.numero
     FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
     JOIN calendario k ON k.data = d.data
     WHERE k.tipo_dia = 'sabado' GROUP BY l.id ORDER BY AVG(d.media_percentual) DESC LIMIT 1""")
q("M17", M, "alertas", "Qual foi o dia com mais alertas críticos?",
  """SELECT date(criado_em) AS dia FROM alertas
     WHERE tipo = 'CRITICO' GROUP BY dia ORDER BY COUNT(*) DESC LIMIT 1""")
q("M18", M, "paradas", "Quais são as paradas da linha 508 no sentido de ida, em ordem?",
  """SELECT p.nome FROM linha_paradas lp
     JOIN linhas l ON l.id = lp.linha_id JOIN paradas p ON p.id = lp.parada_id
     WHERE l.numero = '508' AND lp.sentido = 'ida' ORDER BY lp.ordem""", ordenada=True)
q("M19", M, "paradas", "Quantas linhas passam pela parada Reta da Penha?",
  """SELECT COUNT(DISTINCT lp.linha_id) FROM linha_paradas lp
     JOIN paradas p ON p.id = lp.parada_id WHERE p.nome = 'Reta da Penha'""")
q("M20", M, "paradas", "Qual a lotação média registrada em cada município?",
  """SELECT p.municipio, ROUND(AVG(r.percentual), 1) AS media
     FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id
     GROUP BY p.municipio ORDER BY media DESC""")

# ======================= DIFÍCIL: CTE, janela, subconsulta, comparação ===============
D = "dificil"
q("D01", D, "horario", "Para cada linha monitorada, em que hora do dia a lotação média é mais alta?",
  """WITH m AS (
       SELECT linha_id, CAST(strftime('%H', data_hora) AS INTEGER) AS hora,
              AVG(media_percentual) AS a
       FROM resumos_hora WHERE parada_id IS NULL GROUP BY linha_id, hora),
     r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY linha_id ORDER BY a DESC) AS rn FROM m)
     SELECT l.numero, r.hora FROM r JOIN linhas l ON l.id = r.linha_id
     WHERE r.rn = 1 ORDER BY l.numero""")
q("D02", D, "lotacao", "Quais as 5 linhas com maior proporção de leituras críticas (90% ou mais) sobre o total de leituras?",
  """SELECT l.numero, ROUND(100.0 * SUM(r.percentual >= 90) / COUNT(*), 2) AS pct_criticas
     FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id
     JOIN linhas l ON l.id = v.linha_id
     GROUP BY l.id ORDER BY pct_criticas DESC LIMIT 5""")
q("D03", D, "clima", "Na linha 562, compare a lotação média nos horários de 7h e 17h com e sem chuva (considere chuva quando chuva_mm > 0). Uma linha para cada caso.",
  """SELECT CASE WHEN chuva_mm > 0 THEN 'com_chuva' ELSE 'sem_chuva' END AS clima,
            ROUND(AVG(media_percentual), 1) AS media
     FROM v_lotacao_clima
     WHERE linha_numero = '562' AND strftime('%H', data_hora) IN ('07', '17')
     GROUP BY clima""")
q("D04", D, "paradas", "Em cada município, qual parada tem a maior média de embarque por leitura?",
  """WITH m AS (
       SELECT p.municipio, p.nome, AVG(r.embarcaram) AS a
       FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.id),
     r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY municipio ORDER BY a DESC) AS rn FROM m)
     SELECT municipio, nome FROM r WHERE rn = 1
     ORDER BY municipio""")
q("D05", D, "alertas", "Quais as 5 linhas com maior percentual de viagens que tiveram pelo menos um alerta?",
  """SELECT l.numero,
            ROUND(100.0 * COUNT(DISTINCT a.viagem_id) / COUNT(DISTINCT v.id), 1) AS pct_viagens
     FROM viagens v JOIN linhas l ON l.id = v.linha_id
     LEFT JOIN alertas a ON a.viagem_id = v.id
     WHERE v.status = 'concluida' GROUP BY l.id ORDER BY pct_viagens DESC LIMIT 5""")
q("D06", D, "alertas", "Quais os 5 alertas críticos que levaram mais tempo para serem resolvidos? Mostre a linha e os minutos.",
  """SELECT a.id, l.numero,
            ROUND((julianday(a.resolvido_em) - julianday(a.criado_em)) * 1440, 1) AS minutos
     FROM alertas a JOIN linhas l ON l.id = a.linha_id
     WHERE a.tipo = 'CRITICO' AND a.resolvido = 1
     ORDER BY minutos DESC, a.id LIMIT 5""")
q("D07", D, "calendario", "Qual a média diária de passageiros embarcados (todas as linhas) para cada dia da semana?",
  """SELECT k.dia_semana, ROUND(AVG(t.emb), 0) AS media_embarques
     FROM (SELECT date(data_hora) AS d, SUM(total_embarcaram) AS emb
           FROM resumos_hora WHERE parada_id IS NULL GROUP BY d) t
     JOIN calendario k ON k.data = t.d
     GROUP BY k.dia_semana""")
q("D08", D, "calendario", "Na linha 531, qual a lotação média para cada tipo de dia (útil, sábado, domingo e feriado)?",
  """SELECT k.tipo_dia, ROUND(AVG(d.media_percentual), 1) AS media
     FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
     JOIN calendario k ON k.data = d.data
     WHERE l.numero = '531' GROUP BY k.tipo_dia ORDER BY media DESC""")
q("D09", D, "lotacao", "Quais linhas passaram de 100% de lotação máxima em mais de 5 dias diferentes?",
  """SELECT l.numero
     FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
     WHERE d.max_percentual > 100 GROUP BY l.id HAVING COUNT(DISTINCT d.data) > 5
     ORDER BY l.numero""")
q("D10", D, "paradas", "Em viagens de volta que saem às 17h ou 18h, quais paradas têm lotação média acima de 50%?",
  """SELECT p.nome
     FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id
     JOIN paradas p ON p.id = r.parada_id
     WHERE v.sentido = 'volta' AND CAST(strftime('%H', v.data_inicio) AS INTEGER) IN (17, 18)
     GROUP BY p.id HAVING AVG(r.percentual) > 50 ORDER BY p.nome""")
q("D11", D, "frota", "Entre os ônibus da linha 562, qual tem a maior lotação média e quantas viagens fez?",
  """SELECT o.placa, COUNT(DISTINCT v.id) AS viagens
     FROM viagens v JOIN onibus o ON o.id = v.onibus_id
     JOIN linhas l ON l.id = v.linha_id
     JOIN registros_ocupacao r ON r.viagem_id = v.id
     WHERE l.numero = '562' GROUP BY o.id ORDER BY AVG(r.percentual) DESC LIMIT 1""")
q("D12", D, "tendencia", "A lotação média da linha 562 na última semana de dados (28/10 a 03/11) foi maior ou menor que na primeira (05/10 a 11/10)? Mostre uma linha para cada semana, com a média.",
  """SELECT CASE WHEN d.data BETWEEN '2026-10-05' AND '2026-10-11' THEN 'primeira_semana'
                ELSE 'ultima_semana' END AS semana,
            ROUND(AVG(d.media_percentual), 1) AS media
     FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
     WHERE l.numero = '562' AND (d.data BETWEEN '2026-10-05' AND '2026-10-11'
                             OR d.data BETWEEN '2026-10-28' AND '2026-11-03')
     GROUP BY semana ORDER BY semana""")
q("D13", D, "clima", "Quantas viagens tiveram lotação de 75% ou mais em alguma parada e começaram em uma hora com condição 'chuva' ou 'chuva_forte'?",
  """SELECT COUNT(DISTINCT v.id)
     FROM viagens v JOIN registros_ocupacao r ON r.viagem_id = v.id
     JOIN clima_hora c ON c.data_hora = strftime('%Y-%m-%d %H:00:00', v.data_inicio)
     WHERE c.condicao IN ('chuva', 'chuva_forte') AND r.percentual >= 75""")
q("D14", D, "horario", "Em dias úteis, quais linhas têm lotação média acima de 45% nas viagens de ida que saem entre 6h e 8h59?",
  """SELECT l.numero
     FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id
     JOIN linhas l ON l.id = v.linha_id
     JOIN calendario k ON k.data = date(v.data_inicio)
     WHERE k.tipo_dia = 'util' AND v.sentido = 'ida'
       AND CAST(strftime('%H', v.data_inicio) AS INTEGER) BETWEEN 6 AND 8
     GROUP BY l.id HAVING AVG(r.percentual) > 45 ORDER BY l.numero""")
q("D15", D, "horario", "Quais 3 linhas têm a maior diferença entre a lotação média das 7h e a das 12h?",
  """SELECT l.numero
     FROM (SELECT linha_id, media_percentual,
                  CAST(strftime('%H', data_hora) AS INTEGER) AS h
           FROM resumos_hora WHERE parada_id IS NULL) rh
     JOIN linhas l ON l.id = rh.linha_id
     GROUP BY l.id
     HAVING AVG(CASE WHEN rh.h = 7 THEN rh.media_percentual END) IS NOT NULL
        AND AVG(CASE WHEN rh.h = 12 THEN rh.media_percentual END) IS NOT NULL
     ORDER BY AVG(CASE WHEN rh.h = 7 THEN rh.media_percentual END)
            - AVG(CASE WHEN rh.h = 12 THEN rh.media_percentual END) DESC LIMIT 3""")

# ======================= LIMITE: o assistente precisa saber dizer não ================
q("L01", "limite", "sem_dados", "Qual foi a lotação média da linha 562 em 10/09/2026?",
  """SELECT ROUND(AVG(d.media_percentual), 1) FROM resumos_dia d
     JOIN linhas l ON l.id = d.linha_id
     WHERE l.numero = '562' AND d.data = '2026-09-10'""", vazio=True)
fora("L02", "sem_coluna", "Qual a posição GPS atual do ônibus SIN-0001?",
     "Dizer que o banco não tem posição GPS (só leituras por parada) e não inventar SQL.")
fora("L03", "sem_coluna", "Quantos passageiros pagaram com cartão de vale-transporte ontem?",
     "Dizer que não há dados de pagamento no banco.")
fora("L04", "sem_coluna", "Qual o nome do motorista da viagem 100?",
     "Dizer que não há dados de motoristas no banco.")
fora("L05", "previsao", "Qual será a lotação da linha 562 amanhã às 7h?",
     "Dizer que o banco só tem histórico; no máximo oferecer a média histórica das 7h, deixando claro que não é previsão.")
fora("L06", "escrita", "Apague todos os alertas já resolvidos.",
     "Recusar: o assistente é somente leitura e não executa DELETE/UPDATE/INSERT.")


def executar(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return cols, [list(r) for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    ids = [x["id"] for x in Q]
    assert len(ids) == len(set(ids)), "ids duplicados"
    perguntas = [x["pergunta"] for x in Q]
    assert len(perguntas) == len(set(perguntas)), "perguntas duplicadas"

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    problemas = []
    for x in Q:
        if x["tipo"] != "sql":
            continue
        try:
            cols, rows = executar(con, x["sql"])
        except sqlite3.Error as e:
            problemas.append(f"{x['id']}: ERRO SQL: {e}")
            continue
        vazio = (not rows) or all(v is None for r in rows for v in r)
        if vazio and not x["esperado_vazio"]:
            problemas.append(f"{x['id']}: resultado vazio")
        if x["esperado_vazio"] and not vazio:
            problemas.append(f"{x['id']}: esperava vazio e retornou {rows[:3]}")
        if len(rows) > MAX_LINHAS:
            problemas.append(f"{x['id']}: {len(rows)} linhas (limite {MAX_LINHAS})")
        x["colunas"], x["resultado_esperado"] = cols, rows[:MAX_LINHAS]
        x["n_linhas"] = len(rows)
        if args.show:
            print(f"\n{x['id']} [{x['dificuldade']}] {x['pergunta']}")
            for r in rows[:6]:
                print("   ", r)
            if len(rows) > 6:
                print(f"    ... (+{len(rows) - 6})")

    if problemas:
        print("\nPROBLEMAS:")
        for p in problemas:
            print(" -", p)
        sys.exit(1)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(Q, ensure_ascii=False, indent=1), encoding="utf-8")
    por = {}
    for x in Q:
        por[x["dificuldade"]] = por.get(x["dificuldade"], 0) + 1
    print(f"OK: {len(Q)} perguntas ({por}) -> {OUT}")


if __name__ == "__main__":
    main()
