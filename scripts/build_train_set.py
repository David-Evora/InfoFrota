#!/usr/bin/env python3
"""Gera o conjunto de treino do LoRA de texto para SQL do InfoFrota.

Pares (pergunta em português, resposta JSON com SQL) escritos por famílias de
modelos de pergunta, com valores sorteados do próprio banco. Todo SQL é
executado: nada inválido ou vazio entra no conjunto.

Anti-vazamento em relação a evaluation/questions.json (as 56 perguntas de teste):
  1. nenhuma pergunta de teste entra (comparação com entidades e números mascarados);
  2. nenhum SQL com o mesmo esqueleto de um SQL de referência entra;
  3. cada família marcada como `proximo` (conceito igual ao de uma pergunta de teste,
     ex.: "com e sem chuva") é EXCLUÍDA por padrão. Use --incluir-proximas só para
     comparar; o número principal do LoRA deve vir do conjunto limpo.

Uso:
    python scripts/build_train_set.py                       # limpo, prompt ultra
    python scripts/build_train_set.py --incluir-proximas    # com famílias próximas
    python scripts/build_train_set.py --prompt completo     # system com DDL completo
"""
import argparse
import collections
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from infofrota_ai import prompts  # noqa: E402
from infofrota_ai.db import DB_PATH, SQLBloqueado, SQLErro, executar  # noqa: E402

EVAL = ROOT / "evaluation" / "questions.json"
OUT = ROOT / "training"

FAMILIAS = []


def familia(nome, nivel, n, proximo=(), vazio_ok=False):
    def deco(fn):
        FAMILIAS.append(dict(nome=nome, nivel=nivel, n=n, proximo=tuple(proximo),
                             vazio_ok=vazio_ok, fn=fn))
        return fn
    return deco


# ------------------------------------------------------------------ utilidades
def esc(s):
    return s.replace("'", "''")


def br(iso):
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


TIPO_DIA_PL = {"util": "dias úteis", "sabado": "sábados", "domingo": "domingos",
               "feriado": "feriados"}
TIPO_ALERTA = {"CRITICO": ("crítico", "críticos"), "ATENCAO": ("de atenção", "de atenção")}


def carregar_pools(db_path=DB_PATH):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    q = lambda s: [r[0] for r in con.execute(s)]
    P = dict(
        linhas=q("SELECT numero FROM linhas WHERE monitorada = 1 ORDER BY numero"),
        paradas=q("SELECT nome FROM paradas ORDER BY nome"),
        municipios=q("SELECT DISTINCT municipio FROM paradas ORDER BY municipio"),
        modelos=q("SELECT DISTINCT modelo FROM onibus ORDER BY modelo"),
        placas=q("SELECT placa FROM onibus ORDER BY placa"),
        datas=q("SELECT data FROM calendario ORDER BY data"),
        max_alerta=q("SELECT MAX(id) FROM alertas")[0],
        todos_nomes=q("SELECT nome FROM paradas") + q("SELECT DISTINCT municipio FROM paradas")
        + q("SELECT DISTINCT modelo FROM onibus") + q("SELECT placa FROM onibus"),
    )
    con.close()
    return P


def intervalo(P, rng):
    i = rng.randrange(0, len(P["datas"]) - 3)
    j = min(len(P["datas"]) - 1, i + rng.randint(2, 9))
    return P["datas"][i], P["datas"][j]


def cada(P, rng, itens, fmts, sql_fn, n):
    """Produz até n candidatos: para cada item sorteia um formato de pergunta."""
    out = []
    for it in itens:
        f = rng.choice(fmts)
        out.append((f.format(**it) if isinstance(it, dict) else f.format(it), sql_fn(it), ""))
    rng.shuffle(out)
    return out[:n * 3]


# ================================================================== FÁCIL
@familia("f_contagem_linhas_tipo", "facil", 4, proximo=("F03",))
def _(P, rng):
    fm = ["Quantas linhas {t} existem?", "Qual o total de linhas {t}?"]
    nomes = {"convencional": "convencionais", "circular": "circulares",
             "expresso": "expressas", "noturno": "noturnas"}
    return [(rng.choice(fm).format(t=v), f"SELECT COUNT(*) FROM linhas WHERE tipo = '{k}'", "")
            for k, v in nomes.items()]


@familia("f_contagem_onibus", "facil", 8)
def _(P, rng):
    out = []
    for st, txt in (("ativo", "ativos"), ("manutencao", "em manutenção"), ("inativo", "inativos")):
        out.append((rng.choice(["Quantos ônibus estão {t}?", "Qual o número de ônibus {t} na frota?"]).format(t=txt),
                    f"SELECT COUNT(*) FROM onibus WHERE status = '{st}'", ""))
    for m in P["modelos"]:
        out.append((rng.choice(["Quantos ônibus do modelo {m} a frota tem?", "Quantos {m} existem na frota?"]).format(m=m),
                    f"SELECT COUNT(*) FROM onibus WHERE modelo = '{esc(m)}'", ""))
    return out


@familia("f_onibus_da_linha", "facil", 16)
def _(P, rng):
    fm = ["Quais ônibus têm a linha {L} como linha padrão?", "Que ônibus operam normalmente na linha {L}?",
          "Liste as placas dos ônibus da linha {L}."]
    return [(rng.choice(fm).format(L=L),
             f"SELECT o.placa FROM onibus o JOIN linhas l ON l.id = o.linha_padrao_id WHERE l.numero = '{L}' ORDER BY o.placa", "")
            for L in P["linhas"]]


@familia("f_paradas_municipio", "facil", 8)
def _(P, rng):
    out = [(rng.choice(["Quais paradas existem em {m}?", "Liste as paradas de {m}."]).format(m=m),
            f"SELECT nome FROM paradas WHERE municipio = '{esc(m)}' ORDER BY nome", "") for m in P["municipios"]]
    out.append(("Quantas paradas estão ativas?", "SELECT COUNT(*) FROM paradas WHERE ativa = 1", ""))
    out.append(("Quantas paradas têm coordenadas aproximadas?",
                "SELECT COUNT(*) FROM paradas WHERE coordenadas_aproximadas = 1", ""))
    return out


@familia("f_nome_linha", "facil", 16, proximo=())
def _(P, rng):
    fm = ["Como se chama a linha {L}?", "Qual o trajeto da linha {L}?", "O que é a linha {L}?"]
    return [(rng.choice(fm).format(L=L), f"SELECT nome FROM linhas WHERE numero = '{L}'", "") for L in P["linhas"]]


@familia("f_capacidade", "facil", 18)
def _(P, rng):
    out = [(rng.choice(["Quantos passageiros cabem no ônibus {p}?", "Qual a lotação máxima do ônibus {p}?"]).format(p=p),
            f"SELECT capacidade FROM onibus WHERE placa = '{p}'", "") for p in rng.sample(P["placas"], 12)]
    out += [(f"Qual a capacidade padrão da linha {L}?",
             f"SELECT capacidade_padrao FROM linhas WHERE numero = '{L}'", "") for L in P["linhas"]]
    return out


@familia("f_coord_parada", "facil", 30)
def _(P, rng):
    out = []
    for nm in P["paradas"]:
        out.append((rng.choice(["Quais as coordenadas da parada {n}?", "Onde fica a parada {n}? Mostre latitude e longitude."]).format(n=nm),
                    f"SELECT latitude, longitude FROM paradas WHERE nome = '{esc(nm)}'", ""))
        out.append((rng.choice(["Qual o código oficial da parada {n}?", "Qual o código da parada {n}?"]).format(n=nm),
                    f"SELECT codigo FROM paradas WHERE nome = '{esc(nm)}'", ""))
    return out


@familia("f_viagens_dia_linha", "facil", 30)
def _(P, rng):
    out = []
    for _ in range(80):
        L, d = rng.choice(P["linhas"]), rng.choice(P["datas"])
        f = rng.choice(["Quantas viagens concluídas a linha {L} fez em {d}?",
                        "Quantas viagens a linha {L} completou no dia {d}?"])
        out.append((f.format(L=L, d=br(d)),
                    f"SELECT COUNT(*) FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}' AND date(v.data_inicio) = '{d}' AND v.status = 'concluida'", ""))
    return out


@familia("f_cancel_dia", "facil", 12)
def _(P, rng):
    return [(rng.choice(["Quantas viagens foram canceladas em {d}?", "Quantas viagens canceladas houve no dia {d}?"]).format(d=br(d)),
             f"SELECT COUNT(*) FROM viagens WHERE date(data_inicio) = '{d}' AND status = 'cancelada'", "")
            for d in P["datas"]]


@familia("f_max_lotacao_linha", "facil", 16)
def _(P, rng):
    fm = ["Qual a maior lotação já registrada na linha {L}?", "Qual foi o pico de lotação da linha {L}?"]
    return [(rng.choice(fm).format(L=L),
             f"SELECT MAX(r.percentual) FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}'", "")
            for L in P["linhas"]]


@familia("f_alertas_linha_tipo", "facil", 30)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        for t in ("CRITICO", "ATENCAO"):
            sing, plu = TIPO_ALERTA[t]
            f = rng.choice(["Quantos alertas {x} a linha {L} teve?", "Quantos alertas {x} foram gerados para a linha {L}?"])
            out.append((f.format(x=plu, L=L),
                        f"SELECT COUNT(*) FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE l.numero = '{L}' AND a.tipo = '{t}'", ""))
    return out


@familia("f_alertas_dia", "facil", 15)
def _(P, rng):
    out = []
    for d in P["datas"]:
        t = rng.choice(["CRITICO", "ATENCAO"])
        out.append((f"Quantos alertas {TIPO_ALERTA[t][1]} aconteceram em {br(d)}?",
                    f"SELECT COUNT(*) FROM alertas WHERE tipo = '{t}' AND date(criado_em) = '{d}'", ""))
    return out


@familia("f_calendario_dia", "facil", 20)
def _(P, rng):
    out = []
    for d in P["datas"]:
        out.append((rng.choice(["Que dia da semana foi {d}?", "{d} caiu em qual dia da semana?"]).format(d=br(d)),
                    f"SELECT dia_semana FROM calendario WHERE data = '{d}'", ""))
        out.append((rng.choice(["O dia {d} foi útil, fim de semana ou feriado?", "Que tipo de dia foi {d}?"]).format(d=br(d)),
                    f"SELECT tipo_dia FROM calendario WHERE data = '{d}'", ""))
    return out


@familia("f_clima_dia", "facil", 24)
def _(P, rng):
    out = []
    for d in P["datas"]:
        out.append((rng.choice(["Quanto choveu no total em {d}?", "Qual o volume de chuva acumulado em {d}?"]).format(d=br(d)),
                    f"SELECT ROUND(SUM(chuva_mm), 1) FROM clima_hora WHERE date(data_hora) = '{d}'", ""))
        out.append((rng.choice(["Qual a temperatura máxima registrada em {d}?", "Quão quente ficou em {d}?"]).format(d=br(d)),
                    f"SELECT MAX(temperatura_c) FROM clima_hora WHERE date(data_hora) = '{d}'", ""))
        out.append((f"Em que hora fez mais calor em {br(d)}?",
                    f"SELECT data_hora FROM clima_hora WHERE date(data_hora) = '{d}' ORDER BY temperatura_c DESC LIMIT 1", ""))
    return out


@familia("f_msg_alerta", "facil", 8)
def _(P, rng):
    return [(rng.choice(["Qual a mensagem do alerta {i}?", "O que diz o alerta de número {i}?"]).format(i=i),
             f"SELECT mensagem FROM alertas WHERE id = {i}", "")
            for i in rng.sample(range(1, P["max_alerta"]), 20)]


# ================================================================== MÉDIO
@familia("m_media_linha_tipodia", "medio", 40)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        for t, pl in TIPO_DIA_PL.items():
            f = rng.choice(["Qual a lotação média da linha {L} em {pl}?", "Em {pl}, qual a lotação média da linha {L}?"])
            out.append((f.format(L=L, pl=pl),
                        f"SELECT ROUND(AVG(d.media_percentual), 1) FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id JOIN calendario k ON k.data = d.data WHERE l.numero = '{L}' AND k.tipo_dia = '{t}'", ""))
    return out


@familia("m_media_linha_hora", "medio", 40)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        for h in rng.sample(range(5, 23), 6):
            f = rng.choice(["Qual a lotação média da linha {L} às {h}h?", "Às {h} horas, quanto a linha {L} costuma estar lotada, em média?"])
            out.append((f.format(L=L, h=h),
                        f"SELECT ROUND(AVG(rh.media_percentual), 1) FROM resumos_hora rh JOIN linhas l ON l.id = rh.linha_id WHERE l.numero = '{L}' AND rh.parada_id IS NULL AND CAST(strftime('%H', rh.data_hora) AS INTEGER) = {h}", ""))
    return out


@familia("m_top_linhas", "medio", 30, proximo=("M02", "M07", "M08"))
def _(P, rng):
    out = []
    for n in (3, 4, 5, 6):
        for t in ("CRITICO", "ATENCAO"):
            out.append((f"Quais as {n} linhas com mais alertas {TIPO_ALERTA[t][1]} e quantos cada uma teve?",
                        f"SELECT l.numero, COUNT(*) AS total FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE a.tipo = '{t}' GROUP BY l.id ORDER BY total DESC, l.numero LIMIT {n}", ""))
        out.append((f"Quais as {n} linhas com mais passageiros embarcados, com o total de cada uma?",
                    f"SELECT l.numero, SUM(d.total_embarcaram) AS total FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id GROUP BY l.id ORDER BY total DESC, l.numero LIMIT {n}", ""))
        out.append((f"Quais as {n} linhas com maior lotação média?",
                    f"SELECT l.numero, ROUND(AVG(d.media_percentual), 1) AS media FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id GROUP BY l.id ORDER BY AVG(d.media_percentual) DESC, l.numero LIMIT {n}", ""))
        out.append((f"Quais as {n} linhas com mais viagens canceladas?",
                    f"SELECT l.numero, COUNT(*) AS canceladas FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE v.status = 'cancelada' GROUP BY l.id ORDER BY canceladas DESC, l.numero LIMIT {n}", ""))
    return out


@familia("m_top_paradas", "medio", 24)
def _(P, rng):
    out = []
    for n in (3, 4, 5, 6):
        out.append((f"Quais as {n} paradas onde mais passageiros embarcam, e quantos embarcam?",
                    f"SELECT p.nome, SUM(r.embarcaram) AS total FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.id ORDER BY total DESC, p.nome LIMIT {n}", ""))
        out.append((f"Quais as {n} paradas com maior lotação média dos ônibus?",
                    f"SELECT p.nome, ROUND(AVG(r.percentual), 1) AS media FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.id ORDER BY AVG(r.percentual) DESC, p.nome LIMIT {n}", ""))
        out.append((f"Quais as {n} paradas onde mais passageiros desembarcam?",
                    f"SELECT p.nome FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.id ORDER BY SUM(r.desembarcaram) DESC, p.nome LIMIT {n}", ""))
    return out


@familia("m_top_paradas_criticas", "medio", 6, proximo=("M06",))
def _(P, rng):
    return [(f"Quais as {n} paradas com mais leituras acima de 90% e quantas foram?",
             f"SELECT p.nome, SUM(r.percentual >= 90) AS criticas FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.id ORDER BY criticas DESC, p.nome LIMIT {n}", "")
            for n in (3, 4, 5, 6)]


@familia("m_municipio", "medio", 16)
def _(P, rng):
    out = [("Qual o total de passageiros embarcados em cada município?",
            "SELECT p.municipio, SUM(r.embarcaram) AS total FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.municipio ORDER BY total DESC", ""),
           ("Qual a maior lotação registrada em cada município?",
            "SELECT p.municipio, MAX(r.percentual) AS maxima FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.municipio", ""),
           ("Quantas leituras de ocupação existem em cada município?",
            "SELECT p.municipio, COUNT(*) AS leituras FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.municipio", ""),
           ("Quantas paradas tem cada município?",
            "SELECT municipio, COUNT(*) AS paradas FROM paradas GROUP BY municipio ORDER BY paradas DESC, municipio", "")]
    for m in P["municipios"]:
        out.append((f"Qual o total de embarques nas paradas de {m}?",
                    f"SELECT SUM(r.embarcaram) FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id WHERE p.municipio = '{esc(m)}'", ""))
        out.append((f"Quantas leituras críticas (90% ou mais) houve em {m}?",
                    f"SELECT COUNT(*) FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id WHERE p.municipio = '{esc(m)}' AND r.percentual >= 90", ""))
    return out


@familia("m_modelo", "medio", 10)
def _(P, rng):
    out = [("Qual a lotação média das viagens por modelo de ônibus?",
            "SELECT o.modelo, ROUND(AVG(r.percentual), 1) AS media FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN onibus o ON o.id = v.onibus_id GROUP BY o.modelo ORDER BY media DESC", ""),
           ("Quantas viagens concluídas cada modelo de ônibus fez?",
            "SELECT o.modelo, COUNT(*) AS viagens FROM viagens v JOIN onibus o ON o.id = v.onibus_id WHERE v.status = 'concluida' GROUP BY o.modelo ORDER BY viagens DESC", "")]
    for m in P["modelos"]:
        out.append((f"Qual a lotação média das viagens feitas por ônibus {m}?",
                    f"SELECT ROUND(AVG(r.percentual), 1) FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN onibus o ON o.id = v.onibus_id WHERE o.modelo = '{esc(m)}'", ""))
    return out


@familia("m_sentido_linha", "medio", 16)
def _(P, rng):
    fm = ["Quantas viagens de ida e de volta a linha {L} concluiu?", "Como se dividem as viagens da linha {L} entre ida e volta?"]
    return [(rng.choice(fm).format(L=L),
             f"SELECT v.sentido, COUNT(*) AS viagens FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}' AND v.status = 'concluida' GROUP BY v.sentido", "")
            for L in P["linhas"]]


@familia("m_duracao_linha", "medio", 16)
def _(P, rng):
    fm = ["Qual a duração média, em minutos, das viagens da linha {L}?", "Quanto tempo, em minutos, leva em média uma viagem da linha {L}?"]
    return [(rng.choice(fm).format(L=L),
             f"SELECT ROUND(AVG((julianday(v.data_fim) - julianday(v.data_inicio)) * 1440), 1) FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}' AND v.status = 'concluida'", "")
            for L in P["linhas"]]


@familia("m_duracao_limiar", "medio", 6, proximo=("M14",))
def _(P, rng):
    return [(f"Quais linhas têm duração média de viagem abaixo de {x} minutos?",
             f"SELECT l.numero FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE v.status = 'concluida' GROUP BY l.id HAVING AVG((julianday(v.data_fim) - julianday(v.data_inicio)) * 1440) < {x} ORDER BY l.numero", "")
            for x in (25, 35, 45)]


@familia("m_linhas_media_acima", "medio", 8)
def _(P, rng):
    return [(f"Quais linhas têm lotação média diária acima de {x}%?",
             f"SELECT l.numero FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id GROUP BY l.id HAVING AVG(d.media_percentual) > {x} ORDER BY l.numero", "")
            for x in (10, 15, 20, 24, 26)]


@familia("m_alertas_hora", "medio", 6)
def _(P, rng):
    out = []
    for t in ("CRITICO", "ATENCAO"):
        x = TIPO_ALERTA[t][1]
        out.append((f"Em que hora do dia são gerados mais alertas {x}?",
                    f"SELECT CAST(strftime('%H', criado_em) AS INTEGER) AS hora FROM alertas WHERE tipo = '{t}' GROUP BY hora ORDER BY COUNT(*) DESC LIMIT 1", ""))
        out.append((f"Quais as 3 horas do dia com mais alertas {x} e quantos foram?",
                    f"SELECT CAST(strftime('%H', criado_em) AS INTEGER) AS hora, COUNT(*) AS total FROM alertas WHERE tipo = '{t}' GROUP BY hora ORDER BY total DESC LIMIT 3", ""))
    return out


@familia("m_alertas_diasemana", "medio", 4)
def _(P, rng):
    return [("Em qual dia da semana há mais alertas críticos?",
             "SELECT k.dia_semana FROM alertas a JOIN calendario k ON k.data = date(a.criado_em) WHERE a.tipo = 'CRITICO' GROUP BY k.dia_semana ORDER BY COUNT(*) DESC LIMIT 1", ""),
            ("Quantos alertas de atenção ocorrem em cada tipo de dia?",
             "SELECT k.tipo_dia, COUNT(*) AS total FROM alertas a JOIN calendario k ON k.data = date(a.criado_em) WHERE a.tipo = 'ATENCAO' GROUP BY k.tipo_dia", "")]


@familia("m_embarques_dia_linha", "medio", 30)
def _(P, rng):
    out = []
    for _ in range(80):
        L, d = rng.choice(P["linhas"]), rng.choice(P["datas"])
        f = rng.choice(["Quantos passageiros embarcaram na linha {L} em {d}?", "Qual o total de embarques da linha {L} no dia {d}?"])
        out.append((f.format(L=L, d=br(d)),
                    f"SELECT d.total_embarcaram FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id WHERE l.numero = '{L}' AND d.data = '{d}'", ""))
    return out


@familia("m_periodo", "medio", 40)
def _(P, rng):
    out = []
    for _ in range(60):
        d1, d2 = intervalo(P, rng)
        L = rng.choice(P["linhas"])
        k = rng.randrange(3)
        if k == 0:
            out.append((f"Quantos alertas críticos houve entre {br(d1)} e {br(d2)}?",
                        f"SELECT COUNT(*) FROM alertas WHERE tipo = 'CRITICO' AND date(criado_em) BETWEEN '{d1}' AND '{d2}'", ""))
        elif k == 1:
            out.append((f"Quantos passageiros embarcaram na linha {L} entre {br(d1)} e {br(d2)}?",
                        f"SELECT SUM(d.total_embarcaram) FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id WHERE l.numero = '{L}' AND d.data BETWEEN '{d1}' AND '{d2}'", ""))
        else:
            out.append((f"Quantas viagens foram canceladas entre {br(d1)} e {br(d2)}?",
                        f"SELECT COUNT(*) FROM viagens WHERE status = 'cancelada' AND date(data_inicio) BETWEEN '{d1}' AND '{d2}'", ""))
    return out


@familia("m_paradas_linha", "medio", 30)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        s = rng.choice(["ida", "volta"])
        out.append((rng.choice(["Quantas paradas a linha {L} tem no sentido {s}?", "Quantos pontos a linha {L} atende na {s}?"]).format(L=L, s=s),
                    f"SELECT COUNT(*) FROM linha_paradas lp JOIN linhas l ON l.id = lp.linha_id WHERE l.numero = '{L}' AND lp.sentido = '{s}'", ""))
        out.append((rng.choice(["De qual parada sai a linha {L} no sentido {s}?", "Qual a primeira parada da linha {L} na {s}?"]).format(L=L, s=s),
                    f"SELECT p.nome FROM linha_paradas lp JOIN linhas l ON l.id = lp.linha_id JOIN paradas p ON p.id = lp.parada_id WHERE l.numero = '{L}' AND lp.sentido = '{s}' ORDER BY lp.ordem LIMIT 1", ""))
        out.append((rng.choice(["Qual a última parada da linha {L} no sentido {s}?", "Onde termina a linha {L} na {s}?"]).format(L=L, s=s),
                    f"SELECT p.nome FROM linha_paradas lp JOIN linhas l ON l.id = lp.linha_id JOIN paradas p ON p.id = lp.parada_id WHERE l.numero = '{L}' AND lp.sentido = '{s}' ORDER BY lp.ordem DESC LIMIT 1", ""))
    return out


@familia("m_linhas_parada", "medio", 20, proximo=("M19",))
def _(P, rng):
    out = []
    for nm in P["paradas"]:
        out.append((f"Quais linhas passam pela parada {nm}?",
                    f"SELECT DISTINCT l.numero FROM linha_paradas lp JOIN linhas l ON l.id = lp.linha_id JOIN paradas p ON p.id = lp.parada_id WHERE p.nome = '{esc(nm)}' ORDER BY l.numero", ""))
        out.append((f"Quantas linhas atendem a parada {nm}?",
                    f"SELECT COUNT(DISTINCT lp.linha_id) FROM linha_paradas lp JOIN paradas p ON p.id = lp.parada_id WHERE p.nome = '{esc(nm)}'", ""))
    return out


@familia("m_distintos", "medio", 36)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        out.append((rng.choice(["Quantos ônibus diferentes operaram a linha {L}?", "Quantos veículos distintos rodaram na linha {L}?"]).format(L=L),
                    f"SELECT COUNT(DISTINCT v.onibus_id) FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}'", ""))
        out.append((f"Quantas paradas diferentes a linha {L} atende, somando ida e volta?",
                    f"SELECT COUNT(DISTINCT lp.parada_id) FROM linha_paradas lp JOIN linhas l ON l.id = lp.linha_id WHERE l.numero = '{L}'", ""))
        out.append((f"Em quantos dias diferentes a linha {L} teve alerta crítico?",
                    f"SELECT COUNT(DISTINCT date(a.criado_em)) FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE l.numero = '{L}' AND a.tipo = 'CRITICO'", ""))
    for d in rng.sample(P["datas"], 6):
        out.append((f"Quantas linhas diferentes tiveram viagens em {br(d)}?",
                    f"SELECT COUNT(DISTINCT linha_id) FROM viagens WHERE date(data_inicio) = '{d}'", ""))
    return out


@familia("m_taxa_cancel", "medio", 18)
def _(P, rng):
    out = [("Qual a taxa de cancelamento de viagens de cada linha, em percentual?",
            "SELECT l.numero, ROUND(100.0 * SUM(v.status = 'cancelada') / COUNT(*), 1) AS taxa FROM viagens v JOIN linhas l ON l.id = v.linha_id GROUP BY l.id ORDER BY taxa DESC, l.numero", "")]
    for L in P["linhas"]:
        out.append((rng.choice(["Qual o percentual de viagens canceladas da linha {L}?", "Que porcentagem das viagens da linha {L} foi cancelada?"]).format(L=L),
                    f"SELECT ROUND(100.0 * SUM(v.status = 'cancelada') / COUNT(*), 2) FROM viagens v JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}'", ""))
    return out


@familia("m_dia_extremo", "medio", 6, proximo=("M17", "D07"))
def _(P, rng):
    return [("Qual dia teve a maior lotação média considerando todas as linhas?",
             "SELECT d.data FROM resumos_dia d GROUP BY d.data ORDER BY AVG(d.media_percentual) DESC LIMIT 1", ""),
            ("Qual dia teve a menor lotação média considerando todas as linhas?",
             "SELECT d.data FROM resumos_dia d GROUP BY d.data ORDER BY AVG(d.media_percentual) LIMIT 1", ""),
            ("Em que dia mais passageiros embarcaram somando todas as linhas?",
             "SELECT data FROM resumos_dia GROUP BY data ORDER BY SUM(total_embarcaram) DESC LIMIT 1", ""),
            ("Qual dia teve mais viagens canceladas?",
             "SELECT date(data_inicio) AS dia FROM viagens WHERE status = 'cancelada' GROUP BY dia ORDER BY COUNT(*) DESC LIMIT 1", "")]


@familia("m_precaucao", "medio", 16)
def _(P, rng):
    fm = ["Quantos alertas da linha {L} estão em precaução?", "Quantos alertas da linha {L} tiveram alguma precaução registrada?"]
    return [(rng.choice(fm).format(L=L),
             f"SELECT COUNT(*) FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE l.numero = '{L}' AND a.em_precaucao = 1", "")
            for L in P["linhas"]]


@familia("m_resolucao", "medio", 18)
def _(P, rng):
    out = [(f"Quantos alertas {TIPO_ALERTA[t][1]} já foram resolvidos?",
            f"SELECT COUNT(*) FROM alertas WHERE tipo = '{t}' AND resolvido = 1", "") for t in ("CRITICO", "ATENCAO")]
    for L in P["linhas"]:
        out.append((rng.choice(["Qual o tempo médio, em minutos, para resolver alertas críticos da linha {L}?", "Quanto tempo leva, em média, para um alerta crítico da linha {L} ser resolvido (em minutos)?"]).format(L=L),
                    f"SELECT ROUND(AVG((julianday(a.resolvido_em) - julianday(a.criado_em)) * 1440), 1) FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE l.numero = '{L}' AND a.tipo = 'CRITICO' AND a.resolvido = 1", ""))
    return out


@familia("m_clima_dias", "medio", 8, proximo=("M10",))
def _(P, rng):
    out = [(f"Em quantos dias houve {txt}?",
            f"SELECT COUNT(DISTINCT date(data_hora)) FROM clima_hora WHERE condicao = '{c}'", "")
           for c, txt in (("garoa", "garoa"), ("chuva", "chuva moderada"), ("chuva_forte", "chuva forte"))]
    out += [(f"Em quais dias a chuva passou de {x} mm em alguma hora?",
             f"SELECT DISTINCT date(data_hora) AS dia FROM clima_hora WHERE chuva_mm > {x} ORDER BY dia", "")
            for x in (0.5, 1, 2, 3)]
    return out


@familia("m_viagens_lotadas", "medio", 16)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        x = rng.choice([80, 90, 100])
        out.append((rng.choice(["Quantas viagens da linha {L} passaram de {x}% de lotação em alguma parada?", "Em quantas viagens da linha {L} a lotação chegou a {x}% ou mais em alguma parada?"]).format(L=L, x=x),
                    f"SELECT COUNT(DISTINCT r.viagem_id) FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}' AND r.percentual >= {x}", ""))
    return out


# ================================================================== DIFÍCIL
@familia("d_topo_grupo_parada", "dificil", 10, proximo=("D04",))
def _(P, rng):
    return [("Para cada linha, qual parada tem a maior lotação média?",
             "WITH m AS (SELECT l.numero AS linha, p.nome AS parada, AVG(r.percentual) AS media FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN linhas l ON l.id = v.linha_id JOIN paradas p ON p.id = r.parada_id GROUP BY l.id, p.id), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY linha ORDER BY media DESC) AS rn FROM m) SELECT linha, parada FROM r WHERE rn = 1 ORDER BY linha", ""),
            ("Para cada município, qual linha tem a maior lotação média nas paradas dele?",
             "WITH m AS (SELECT p.municipio, l.numero AS linha, AVG(r.percentual) AS media FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN linhas l ON l.id = v.linha_id JOIN paradas p ON p.id = r.parada_id GROUP BY p.municipio, l.id), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY municipio ORDER BY media DESC) AS rn FROM m) SELECT municipio, linha FROM r WHERE rn = 1 ORDER BY municipio", ""),
            ("Para cada sentido, qual parada tem mais embarques no total?",
             "WITH m AS (SELECT v.sentido, p.nome AS parada, SUM(r.embarcaram) AS total FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN paradas p ON p.id = r.parada_id GROUP BY v.sentido, p.id), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY sentido ORDER BY total DESC) AS rn FROM m) SELECT sentido, parada FROM r WHERE rn = 1", "")]


@familia("d_topo_grupo_hora", "dificil", 8, proximo=("D01",))
def _(P, rng):
    return [("Para cada tipo de dia, em que hora a lotação média é maior?",
             "WITH m AS (SELECT k.tipo_dia, CAST(strftime('%H', rh.data_hora) AS INTEGER) AS hora, AVG(rh.media_percentual) AS media FROM resumos_hora rh JOIN calendario k ON k.data = date(rh.data_hora) WHERE rh.parada_id IS NULL GROUP BY k.tipo_dia, hora), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY tipo_dia ORDER BY media DESC) AS rn FROM m) SELECT tipo_dia, hora FROM r WHERE rn = 1 ORDER BY tipo_dia", ""),
            ("Para cada linha, em que hora mais passageiros embarcam, em média?",
             "WITH m AS (SELECT linha_id, CAST(strftime('%H', data_hora) AS INTEGER) AS hora, AVG(total_embarcaram) AS media FROM resumos_hora WHERE parada_id IS NULL GROUP BY linha_id, hora), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY linha_id ORDER BY media DESC) AS rn FROM m) SELECT l.numero, r.hora FROM r JOIN linhas l ON l.id = r.linha_id WHERE r.rn = 1 ORDER BY l.numero", "")]


@familia("d_ultimo_por_onibus", "dificil", 32)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        sql = (f"WITH x AS (SELECT o.placa, r.momento, r.percentual, ROW_NUMBER() OVER (PARTITION BY o.id ORDER BY r.momento DESC) AS rn FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN onibus o ON o.id = v.onibus_id JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}') SELECT placa, momento, percentual FROM x WHERE rn = 1 ORDER BY placa")
        for f in ("Qual a última leitura de ocupação de cada ônibus que rodou na linha {L}?",
                  "Mostre, para cada ônibus da linha {L}, a leitura de lotação mais recente."):
            out.append((f.format(L=L), sql, ""))
    return out


@familia("d_primeiro_por_dia", "dificil", 24)
def _(P, rng):
    out = []
    for _ in range(60):
        L, d = rng.choice(P["linhas"]), rng.choice(P["datas"])
        sql = (f"WITH x AS (SELECT o.placa, v.data_inicio, ROW_NUMBER() OVER (PARTITION BY o.id ORDER BY v.data_inicio) AS rn FROM viagens v JOIN onibus o ON o.id = v.onibus_id JOIN linhas l ON l.id = v.linha_id WHERE l.numero = '{L}' AND date(v.data_inicio) = '{d}' AND v.status = 'concluida') SELECT placa, data_inicio FROM x WHERE rn = 1 ORDER BY placa")
        out.append((rng.choice(["Qual foi a primeira viagem de cada ônibus da linha {L} em {d}?", "Em {d}, a que horas cada ônibus da linha {L} começou a primeira viagem?"]).format(L=L, d=br(d)), sql, ""))
    return out


@familia("d_top2_por_grupo", "dificil", 8)
def _(P, rng):
    out = []
    for n in (2, 3):
        out.append((f"Quais as {n} paradas com mais embarques em cada município?",
                    f"WITH m AS (SELECT p.municipio, p.nome, SUM(r.embarcaram) AS total FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.id), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY municipio ORDER BY total DESC) AS rn FROM m) SELECT municipio, nome FROM r WHERE rn <= {n} ORDER BY municipio, rn", ""))
        out.append((f"Quais os {n} ônibus mais lotados, em média, de cada modelo?",
                    f"WITH m AS (SELECT o.modelo, o.placa, AVG(r.percentual) AS media FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN onibus o ON o.id = v.onibus_id GROUP BY o.id), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY modelo ORDER BY media DESC) AS rn FROM m) SELECT modelo, placa FROM r WHERE rn <= {n} ORDER BY modelo, rn", ""))
        out.append((f"Quais as {n} linhas com mais alertas críticos em cada tipo de linha?",
                    f"WITH m AS (SELECT l.tipo, l.numero, COUNT(*) AS total FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE a.tipo = 'CRITICO' GROUP BY l.id), r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY tipo ORDER BY total DESC) AS rn FROM m) SELECT tipo, numero FROM r WHERE rn <= {n} ORDER BY tipo, rn", ""))
    return out


@familia("d_subconsulta_media", "dificil", 6)
def _(P, rng):
    base = lambda col: f"(SELECT linha_id, SUM({col}) AS t FROM resumos_dia GROUP BY linha_id)"
    out = []
    for col, txt in (("total_embarcaram", "passageiros embarcados"), ("total_viagens", "viagens"),
                     ("total_alertas_critico", "alertas críticos")):
        out.append((f"Quais linhas têm total de {txt} acima da média entre as linhas?",
                    f"SELECT l.numero FROM {base(col)} x JOIN linhas l ON l.id = x.linha_id WHERE x.t > (SELECT AVG(t) FROM {base(col)}) ORDER BY l.numero", ""))
    return out


@familia("d_participacao", "dificil", 6)
def _(P, rng):
    out = []
    for col, txt in (("total_embarcaram", "passageiros embarcados"), ("total_desembarcaram", "passageiros desembarcados"),
                     ("total_viagens", "viagens")):
        out.append((f"Qual a participação percentual de cada linha no total de {txt}?",
                    f"SELECT l.numero, ROUND(100.0 * SUM(d.{col}) / (SELECT SUM({col}) FROM resumos_dia), 1) AS participacao FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id GROUP BY l.id ORDER BY participacao DESC, l.numero", ""))
    return out


@familia("d_ranking", "dificil", 6)
def _(P, rng):
    return [("Mostre o ranking das linhas por lotação média, com a posição de cada uma.",
             "SELECT RANK() OVER (ORDER BY AVG(d.media_percentual) DESC) AS posicao, l.numero, ROUND(AVG(d.media_percentual), 1) AS media FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id GROUP BY l.id ORDER BY posicao, l.numero", ""),
            ("Faça um ranking das linhas pelo total de passageiros embarcados.",
             "SELECT RANK() OVER (ORDER BY SUM(d.total_embarcaram) DESC) AS posicao, l.numero, SUM(d.total_embarcaram) AS total FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id GROUP BY l.id ORDER BY posicao, l.numero", ""),
            ("Qual a posição de cada município no ranking de embarques?",
             "SELECT RANK() OVER (ORDER BY SUM(r.embarcaram) DESC) AS posicao, p.municipio, SUM(r.embarcaram) AS total FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.municipio ORDER BY posicao", "")]


@familia("d_paradas_limiar", "dificil", 10)
def _(P, rng):
    out = []
    for x, k in ((70, 100), (80, 100), (80, 300), (90, 50), (90, 100), (100, 30), (100, 10), (75, 200)):
        out.append((f"Quais paradas tiveram mais de {k} leituras com lotação acima de {x}%? Mostre quantas foram.",
                    f"SELECT p.nome, COUNT(*) AS leituras FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id WHERE r.percentual > {x} GROUP BY p.id HAVING COUNT(*) > {k} ORDER BY leituras DESC, p.nome", ""))
    return out


@familia("d_variacao_dia", "dificil", 32)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        base = f"SELECT d.data, d.media_percentual - LAG(d.media_percentual) OVER (ORDER BY d.data) AS delta FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id WHERE l.numero = '{L}'"
        out.append((f"Em que dia a lotação média da linha {L} mais subiu em relação ao dia anterior?",
                    f"SELECT data FROM ({base}) WHERE delta IS NOT NULL ORDER BY delta DESC LIMIT 1", ""))
        out.append((f"Em que dia a lotação média da linha {L} mais caiu em relação ao dia anterior?",
                    f"SELECT data FROM ({base}) WHERE delta IS NOT NULL ORDER BY delta LIMIT 1", ""))
    return out


@familia("d_acima_media_linha", "dificil", 16)
def _(P, rng):
    out = []
    for L in P["linhas"]:
        out.append((rng.choice(["Em quais horas a lotação média da linha {L} fica acima da média da própria linha?", "Quais horas do dia a linha {L} lota mais do que a sua média geral?"]).format(L=L),
                    f"SELECT CAST(strftime('%H', rh.data_hora) AS INTEGER) AS hora FROM resumos_hora rh JOIN linhas l ON l.id = rh.linha_id WHERE l.numero = '{L}' AND rh.parada_id IS NULL GROUP BY hora HAVING AVG(rh.media_percentual) > (SELECT AVG(rh2.media_percentual) FROM resumos_hora rh2 JOIN linhas l2 ON l2.id = rh2.linha_id WHERE l2.numero = '{L}' AND rh2.parada_id IS NULL) ORDER BY hora", ""))
    return out


@familia("d_pivot", "dificil", 6)
def _(P, rng):
    return [("Para cada linha, mostre lado a lado a lotação média nos dias úteis e nos fins de semana.",
             "SELECT l.numero, ROUND(AVG(CASE WHEN k.tipo_dia = 'util' THEN d.media_percentual END), 1) AS util, ROUND(AVG(CASE WHEN k.tipo_dia IN ('sabado', 'domingo') THEN d.media_percentual END), 1) AS fim_de_semana FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id JOIN calendario k ON k.data = d.data GROUP BY l.id ORDER BY l.numero", ""),
            ("Para cada linha, compare os alertas críticos e os de atenção em duas colunas.",
             "SELECT l.numero, SUM(a.tipo = 'CRITICO') AS criticos, SUM(a.tipo = 'ATENCAO') AS atencao FROM alertas a JOIN linhas l ON l.id = a.linha_id GROUP BY l.id ORDER BY l.numero", ""),
            ("Para cada município, mostre o total de embarques e o de desembarques lado a lado.",
             "SELECT p.municipio, SUM(r.embarcaram) AS embarques, SUM(r.desembarcaram) AS desembarques FROM registros_ocupacao r JOIN paradas p ON p.id = r.parada_id GROUP BY p.municipio ORDER BY p.municipio", "")]


# --- difíceis próximas de perguntas de teste (excluídas por padrão) ---
@familia("d_comparacao_chuva", "dificil", 24, proximo=("D03", "M09", "D13"))
def _(P, rng):
    out = []
    for L in P["linhas"]:
        h = rng.choice([7, 8, 17, 18])
        out.append((f"Na linha {L}, qual a lotação média às {h}h com e sem chuva (chuva_mm > 0)? Uma linha para cada caso.",
                    f"SELECT CASE WHEN chuva_mm > 0 THEN 'com chuva' ELSE 'sem chuva' END AS clima, ROUND(AVG(media_percentual), 1) AS media FROM v_lotacao_clima WHERE linha_numero = '{L}' AND CAST(strftime('%H', data_hora) AS INTEGER) = {h} GROUP BY clima", ""))
    out.append(("Quantas viagens começaram em horas com chuva forte e tiveram lotação de 90% ou mais em alguma parada?",
                "SELECT COUNT(DISTINCT v.id) FROM viagens v JOIN registros_ocupacao r ON r.viagem_id = v.id JOIN clima_hora c ON c.data_hora = strftime('%Y-%m-%d %H:00:00', v.data_inicio) WHERE c.condicao = 'chuva_forte' AND r.percentual >= 90", ""))
    return out


@familia("d_semanas", "dificil", 16, proximo=("D12",))
def _(P, rng):
    return [(f"A lotação média da linha {L} subiu ou caiu da primeira (05/10 a 11/10) para a segunda semana (12/10 a 18/10)? Uma linha para cada semana, com a média.",
             f"SELECT CASE WHEN d.data BETWEEN '2026-10-05' AND '2026-10-11' THEN 'semana_1' ELSE 'semana_2' END AS semana, ROUND(AVG(d.media_percentual), 1) AS media FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id WHERE l.numero = '{L}' AND d.data BETWEEN '2026-10-05' AND '2026-10-18' GROUP BY semana ORDER BY semana", "")
            for L in P["linhas"]]


@familia("d_tipo_dia_linha", "dificil", 16, proximo=("D08", "M05"))
def _(P, rng):
    return [(f"Na linha {L}, qual a lotação média em cada tipo de dia?",
             f"SELECT k.tipo_dia, ROUND(AVG(d.media_percentual), 1) AS media FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id JOIN calendario k ON k.data = d.data WHERE l.numero = '{L}' GROUP BY k.tipo_dia ORDER BY media DESC", "")
            for L in P["linhas"]]


@familia("d_pico_sentido", "dificil", 12, proximo=("D10", "D14"))
def _(P, rng):
    return [(f"Em dias úteis, quais linhas têm lotação média acima de {x}% nas viagens de {s} que saem entre {h}h e {h}h59?",
             f"SELECT l.numero FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id JOIN linhas l ON l.id = v.linha_id JOIN calendario k ON k.data = date(v.data_inicio) WHERE k.tipo_dia = 'util' AND v.sentido = '{s}' AND CAST(strftime('%H', v.data_inicio) AS INTEGER) = {h} GROUP BY l.id HAVING AVG(r.percentual) > {x} ORDER BY l.numero", "")
            for s, h, x in (("ida", 7, 40), ("volta", 17, 40), ("ida", 8, 50), ("volta", 18, 45), ("ida", 6, 30), ("volta", 16, 30))]


@familia("d_pct_viagens_alerta", "dificil", 16, proximo=("D05",))
def _(P, rng):
    return [(f"Qual o percentual de viagens da linha {L} que tiveram pelo menos um alerta?",
             f"SELECT ROUND(100.0 * COUNT(DISTINCT a.viagem_id) / COUNT(DISTINCT v.id), 1) FROM viagens v JOIN linhas l ON l.id = v.linha_id LEFT JOIN alertas a ON a.viagem_id = v.id WHERE l.numero = '{L}' AND v.status = 'concluida'", "")
            for L in P["linhas"]]


@familia("d_tempo_resolucao_top", "dificil", 8, proximo=("D06",))
def _(P, rng):
    return [(f"Quais os {n} alertas de atenção que demoraram mais para ser resolvidos? Mostre a linha e os minutos.",
             f"SELECT a.id, l.numero, ROUND((julianday(a.resolvido_em) - julianday(a.criado_em)) * 1440, 1) AS minutos FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE a.tipo = 'ATENCAO' AND a.resolvido = 1 ORDER BY minutos DESC, a.id LIMIT {n}", "")
            for n in (3, 5, 10)]


@familia("d_media_dia_semana", "dificil", 6, proximo=("D07",))
def _(P, rng):
    return [("Qual a média diária de viagens concluídas, somando todas as linhas, para cada dia da semana?",
             "SELECT k.dia_semana, ROUND(AVG(t.viagens), 0) AS media_viagens FROM (SELECT data, SUM(total_viagens) AS viagens FROM resumos_dia GROUP BY data) t JOIN calendario k ON k.data = t.data GROUP BY k.dia_semana", ""),
            ("Qual a média diária de alertas críticos, somando todas as linhas, por dia da semana?",
             "SELECT k.dia_semana, ROUND(AVG(t.alertas), 1) AS media_alertas FROM (SELECT data, SUM(total_alertas_critico) AS alertas FROM resumos_dia GROUP BY data) t JOIN calendario k ON k.data = t.data GROUP BY k.dia_semana", "")]


@familia("d_diferenca_horas", "dificil", 10, proximo=("D15",))
def _(P, rng):
    out = []
    for h1, h2 in ((8, 14), (17, 21), (6, 15), (18, 10)):
        out.append((f"Quais 3 linhas têm a maior diferença entre a lotação média das {h1}h e a das {h2}h?",
                    f"SELECT l.numero FROM (SELECT linha_id, media_percentual, CAST(strftime('%H', data_hora) AS INTEGER) AS h FROM resumos_hora WHERE parada_id IS NULL) rh JOIN linhas l ON l.id = rh.linha_id GROUP BY l.id HAVING AVG(CASE WHEN rh.h = {h1} THEN rh.media_percentual END) IS NOT NULL AND AVG(CASE WHEN rh.h = {h2} THEN rh.media_percentual END) IS NOT NULL ORDER BY AVG(CASE WHEN rh.h = {h1} THEN rh.media_percentual END) - AVG(CASE WHEN rh.h = {h2} THEN rh.media_percentual END) DESC LIMIT 3", ""))
    return out


@familia("d_lotacao_veiculo", "dificil", 16, proximo=("D11",))
def _(P, rng):
    return [(f"Entre os ônibus da linha {L}, qual fez mais viagens concluídas e qual a lotação média dele?",
             f"SELECT o.placa, COUNT(DISTINCT v.id) AS viagens, ROUND(AVG(r.percentual), 1) AS media FROM viagens v JOIN onibus o ON o.id = v.onibus_id JOIN linhas l ON l.id = v.linha_id JOIN registros_ocupacao r ON r.viagem_id = v.id WHERE l.numero = '{L}' AND v.status = 'concluida' GROUP BY o.id ORDER BY viagens DESC, o.placa LIMIT 1", "")
            for L in P["linhas"]]


@familia("d_dias_limiar", "dificil", 5, proximo=("D09",))
def _(P, rng):
    return [(f"Quais linhas tiveram alerta crítico em mais de {k} dias diferentes?",
             f"SELECT l.numero FROM alertas a JOIN linhas l ON l.id = a.linha_id WHERE a.tipo = 'CRITICO' GROUP BY l.id HAVING COUNT(DISTINCT date(a.criado_em)) > {k} ORDER BY l.numero", "")
            for k in (5, 8, 10, 15, 20)]


# ================================================================== LIMITE (recusas)
def _recusas(topicos, formatos, n_ent=None):
    out = []
    for topico, motivo in topicos:
        for f in formatos:
            out.append((f.format(t=topico), None, motivo))
    return out


@familia("r_sem_dado", "limite", 40)
def _(P, rng):
    T = [("o consumo de combustível", "O banco não tem dados de consumo de combustível."),
         ("o custo de manutenção", "O banco não tem dados de custos de manutenção."),
         ("o número de reclamações de passageiros", "O banco não tem registros de reclamações."),
         ("a nota de satisfação dos passageiros", "O banco não tem pesquisas de satisfação."),
         ("o horário programado oficial das viagens", "O banco só tem as viagens realizadas, não a grade de horários programados."),
         ("a quilometragem rodada", "O banco não tem quilometragem."),
         ("o ano de fabricação do ônibus", "O banco não registra o ano de fabricação dos ônibus."),
         ("os acidentes ocorridos", "O banco não tem registros de acidentes."),
         ("as câmeras de segurança", "O banco não tem dados de câmeras."),
         ("o preço da passagem", "O banco não tem informações de tarifa."),
         ("o número de ônibus com ar-condicionado", "O banco não registra equipamentos dos ônibus."),
         ("o nome do fabricante da carroceria", "O banco só tem o modelo do ônibus, não o fabricante da carroceria.")]
    F = ["Qual {t}?".replace("Qual", "Me diga"), "Você sabe {t}?", "Quero saber {t} da linha {L}.", "Mostre {t} do mês."]
    out = []
    for topico, motivo in T:
        for f in F:
            out.append((f.format(t=topico, L=rng.choice(P["linhas"])).replace("Me diga  ", "Me diga "), None, motivo))
    return out


@familia("r_sem_dado_proximo", "limite", 12, proximo=("L02", "L03", "L04"))
def _(P, rng):
    T = [(f"Onde está o ônibus {rng.choice(P['placas'])} agora?", "O banco não tem posição em tempo real, só leituras por parada."),
         ("Qual a velocidade atual do ônibus " + rng.choice(P["placas"]) + "?", "O banco não tem GPS nem velocidade."),
         ("Quantos passageiros usaram bilhete único hoje?", "O banco não tem dados de bilhetagem ou pagamento."),
         ("Qual o valor arrecadado pela linha " + rng.choice(P["linhas"]) + "?", "O banco não tem dados de arrecadação."),
         ("Quem dirige a linha " + rng.choice(P["linhas"]) + " de manhã?", "O banco não tem dados de motoristas."),
         ("Qual o nome do cobrador da viagem 250?", "O banco não tem dados de funcionários.")]
    return [(q, None, m) for q, m in T]


@familia("r_previsao", "limite", 8, proximo=("L05",))
def _(P, rng):
    T = ["Quanto estará lotada a linha {L} na próxima segunda?", "Vai chover amanhã durante o horário de pico?",
         "Quantos alertas críticos teremos na semana que vem?", "Qual a lotação prevista da linha {L} para as 18h de hoje?"]
    return [(t.format(L=rng.choice(P["linhas"])), None,
             "O banco só tem histórico; não faz previsões. Posso consultar a média histórica, que não é uma previsão.") for t in T]


@familia("r_escrita", "limite", 14)
def _(P, rng):
    T = ["Atualize o status do ônibus {p} para manutenção.", "Insira uma nova linha chamada 999 no banco.",
         "Altere a capacidade do ônibus {p} para 100 passageiros.", "Cadastre uma nova parada em Serra.",
         "Corrija o nome da linha {L} para 'Linha Teste'.", "Marque todos os alertas da linha {L} como resolvidos.",
         "Renomeie a parada {n} para 'Ponto Central'."]
    return [(t.format(p=rng.choice(P["placas"]), L=rng.choice(P["linhas"]), n=rng.choice(P["paradas"])), None,
             "O assistente é somente leitura e não altera dados do banco.") for t in T for _ in range(2)]


@familia("r_escrita_apaga", "limite", 8, proximo=("L06",))
def _(P, rng):
    T = ["Exclua os alertas da linha {L}.", "Delete as viagens canceladas.", "Remova todos os registros de ocupação antigos.",
         "Limpe a tabela de alertas."]
    return [(t.format(L=rng.choice(P["linhas"])), None, "O assistente é somente leitura e não apaga dados.") for t in T]


@familia("r_fora_dominio", "limite", 8)
def _(P, rng):
    T = ["Qual a capital da França?", "Me conte uma piada.", "Escreva um poema sobre ônibus.", "Quanto é 15 vezes 12?",
         "Quem ganhou a última Copa do Mundo?", "Como faço um bolo de cenoura?", "Qual o melhor time do Espírito Santo?",
         "Traduza 'bom dia' para inglês."]
    return [(t, None, "A pergunta não é sobre os dados do InfoFrota.") for t in T]


@familia("r_sem_periodo", "limite", 6, proximo=("L01",), vazio_ok=True)
def _(P, rng):
    out = []
    for L in rng.sample(P["linhas"], 6):
        d = rng.choice(["2026-08-12", "2026-09-20", "2026-12-05"])
        out.append((f"Qual a lotação média da linha {L} em {br(d)}?",
                    f"SELECT ROUND(AVG(d.media_percentual), 1) FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id WHERE l.numero = '{L}' AND d.data = '{d}'", ""))
    return out


# ------------------------------------------------------------------ anti-vazamento
STOP = set("de da do das dos a o as os e em no na nos nas por para com que qual quais quantos quantas um uma é foi são".split())


def tokens(texto, nomes):
    t = texto.lower()
    for nm in sorted(nomes, key=len, reverse=True):
        t = t.replace(nm.lower(), " ENT ")
    t = re.sub(r"\d+([/.,:]\d+)*", " N ", t)
    t = re.sub(r"[^\wà-ÿ]+", " ", t)
    return {w for w in t.split() if w not in STOP}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def esqueleto(sql):
    s = re.sub(r"'[^']*'", "?", sql.lower())
    s = re.sub(r"\b\d+(\.\d+)?\b", "?", s)
    return re.sub(r"\s+", " ", s).strip()


def montar(args):
    rng = random.Random(args.seed)
    P = carregar_pools(args.db)
    teste = json.loads(EVAL.read_text(encoding="utf-8"))
    nomes = P["todos_nomes"]
    tok_teste = [(q["id"], tokens(q["pergunta"], nomes)) for q in teste]
    esq_teste = {esqueleto(q["sql"]): q["id"] for q in teste if q.get("sql")}

    descartes = collections.Counter()
    itens, vistos = [], set()
    for fam in FAMILIAS:
        if fam["proximo"] and not args.incluir_proximas:
            descartes["familia_proxima_excluida"] += 1
            continue
        cands = fam["fn"](P, rng)
        rng.shuffle(cands)
        aceitos = 0
        for pergunta, sql, motivo in cands:
            if aceitos >= fam["n"]:
                break
            chave = re.sub(r"\s+", " ", pergunta.lower())
            if chave in vistos:
                descartes["duplicada"] += 1
                continue
            tk = tokens(pergunta, nomes)
            prox = max(((jaccard(tk, t), i) for i, t in tok_teste), default=(0, ""))
            if prox[0] >= args.limiar_similaridade:
                descartes[f"parecida_com_teste:{prox[1]}"] += 1
                continue
            if sql:
                if esqueleto(sql) in esq_teste:
                    descartes[f"esqueleto_igual_ao_teste:{esq_teste[esqueleto(sql)]}"] += 1
                    continue
                try:
                    res = executar(sql, args.db, max_linhas=500)
                except (SQLBloqueado, SQLErro) as e:
                    raise SystemExit(f"SQL inválido na família {fam['nome']}: {e}\n{sql}")
                vazio = not res.linhas or all(v is None for r in res.linhas for v in r)
                if vazio and not fam["vazio_ok"]:
                    descartes["resultado_vazio"] += 1
                    continue
            vistos.add(chave)
            aceitos += 1
            resposta = {"pode_responder": sql is not None, "sql": sql or "", "motivo": motivo}
            itens.append(dict(familia=fam["nome"], nivel=fam["nivel"], proximo=list(fam["proximo"]),
                              pergunta=pergunta, **resposta,
                              similaridade_max_teste=round(prox[0], 3), mais_parecida_com=prox[1]))
    rng.shuffle(itens)
    return itens, descartes, P


def colunas_do_esquema(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cols = {}
    for nome, in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"):
        for c in con.execute(f"PRAGMA table_info({nome})"):
            cols.setdefault(c[1], []).append(nome)
    con.close()
    return cols


def relatorio(itens, descartes, args, n_train, n_val):
    por_fam = collections.Counter(i["familia"] for i in itens)
    por_nivel = collections.Counter(i["nivel"] for i in itens)
    sqls = " ".join(i["sql"] for i in itens)
    cols = colunas_do_esquema(args.db)
    sem = sorted(c for c in cols if not re.search(rf"\b{re.escape(c)}\b", sqls))
    proximos = sorted(itens, key=lambda i: -i["similaridade_max_teste"])[:8]
    sims = [i["similaridade_max_teste"] for i in itens]
    L = [f"# Conjunto de treino do LoRA\n",
         f"Modo: **{'COM' if args.incluir_proximas else 'SEM'} famílias próximas do teste** · prompt `{args.prompt}`{' + RAG' if args.rag else ''} · semente {args.seed}\n",
         f"Total: **{len(itens)}** exemplos (treino {n_train}, validação {n_val}) · "
         f"recusas: {sum(1 for i in itens if not i['pode_responder'])} "
         f"({sum(1 for i in itens if not i['pode_responder']) / len(itens):.0%})\n",
         "| Nível | Exemplos |", "|---|---|"]
    L += [f"| {k} | {por_nivel[k]} |" for k in ("facil", "medio", "dificil", "limite")]
    L += ["\n## Anti-vazamento (contra as 56 perguntas de teste)\n",
          f"- Pergunta de teste idêntica ou parecida (Jaccard ≥ {args.limiar_similaridade}, com entidades e números mascarados): descartadas.",
          "- SQL com o mesmo esqueleto de um SQL de referência: descartados.",
          f"- Similaridade máxima com qualquer pergunta de teste entre os exemplos mantidos: **{max(sims):.2f}** (média {sum(sims) / len(sims):.2f}).",
          "- Famílias próximas em conceito a perguntas de teste: " + ("**incluídas** (comparação)." if args.incluir_proximas else "**excluídas**."),
          "\nDescartes:\n"] + [f"- `{k}`: {v}" for k, v in sorted(descartes.items())]
    L += ["\nMais parecidos com o teste (para revisão manual):\n"]
    L += [f"- {i['similaridade_max_teste']:.2f} · treino: «{i['pergunta']}» · teste {i['mais_parecida_com']}" for i in proximos]
    L += [f"\n## Cobertura de colunas\n",
          f"{len(cols) - len(sem)}/{len(cols)} nomes de coluna aparecem em algum SQL de treino."
          + (f" Sem cobertura: {', '.join(sem)}." if sem else ""),
          "\n## Exemplos por família\n", "| Família | Exemplos |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(por_fam.items())]
    L += ["\n## Limites\n",
          "- Perguntas geradas por modelos de frase (3 a 4 formulações por família): a variedade de linguagem é menor que a de usuários reais.",
          "- A validação usa a mesma distribuição do treino: serve para acompanhar a perda, não para medir generalização. Quem mede é a avaliação de 56 perguntas."]
    return "\n".join(L) + "\n"


def exportar(itens, args):
    OUT.mkdir(exist_ok=True)
    modo = prompts.MODOS[args.prompt]
    system = prompts.montar_system(args.db, compacto=modo)
    indice = None
    if args.rag:   # o contexto de cada exemplo é recuperado da pergunta dele, como na inferência
        from infofrota_ai.rag import Indice
        indice = Indice(args.db)
    n_val = max(1, round(len(itens) * args.val))
    val, train = itens[:n_val], itens[n_val:]
    (OUT / "dataset.jsonl").write_text(
        "\n".join(json.dumps(i, ensure_ascii=False) for i in itens) + "\n", encoding="utf-8")
    for nome, parte in (("train_chat.jsonl", train), ("val_chat.jsonl", val)):
        linhas = []
        for i in parte:
            resp = {"pode_responder": i["pode_responder"], "sql": i["sql"], "motivo": i["motivo"]}
            linhas.append(json.dumps({"messages": [
                {"role": "system", "content": system if not indice else prompts.montar_system(
                    args.db, compacto=modo, contexto=indice.contexto(i["pergunta"]))},
                {"role": "user", "content": i["pergunta"]},
                {"role": "assistant", "content": json.dumps(resp, ensure_ascii=False)}]}, ensure_ascii=False))
        (OUT / nome).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (OUT / "REPORT.md").write_text(relatorio(itens, args.descartes, args, len(train), len(val)), encoding="utf-8")
    return len(train), len(val)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--prompt", choices=list(prompts.MODOS), default="ultra")
    ap.add_argument("--incluir-proximas", action="store_true")
    ap.add_argument("--limiar-similaridade", type=float, default=0.8)
    ap.add_argument("--val", type=float, default=0.08)
    ap.add_argument("--rag", action="store_true", help="inclui o contexto recuperado (RAG de esquema) no system de cada exemplo")
    ap.add_argument("--saida", default="training", help="pasta de saída dentro do repo")
    args = ap.parse_args()
    global OUT
    OUT = ROOT / args.saida
    itens, descartes, _ = montar(args)
    args.descartes = descartes
    n_train, n_val = exportar(itens, args)
    print(f"{len(itens)} exemplos (treino {n_train}, validação {n_val}) -> {OUT}")
    print("descartes:", dict(descartes))


if __name__ == "__main__":
    main()
