#!/usr/bin/env python3
"""Gerador de dados sintéticos do InfoFrota AI.

Linhas e rótulos: reais (data/linhas_ceturbes.csv, CETURBES).
Frota, viagens, lotação, clima e alertas: SINTÉTICOS, gerados com semente fixa.

Uso:
    python scripts/generate_data.py            # gera data/infofrota.db
    python scripts/generate_data.py --dias 45 --seed 7
"""
import argparse
import csv
import math
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_LINHAS = ROOT / "data" / "linhas_ceturbes.csv"
SCHEMA = ROOT / "db" / "schema.sql"
DB_PATH = ROOT / "data" / "infofrota.db"

FERIADOS = {
    date(2026, 10, 12): "Nossa Senhora Aparecida",
    date(2026, 11, 2): "Finados",
}
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

# (codigo, nome, lat, lon, municipio, aproximada)
# As 10 primeiras vêm do schema original; as demais têm coordenadas aproximadas.
PARADAS = [
    ("VV-001", "Terminal Ibes", -20.3647, -40.3614, "Vila Velha", 0),
    ("VV-002", "Praia de Itaparica", -20.3521, -40.3598, "Vila Velha", 0),
    ("VV-003", "Shopping Vila Velha", -20.3489, -40.3545, "Vila Velha", 0),
    ("VV-004", "Terminal Vila Velha", -20.3395, -40.3477, "Vila Velha", 0),
    ("VT-001", "Praça Coelho e Campos", -20.3164, -40.3322, "Vitória", 0),
    ("VT-002", "Terminal Jardim América", -20.2988, -40.3108, "Cariacica", 0),
    ("VT-003", "Reta da Penha", -20.2812, -40.2983, "Vitória", 0),
    ("SE-001", "Terminal Laranjeiras", -20.2543, -40.3201, "Serra", 0),
    ("CA-001", "Terminal Campo Grande", -20.2934, -40.3876, "Cariacica", 0),
    ("CA-002", "Terminal Itacibá", -20.3012, -40.4012, "Cariacica", 0),
    ("SE-002", "Terminal Carapina", -20.2398, -40.2745, "Serra", 1),
    ("SE-003", "Terminal Jacaraípe", -20.1547, -40.2051, "Serra", 1),
    ("SE-004", "Serra Sede", -20.1285, -40.3074, "Serra", 1),
    ("VT-004", "Terceira Ponte", -20.3231, -40.3046, "Vila Velha", 1),
    ("VT-005", "Jardim Camburi", -20.2721, -40.2689, "Vitória", 1),
    ("VV-005", "Terminal Itaparica", -20.3575, -40.3620, "Vila Velha", 1),
    ("VV-006", "Terminal São Torquato", -20.3420, -40.3250, "Vila Velha", 1),
    ("VI-001", "Viana Centro", -20.3900, -40.4960, "Viana", 1),
    ("VI-002", "Vila Bethânia", -20.4000, -40.4850, "Viana", 1),
    ("VI-003", "Marcílio de Noronha", -20.3770, -40.5010, "Viana", 1),
]
# Código curto usado nas rotas abaixo
P = {
    "IBES": "VV-001", "VVELHA": "VV-004", "SHOPVV": "VV-003", "ITAPARICA": "VV-005",
    "COELHO": "VT-001", "JARDIMAM": "VT-002", "RETA": "VT-003", "LARANJ": "SE-001",
    "CGRANDE": "CA-001", "ITACIBA": "CA-002", "CARAPINA": "SE-002", "JACARAIPE": "SE-003",
    "SERRA": "SE-004", "PONTE": "VT-004", "CAMBURI": "VT-005", "STORQUATO": "VV-006",
    "VIANA": "VI-001", "BETHANIA": "VI-002", "MARCILIO": "VI-003",
}

# numero -> (ocupação média no pico em %, nº de ônibus, paradas em ordem de 'ida')
LINHAS_MONITORADAS = {
    "500": (72, 4, ["VVELHA", "PONTE", "JARDIMAM", "CGRANDE", "ITACIBA"]),
    "501": (78, 5, ["JACARAIPE", "CARAPINA", "RETA", "PONTE", "VVELHA", "ITAPARICA"]),
    "505": (80, 5, ["LARANJ", "CARAPINA", "CAMBURI", "JARDIMAM", "ITACIBA"]),
    "508": (85, 5, ["LARANJ", "CARAPINA", "CAMBURI", "PONTE", "VVELHA", "ITAPARICA"]),
    "510": (70, 4, ["CARAPINA", "RETA", "PONTE", "VVELHA"]),
    "514": (62, 3, ["IBES", "SHOPVV", "VVELHA", "PONTE"]),
    "531": (88, 5, ["CGRANDE", "JARDIMAM", "COELHO", "PONTE", "VVELHA"]),
    "536": (82, 4, ["CGRANDE", "PONTE", "VVELHA"]),
    "559": (66, 3, ["LARANJ", "CARAPINA", "RETA", "STORQUATO"]),
    "562": (92, 6, ["LARANJ", "CARAPINA", "RETA", "JARDIMAM", "CGRANDE"]),
    "563": (40, 3, ["CARAPINA", "RETA", "PONTE", "VVELHA"]),
    "591": (90, 5, ["SERRA", "CARAPINA", "RETA", "JARDIMAM", "CGRANDE"]),
    "860": (60, 3, ["JACARAIPE", "SERRA", "LARANJ"]),
    "875": (55, 3, ["JACARAIPE", "SERRA", "LARANJ"]),
    "901": (75, 4, ["VIANA", "BETHANIA", "CGRANDE"]),
    "912": (68, 3, ["MARCILIO", "BETHANIA", "CGRANDE"]),
}

MODELOS = [("Volvo B270F", 80), ("Mercedes-Benz O-500", 90), ("Caio Apache", 80),
           ("Marcopolo Torino", 80), ("Volvo B340M articulado", 110)]

# Fator de demanda por hora de partida (pico = 1.0)
CURVA = [0.30, 0.28, 0.25, 0.25, 0.30, 0.45, 0.85, 1.00, 0.90, 0.60, 0.50, 0.50,
         0.60, 0.55, 0.50, 0.55, 0.75, 1.00, 0.95, 0.75, 0.55, 0.45, 0.40, 0.35]

PRECAUCOES = ["Ônibus de reforço despachado", "Viagem extra programada",
              "Fiscal acionado no ponto", "Intervalo reduzido na linha"]


def tipo_linha(rotulo):
    r = rotulo.upper()
    if "NOTURNO" in r:
        return "noturno"
    if "EXPRESSO" in r:
        return "expresso"
    if "CIRCULAR" in r:
        return "circular"
    return "convencional"


def gerar_clima(rng, dias):
    """(data, hora) -> (chuva_mm, temperatura_c, condicao)."""
    clima = {}
    for d in dias:
        chove = rng.random() < 0.35
        ini = rng.randint(0, 22)
        dur = rng.randint(1, 5)
        escala = rng.expovariate(1 / 3.0) + 0.5
        offset_t = rng.gauss(0, 1.5)
        for h in range(24):
            mm = 0.0
            if chove and ini <= h < ini + dur:
                mm = round(max(0.1, rng.gauss(escala, escala * 0.4)), 1)
            temp = round(24 + 5 * math.sin((h - 9) * math.pi / 12) + offset_t
                         - (2 if mm else 0) + rng.gauss(0, 0.4), 1)
            cond = ("chuva_forte" if mm >= 5 else "chuva" if mm >= 1
                    else "garoa" if mm > 0 else "seco")
            clima[(d, h)] = (mm, temp, cond)
    return clima


def horarios_partida(rng, tipo_dia, noturno, sentido):
    """Minutos desde 00:00 em que as viagens saem."""
    off = 0 if sentido == "ida" else 8
    if noturno:
        base = [22 * 60, 23 * 60] + [h * 60 for h in range(0, 5)]
        return [m + (0 if sentido == "ida" else 30) for m in base]
    saidas, t = [], 5 * 60 + off
    while t <= 23 * 60 + 30:
        h = t // 60
        if tipo_dia == "util" and (6 <= h < 9 or 16 <= h < 19):
            passo = 20
        elif tipo_dia == "util":
            passo = 45
        else:
            passo = 40
        saidas.append(max(0, t + rng.randint(-3, 3)))
        t += passo
    return saidas


def simular_viagem(rng, n, cap, target, hora, sentido, tipo_dia, mm):
    """Retorna lista de ocupações (inteiros) por parada; a última é 0."""
    fh = CURVA[hora]
    manha, tarde = 5 <= hora < 10, 16 <= hora < 20
    if sentido == "ida":
        fd = 1.0 if manha else 0.65 if tarde else 0.85
    else:
        fd = 1.0 if tarde else 0.65 if manha else 0.85
    fdia = {"util": 1.0, "sabado": 0.6, "domingo": 0.4, "feriado": 0.45}[tipo_dia]
    frain = 1 + min(mm, 6) / 6 * 0.25
    pico = target / 100 * cap * fh * fd * fdia * frain * rng.lognormvariate(0, 0.14)
    occ = []
    for i in range(n):
        if i == n - 1:
            occ.append(0)
            continue
        x = i / (n - 1)
        forma = 0.45 + 0.55 * 4 * x * (1 - x)
        v = pico * forma * (1 + rng.gauss(0, 0.06))
        occ.append(int(max(0, min(round(v), round(cap * 1.1)))))
    return occ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--fim", default="2026-11-03", help="último dia gerado (AAAA-MM-DD)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    fim = date.fromisoformat(args.fim)
    dias = [fim - timedelta(days=i) for i in range(args.dias - 1, -1, -1)]

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    cur = con.cursor()

    # ---- linhas (reais) -------------------------------------------------
    vistos, linha_id = {}, {}
    with open(CSV_LINHAS, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            num = row["Linha"].strip()
            if num in vistos:
                print(f"  linha duplicada no CSV, mantida a primeira: {num}")
                continue
            rot = " ".join(row["Rotulo"].split())
            vistos[num] = rot
    for num, rot in vistos.items():
        cur.execute(
            "INSERT INTO linhas (numero, nome, tipo, capacidade_padrao, monitorada, ativa)"
            " VALUES (?,?,?,?,?,1)",
            (num, rot, tipo_linha(rot), 80, 1 if num in LINHAS_MONITORADAS else 0))
        linha_id[num] = cur.lastrowid
    ausentes = [n for n in LINHAS_MONITORADAS if n not in linha_id]
    assert not ausentes, f"linhas monitoradas fora do CSV: {ausentes}"

    # ---- paradas ---------------------------------------------------------
    parada_id = {}
    for cod, nome, lat, lon, mun, aprox in PARADAS:
        cur.execute(
            "INSERT INTO paradas (nome, codigo, latitude, longitude, municipio,"
            " coordenadas_aproximadas) VALUES (?,?,?,?,?,?)",
            (nome, cod, lat, lon, mun, aprox))
        parada_id[cod] = cur.lastrowid

    # ---- ônibus e linha_paradas -----------------------------------------
    frota, rotas, seq_placa = {}, {}, 1
    for num, (target, n_bus, stops) in LINHAS_MONITORADAS.items():
        lid = linha_id[num]
        ids = [parada_id[P[s]] for s in stops]
        rotas[num] = ids
        for sentido, seq in (("ida", ids), ("volta", ids[::-1])):
            for ordem, pid in enumerate(seq, 1):
                cur.execute(
                    "INSERT INTO linha_paradas (linha_id, parada_id, ordem, sentido)"
                    " VALUES (?,?,?,?)", (lid, pid, ordem, sentido))
        frota[num] = []
        for _ in range(n_bus + (1 if rng.random() < 0.25 else 0)):
            modelo, cap = rng.choice(MODELOS)
            status = "ativo" if len(frota[num]) < n_bus else "manutencao"
            cur.execute(
                "INSERT INTO onibus (placa, modelo, capacidade, linha_padrao_id, status)"
                " VALUES (?,?,?,?,?)",
                (f"SIN-{seq_placa:04d}", modelo, cap, lid, status))
            seq_placa += 1
            if status == "ativo":
                frota[num].append((cur.lastrowid, cap))

    # ---- calendário e clima ---------------------------------------------
    clima = gerar_clima(rng, dias)
    for d in dias:
        if d in FERIADOS:
            tipo = "feriado"
        else:
            tipo = ["util"] * 5 + ["sabado", "domingo"]
            tipo = tipo[d.weekday()]
        cur.execute("INSERT INTO calendario VALUES (?,?,?,?)",
                    (d.isoformat(), DIAS_SEMANA[d.weekday()], tipo, FERIADOS.get(d)))
        for h in range(24):
            mm, temp, cond = clima[(d, h)]
            cur.execute("INSERT INTO clima_hora VALUES (?,?,?,?)",
                        (f"{d.isoformat()} {h:02d}:00:00", mm, temp, cond))
    tipo_dia_de = {r[0]: r[1] for r in cur.execute("SELECT data, tipo_dia FROM calendario")}

    # ---- viagens, leituras e alertas ------------------------------------
    viagens, regs, alertas = [], [], []
    vid = rid = aid = 0
    for d in dias:
        tdia = tipo_dia_de[d.isoformat()]
        for num, (target, _, _) in LINHAS_MONITORADAS.items():
            lid = linha_id[num]
            noturno = tipo_linha(vistos[num]) == "noturno"
            rodizio = 0
            for sentido in ("ida", "volta"):
                paradas = rotas[num] if sentido == "ida" else rotas[num][::-1]
                n = len(paradas)
                for minuto in horarios_partida(rng, tdia, noturno, sentido):
                    onibus, cap = frota[num][rodizio % len(frota[num])]
                    rodizio += 1
                    inicio = datetime(d.year, d.month, d.day) + timedelta(minutes=minuto)
                    vid += 1
                    if rng.random() < 0.015:
                        viagens.append((vid, onibus, lid, sentido,
                                        inicio.strftime("%Y-%m-%d %H:%M:%S"), None, "cancelada"))
                        continue
                    mm = clima[(d, inicio.hour)][0]
                    occ = simular_viagem(rng, n, cap, target, inicio.hour, sentido, tdia, mm)
                    perna = rng.uniform(7, 13) * (1.1 if mm > 0 else 1.0)
                    t, anterior, aberto = inicio, 0, []
                    for i, pid in enumerate(paradas):
                        if i:
                            t += timedelta(minutes=perna * rng.uniform(0.9, 1.1))
                        o = occ[i]
                        des_base = round(anterior * rng.uniform(0.08, 0.30))
                        des = min(anterior, max(des_base, anterior - o))
                        emb = o - anterior + des
                        pct = round(o / cap * 100, 2)
                        rid += 1
                        momento = t.strftime("%Y-%m-%d %H:%M:%S")
                        regs.append((rid, vid, pid, momento, emb, des, o, pct))
                        # mesma regra do trigger original
                        if pct >= 90:
                            if not any(a[4] == "CRITICO" for a in aberto):
                                aid += 1
                                prec = rng.random() < 0.3
                                a = [aid, vid, lid, pid, "CRITICO", pct,
                                     f"Superlotação detectada – {pct}% de ocupação", momento,
                                     0, None, 1 if prec else 0,
                                     rng.choice(PRECAUCOES) if prec else None]
                                aberto.append(a)
                                alertas.append(a)
                        elif pct >= 75:
                            if not aberto:
                                aid += 1
                                a = [aid, vid, lid, pid, "ATENCAO", pct,
                                     f"Aproximando-se da capacidade crítica – {pct}% de ocupação",
                                     momento, 0, None, 0, None]
                                aberto.append(a)
                                alertas.append(a)
                        else:
                            for a in aberto:
                                a[8], a[9] = 1, momento
                            aberto = []
                        anterior = o
                    viagens.append((vid, onibus, lid, sentido,
                                    inicio.strftime("%Y-%m-%d %H:%M:%S"),
                                    t.strftime("%Y-%m-%d %H:%M:%S"), "concluida"))

    cur.executemany("INSERT INTO viagens VALUES (?,?,?,?,?,?,?)", viagens)
    cur.executemany("INSERT INTO registros_ocupacao VALUES (?,?,?,?,?,?,?,?)", regs)
    cur.executemany("INSERT INTO alertas VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", alertas)

    # ---- agregações (equivalem às procedures sp_agregar_hora/dia) --------
    hora_expr = "strftime('%Y-%m-%d %H:00:00', r.momento)"
    for parada_sel, grupo in (("NULL", "v.linha_id, " + hora_expr),
                              ("r.parada_id", "v.linha_id, r.parada_id, " + hora_expr)):
        cur.execute(f"""
            INSERT INTO resumos_hora (linha_id, parada_id, data_hora, total_registros,
                media_percentual, max_percentual, min_percentual, total_embarcaram,
                total_desembarcaram, leituras_acima_75)
            SELECT v.linha_id, {parada_sel}, {hora_expr}, COUNT(*),
                   ROUND(AVG(r.percentual), 2), MAX(r.percentual), MIN(r.percentual),
                   SUM(r.embarcaram), SUM(r.desembarcaram), SUM(r.percentual >= 75)
            FROM registros_ocupacao r JOIN viagens v ON v.id = r.viagem_id
            GROUP BY {grupo}""")
    # viagens que passam da meia-noite do último dia ficam fora dos resumos
    cur.execute("DELETE FROM resumos_hora WHERE date(data_hora) > ?", (fim.isoformat(),))
    cur.execute("""CREATE TEMP VIEW h AS
        SELECT linha_id, date(data_hora) AS d, data_hora, media_percentual,
               max_percentual, total_registros, total_embarcaram, total_desembarcaram
        FROM resumos_hora WHERE parada_id IS NULL""")
    cur.execute("""
        INSERT INTO resumos_dia (linha_id, data, media_percentual, max_percentual, hora_pico,
            total_viagens, total_alertas_atencao, total_alertas_critico,
            total_embarcaram, total_desembarcaram)
        SELECT h.linha_id, h.d,
               ROUND(SUM(h.media_percentual * h.total_registros) / SUM(h.total_registros), 2),
               MAX(h.max_percentual),
               (SELECT strftime('%H:%M:%S', p.data_hora) FROM h p
                 WHERE p.linha_id = h.linha_id AND p.d = h.d
                 ORDER BY p.media_percentual DESC, p.data_hora LIMIT 1),
               (SELECT COUNT(*) FROM viagens v WHERE v.linha_id = h.linha_id
                  AND date(v.data_inicio) = h.d AND v.status = 'concluida'),
               (SELECT COUNT(*) FROM alertas a WHERE a.linha_id = h.linha_id
                  AND date(a.criado_em) = h.d AND a.tipo = 'ATENCAO'),
               (SELECT COUNT(*) FROM alertas a WHERE a.linha_id = h.linha_id
                  AND date(a.criado_em) = h.d AND a.tipo = 'CRITICO'),
               SUM(h.total_embarcaram), SUM(h.total_desembarcaram)
        FROM h GROUP BY h.linha_id, h.d""")
    cur.execute("DROP VIEW h")

    con.commit()
    for t in ("linhas", "onibus", "paradas", "linha_paradas", "viagens",
              "registros_ocupacao", "alertas", "resumos_hora", "resumos_dia",
              "clima_hora", "calendario"):
        print(f"{t:20s} {cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>8}")
    con.close()
    print(f"\nBanco gerado em {DB_PATH}")


if __name__ == "__main__":
    main()
