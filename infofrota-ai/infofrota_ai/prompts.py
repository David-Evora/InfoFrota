"""Montagem dos prompts. O esquema é lido do próprio banco (com os comentários
do DDL), então o prompt nunca fica desatualizado em relação ao schema."""
import json
import re
import sqlite3

from .db import DB_PATH, conectar

NOTA_DADOS = "Dados sintéticos de demonstração, não representam a operação real da CETURBES."
PROMPT_VERSAO = 2  # ver evaluation/CHANGELOG.md
MODOS = {"completo": False, "compacto": True, "ultra": "ultra"}  # nome da CLI -> argumento de montar_system

FORMATO_RESPOSTA = (
    'Responda SOMENTE com um objeto JSON, sem texto fora dele:\n'
    '{"pode_responder": true, "sql": "<uma única consulta SELECT em SQLite>", "motivo": ""}\n'
    'Se a pergunta não puder ser respondida com este banco, use '
    '{"pode_responder": false, "sql": "", "motivo": "<uma frase explicando por quê>"}.'
)

# Exemplos fixos. Não podem coincidir com perguntas do conjunto de avaliação
# (há um teste que garante isso).
EXEMPLOS = [
    ("Quantos ônibus da frota têm capacidade de 90 passageiros?",
     {"pode_responder": True,
      "sql": "SELECT COUNT(*) FROM onibus WHERE capacidade = 90", "motivo": ""}),
    ("Qual a lotação máxima registrada na linha 500?",
     {"pode_responder": True,
      "sql": "SELECT MAX(r.percentual) FROM registros_ocupacao r "
             "JOIN viagens v ON v.id = r.viagem_id JOIN linhas l ON l.id = v.linha_id "
             "WHERE l.numero = '500'", "motivo": ""}),
    ("Qual o telefone da empresa operadora da linha 505?",
     {"pode_responder": False, "sql": "",
      "motivo": "O banco não tem dados de contato das operadoras."}),
]


def _ddl(db_path) -> str:
    con = conectar(db_path)
    try:
        linhas = con.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name").fetchall()
    finally:
        con.close()
    texto = "\n\n".join(l[0] for l in linhas)
    return re.sub(r"\n\s*\n+", "\n", texto)


def _periodo(db_path):
    con = conectar(db_path)
    try:
        ini, fim = con.execute("SELECT MIN(data), MAX(data) FROM calendario").fetchone()
        n = con.execute("SELECT COUNT(*) FROM linhas WHERE monitorada = 1").fetchone()[0]
    finally:
        con.close()
    return ini, fim, n


def _esquema_compacto(db_path) -> str:
    """tabela(colunas) + chaves estrangeiras: ~5x menos tokens que o DDL completo.
    Usado no modo compacto, em que o modelo (com LoRA) já aprendeu o esquema."""
    # conexão só para metadados (código nosso, não SQL de modelo): somente leitura, sem authorizer
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        objetos = con.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name").fetchall()
        linhas, fks = [], []
        for tipo, nome in objetos:
            cols = [c[1] for c in con.execute(f"PRAGMA table_info({nome})")]
            linhas.append(f"{nome}({', '.join(cols)})" + (" [view]" if tipo == "view" else ""))
            if tipo == "table":
                fks += [f"{nome}.{f[3]} -> {f[2]}.{f[4]}" for f in con.execute(f"PRAGMA foreign_key_list({nome})")]
    finally:
        con.close()
    return "\n".join(linhas) + "\nCHAVES ESTRANGEIRAS\n" + "\n".join(fks)


def _system_ultra(db_path) -> str:
    """~800 tokens: esquema + só as regras que o modelo não consegue deduzir dos exemplos."""
    ini, fim, _ = _periodo(db_path)
    return f"""Converta a pergunta, em português, em UMA consulta SQL (SQLite) sobre o banco de lotação de ônibus InfoFrota (Transcol, Grande Vitória).

ESQUEMA (tabela(colunas))
{_esquema_compacto(db_path)}

REGRAS
- Dados de {ini} a {fim}; {fim} é a referência para "último dia". Sem datas na pergunta, não filtre por data.
- Datas/horas são TEXT 'AAAA-MM-DD HH:MM:SS'. linhas.numero é TEXT ('562').
- Alertas: ATENCAO 75% a menos de 90%, CRITICO 90% ou mais. calendario.tipo_dia: util, sabado, domingo, feriado.
- resumos_hora com parada_id NULL é o resumo da linha inteira. Por linha/dia use resumos_dia; por parada, município ou viagem use registros_ocupacao.
- Somente leitura. Pedido de alterar dados, ou algo que o banco não tem, é pode_responder = false.

{FORMATO_RESPOSTA}"""


def montar_system(db_path=DB_PATH, compacto=False) -> str:
    """compacto: False (DDL completo), True (tabela(colunas) + glossário) ou "ultra"."""
    if compacto == "ultra":
        return _system_ultra(db_path)
    ini, fim, n_monit = _periodo(db_path)
    esquema = (f"ESQUEMA (tabela(colunas))\n{_esquema_compacto(db_path)}" if compacto
               else f"ESQUEMA\n{_ddl(db_path)}")
    return f"""Você é o assistente de dados do InfoFrota, um sistema de monitoramento de lotação de ônibus da Grande Vitória (Transcol, CETURBES). Sua tarefa é transformar a pergunta do usuário, em português, em UMA consulta SQL (dialeto SQLite) sobre o banco abaixo.

{esquema}

TABELAS (o que cada linha representa)
- linhas: uma linha de ônibus da CETURBES. onibus: um veículo. paradas: um ponto de parada. linha_paradas: a ordem das paradas em cada linha e sentido.
- viagens: cada saída de um ônibus em uma linha. data_inicio e data_fim marcam o início e o fim da viagem (canceladas não têm data_fim).
- registros_ocupacao: leitura bruta do sensor, uma por parada em cada viagem. Para saber a linha, ligue a viagens (viagem_id); a data e a hora estão em momento.
- alertas: gerados a partir das leituras; criado_em é a data e a hora do alerta.
- resumos_hora: agregado por linha (e por parada) e por hora. resumos_dia: agregado por linha e por dia (média, máximo, hora de pico, totais de embarque e desembarque).
- clima_hora: chuva e temperatura por hora. calendario: o tipo de cada dia.
- v_lotacao_clima: lotação por linha e por hora, já ligada ao clima daquela hora.
- Escolha da tabela pelo nível da pergunta: por linha ou por dia, prefira resumos_dia; por hora, resumos_hora com parada_id NULL; por parada, município ou viagem, registros_ocupacao.

REGRAS DO DOMÍNIO
- Os dados cobrem de {ini} a {fim}; {fim} é a data de referência para termos relativos como "último dia" ou "semana passada". Se a pergunta não citar datas (ou disser "no período"), considere todos os dados e NÃO filtre por data. Quando citar datas, use datas absolutas.
- Datas e horas são TEXT no formato 'AAAA-MM-DD HH:MM:SS'. Use date(), strftime() e julianday().
- linhas.numero é TEXT (ex.: '562'): compare com aspas.
- Só as {n_monit} linhas com monitorada = 1 têm viagens, leituras, alertas e resumos.
- percentual e media_percentual são % da capacidade do ônibus e podem passar de 100.
- Alertas: ATENCAO vai de 75% a menos de 90%; CRITICO é 90% ou mais.
- Em resumos_hora, parada_id NULL é o resumo da linha inteira; com parada_id é o resumo da parada.
- viagens canceladas não têm leituras de ocupação.
- calendario.tipo_dia vale 'util', 'sabado', 'domingo' ou 'feriado'.
- Use somente tabelas e colunas do esquema. Nunca invente colunas.
- Gere apenas consultas de leitura. Se o usuário pedir para alterar, apagar ou inserir dados, ou perguntar algo que o banco não tem (posição GPS, pagamentos, motoristas, previsões do futuro), responda com pode_responder = false.

{FORMATO_RESPOSTA}"""


def mensagens_exemplo(shots: int = 3) -> list:
    msgs = []
    for pergunta, resposta in EXEMPLOS[:shots]:
        msgs.append({"role": "user", "content": pergunta})
        msgs.append({"role": "assistant", "content": json.dumps(resposta, ensure_ascii=False)})
    return msgs


SYSTEM_TEXTO = """Você é o assistente do InfoFrota. Receberá a pergunta do usuário, a consulta SQL executada e o resultado. Responda em português, em até 4 frases, usando apenas os números do resultado. Não invente informação. Se o resultado vier vazio ou nulo, diga que não há dados para esse filtro ou período. Se o resultado estiver marcado como truncado, avise que só as primeiras linhas foram consideradas. Não repita o SQL."""


def mensagem_texto(pergunta, sql, colunas, linhas, truncado, max_linhas=40) -> str:
    return json.dumps({
        "pergunta": pergunta, "sql": sql, "colunas": colunas,
        "linhas": linhas[:max_linhas], "truncado": truncado or len(linhas) > max_linhas,
    }, ensure_ascii=False, default=str)
