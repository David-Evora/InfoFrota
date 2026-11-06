"""RAG de esquema para o Text-to-SQL.

Indexa, a partir do próprio banco, (1) tabelas/views com colunas, descrição e chaves,
(2) valores categóricos válidos de cada coluna e (3) regras do domínio. Para cada
pergunta, recupera por BM25 o que é relevante e devolve um bloco de contexto que
entra no system prompt (opção --rag).

NÃO lê evaluation/questions.json: o índice só usa o banco e as descrições abaixo.
Uso: python -m infofrota_ai.rag "Quais ônibus estão em manutenção?"
     python -m infofrota_ai.rag --recall      # cobertura do contexto sobre as perguntas de teste
"""
import math
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass

from .db import DB_PATH

DESCRICOES = {
    "linhas": "uma linha de ônibus da CETURBES; só as monitoradas têm viagens, leituras e alertas",
    "onibus": "um veículo da frota, com placa, modelo, capacidade, linha padrão e status",
    "paradas": "um ponto de parada, com município e coordenadas",
    "linha_paradas": "ordem das paradas em cada linha e sentido (itinerário)",
    "viagens": "cada saída de um ônibus em uma linha; início, fim, sentido e status",
    "registros_ocupacao": "leitura bruta do sensor por parada em cada viagem: embarque, desembarque, ocupação e percentual",
    "alertas": "alertas de lotação gerados das leituras, com tipo, ações de precaução e resolução",
    "resumos_hora": "agregado de lotação por linha (ou parada) e por hora",
    "resumos_dia": "agregado de lotação por linha e por dia: média, máximo, hora de pico, embarques, alertas",
    "clima_hora": "chuva, temperatura e condição do tempo por hora",
    "calendario": "tipo de cada dia (útil, sábado, domingo, feriado), dia da semana e nome do feriado",
    "v_ocupacao_atual": "view: última leitura de cada viagem em andamento",
    "v_alertas_abertos": "view: alertas ainda não resolvidos",
    "v_relatorio_linha_hora": "view: lotação por linha e hora, com número e nome da linha, data e hora",
    "v_relatorio_parada_problema": "view: paradas com maior ocupação média nos últimos 30 dias",
    "v_lotacao_clima": "view: lotação por linha e hora ligada ao clima daquela hora (chuva_mm, condição)",
}

# (tabela, coluna) cujos valores distintos viram documentos de "valores válidos"
CATEGORICAS = [
    ("onibus", "status"), ("alertas", "tipo"), ("alertas", "precaucao_descricao"),
    ("viagens", "status"), ("viagens", "sentido"), ("linha_paradas", "sentido"),
    ("calendario", "tipo_dia"), ("calendario", "dia_semana"), ("calendario", "feriado_nome"),
    ("clima_hora", "condicao"), ("linhas", "tipo"), ("paradas", "municipio"),
]

REGRAS = [
    "ATENCAO é lotação de 75% a menos de 90%; CRITICO é 90% ou mais. percentual pode passar de 100.",
    "Datas e horas são TEXT 'AAAA-MM-DD HH:MM:SS'. Para o dia use date(coluna); para a hora, strftime('%H', coluna).",
    "linhas.numero é TEXT: compare com aspas ('562'). Só as linhas com monitorada = 1 têm dados de lotação.",
    "resumos_hora com parada_id NULL é o resumo da linha inteira; com parada_id é da parada.",
    "Por linha ou por dia use resumos_dia; por hora use resumos_hora; por parada, município ou viagem use registros_ocupacao.",
    "Para saber o tipo de dia (útil, sábado, domingo, feriado) ligue a data ao calendario: calendario.data = date(...).",
    "Chuva: chuva_mm > 0 em clima_hora ou v_lotacao_clima. Para contar dias use COUNT(DISTINCT date(data_hora)).",
    "Viagens canceladas não têm leituras nem data_fim. A duração da viagem é julianday(data_fim) - julianday(data_inicio).",
    "A linha de uma leitura vem de viagens (registros_ocupacao.viagem_id -> viagens.linha_id), e o número da linha de linhas.numero.",
    "Ordem das paradas de uma linha: linha_paradas.ordem, filtrando linha_id e sentido.",
]

STOP = set("""de da do das dos a o as os em no na nos nas por para com que qual quais quantos quantas
e ou um uma uns umas foi foram tem tem ser sao e ao aos ha mais menos cada entre sobre se mas
me diga mostre liste quero saber houve teve tiveram""".split())

SINONIMOS = {  # stem -> termos de índice relacionados
    "lotacao": ["ocupacao", "percentual"], "ocupacao": ["percentual"],
    "passageiro": ["embarcaram", "desembarcaram", "ocupacao"],
    "embarque": ["embarcaram"], "embarcado": ["embarcaram"], "desembarque": ["desembarcaram"],
    "pico": ["hora", "pico"], "chuva": ["chuva_mm", "clima", "condicao"], "choveu": ["chuva", "clima"],
    "clima": ["chuva_mm", "temperatura"], "temperatura": ["temperatura_c"],
    "feriado": ["feriado_nome", "calendario", "tipo_dia"], "util": ["tipo_dia", "calendario"],
    "sabado": ["tipo_dia", "calendario"], "domingo": ["tipo_dia", "calendario"],
    "semana": ["dia_semana", "calendario"], "precaucao": ["precaucao_descricao", "em_precaucao"],
    "manutencao": ["status", "onibus"], "ativo": ["status", "onibus"], "inativo": ["status"],
    "cancelada": ["status", "viagens"], "cancelado": ["status", "viagens"], "concluida": ["status"],
    "duracao": ["data_inicio", "data_fim", "julianday"], "ida": ["sentido"], "volta": ["sentido"],
    "critico": ["alertas", "tipo"], "atencao": ["alertas", "tipo"], "alerta": ["alertas"],
    "municipio": ["paradas"], "resolvido": ["resolvido_em"], "resolucao": ["resolvido_em", "criado_em"],
    "placa": ["onibus"], "veiculo": ["onibus"], "frota": ["onibus"], "capacidade": ["capacidade"],
    "itinerario": ["linha_paradas", "ordem"], "rota": ["linha_paradas", "ordem"],
}


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _stem(w):
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


def tokens(texto, expandir=False):
    t = _sem_acento(texto.lower())
    brutos = re.findall(r"[a-z0-9]+", t.replace("_", " ")) + re.findall(r"[a-z0-9_]+_[a-z0-9_]+", t)
    saida = []
    for w in brutos:
        if w in STOP or len(w) < 2:
            continue
        w = _stem(w)
        saida.append(w)
        if expandir:
            for s in SINONIMOS.get(w, []):
                saida += tokens(s)
    return saida


@dataclass
class Doc:
    tipo: str          # tabela | valores | regra
    id: str
    texto: str         # o que vai para o prompt
    indice: list       # tokens indexados


class Indice:
    def __init__(self, db_path=DB_PATH):
        self.docs = []
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            self._tabelas(con)
            self._valores(con)
        finally:
            con.close()
        for i, r in enumerate(REGRAS):
            self.docs.append(Doc("regra", f"regra{i}", r, tokens(r)))
        self.por_tipo = {t: [d for d in self.docs if d.tipo == t] for t in ("tabela", "valores", "regra")}
        self.idf = {t: self._idf(ds) for t, ds in self.por_tipo.items()}

    def _tabelas(self, con):
        objs = con.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table','view') "
                           "AND name NOT LIKE 'sqlite_%'").fetchall()
        for tipo, nome in objs:
            cols = [c[1] for c in con.execute(f"PRAGMA table_info({nome})")]
            fks = ([f"{nome}.{f[3]} -> {f[2]}.{f[4]}" for f in con.execute(f"PRAGMA foreign_key_list({nome})")]
                   if tipo == "table" else [])
            desc = DESCRICOES.get(nome, "")
            texto = f"- {nome}({', '.join(cols)}): {desc}" + (f". Chaves: {'; '.join(fks)}" if fks else "")
            self.docs.append(Doc("tabela", nome, texto, tokens(nome) * 3 + tokens(desc) + tokens(" ".join(cols))))

    def _valores(self, con):
        for tab, col in CATEGORICAS:
            vals = [r[0] for r in con.execute(
                f"SELECT DISTINCT {col} FROM {tab} WHERE {col} IS NOT NULL ORDER BY {col} LIMIT 40")]
            if not vals:
                continue
            lista = ", ".join(repr(str(v)) for v in vals)
            self.docs.append(Doc("valores", f"{tab}.{col}", f"- {tab}.{col}: {lista}",
                                 tokens(f"{tab} {col}") + tokens(" ".join(str(v) for v in vals))))

    @staticmethod
    def _idf(docs):
        n, df = len(docs), Counter()
        for d in docs:
            df.update(set(d.indice))
        return {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def buscar(self, pergunta, tipo, k):
        q = set(tokens(pergunta, expandir=True))
        docs, idf = self.por_tipo[tipo], self.idf[tipo]
        media = sum(len(d.indice) for d in docs) / len(docs)
        pontos = []
        for d in docs:
            tf, dl, s = Counter(d.indice), len(d.indice), 0.0
            for t in q:
                if t in tf:
                    s += idf.get(t, 0) * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * dl / media))
            if s > 0:
                pontos.append((s, d))
        pontos.sort(key=lambda x: -x[0])
        return [d for _, d in pontos[:k]]

    def recuperar(self, pergunta, k_tabelas=4, k_valores=5, k_regras=3):
        return {"tabelas": self.buscar(pergunta, "tabela", k_tabelas),
                "valores": self.buscar(pergunta, "valores", k_valores),
                "regras": self.buscar(pergunta, "regra", k_regras)}

    def contexto(self, pergunta, **kw):
        r = self.recuperar(pergunta, **kw)
        blocos = ["CONTEXTO RECUPERADO PARA ESTA PERGUNTA (use nomes e valores exatamente como aparecem)"]
        for titulo, chave in (("Tabelas relevantes", "tabelas"), ("Valores válidos", "valores"), ("Regras", "regras")):
            if r[chave]:
                blocos.append(f"{titulo}:\n" + "\n".join(d.texto if d.texto.startswith("-") else f"- {d.texto}"
                                                         for d in r[chave]))
        return "\n".join(blocos)


def recall_nas_perguntas(db_path=DB_PATH):
    """Mede, nas perguntas de teste, se o contexto traz as tabelas/views e os valores literais
    usados no SQL de referência. Só mede: o índice nunca usa essas perguntas."""
    import json
    from .evaluate import QUESTOES
    idx = Indice(db_path)
    nomes = {d.id for d in idx.por_tipo["tabela"]}
    todas = {v for d in idx.por_tipo["valores"] for v in re.findall(r"'([^']*)'", d.texto)}
    t_ok = t_tot = v_ok = v_tot = c_ok = c_tot = 0
    for q in json.loads(QUESTOES.read_text(encoding="utf-8")):
        if q["tipo"] == "fora_do_escopo":
            continue
        sql = q["sql"]
        usadas = {n for n in nomes if re.search(rf"\b{n}\b", sql)}
        lits = {v for v in re.findall(r"'([^']*)'", sql) if v in todas}
        r = idx.recuperar(q["pergunta"])
        ctx_tab = {d.id for d in r["tabelas"]}
        ctx_val = {v for d in r["valores"] for v in re.findall(r"'([^']*)'", d.texto)}
        t_tot += len(usadas); t_ok += len(usadas & ctx_tab)
        v_tot += len(lits); v_ok += len(lits & ctx_val)
        c_tot += 1; c_ok += usadas <= ctx_tab
    return {"tabelas": (t_ok, t_tot), "valores": (v_ok, v_tot), "perguntas_com_todas_as_tabelas": (c_ok, c_tot)}


def main():
    a = sys.argv[1:]
    if a[:1] == ["--recall"]:
        for k, (ok, tot) in recall_nas_perguntas().items():
            print(f"{k}: {ok}/{tot} ({ok / max(tot, 1):.0%})")
        return
    print(Indice().contexto(" ".join(a)))


if __name__ == "__main__":
    main()
