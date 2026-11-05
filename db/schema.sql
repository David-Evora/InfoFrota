-- ============================================================
--  InfoFrota AI - schema (SQLite)
--  Adaptado do schema MySQL do InfoFrota (CETURBES / Transcol).
--
--  Diferenças em relação ao MySQL original:
--   * Removidos: usuarios (não é útil para análise), triggers,
--     stored procedures e events. A lógica de alertas e as
--     agregações são feitas pelo gerador (scripts/generate_data.py).
--   * ENUM virou TEXT com CHECK; BOOLEAN virou INTEGER (0/1).
--   * Datas e horas são TEXT: 'YYYY-MM-DD HH:MM:SS'.
--   * linhas ganhou 'tipo' e 'monitorada'; target_ocupacao_pct saiu
--     (era parâmetro da simulação, não deve aparecer para o assistente).
--   * paradas ganhou 'coordenadas_aproximadas'.
--   * resumos_hora.total_alertas virou leituras_acima_75 (nome fiel ao conteúdo).
--   * Novas tabelas: clima_hora e calendario.
-- ============================================================

PRAGMA foreign_keys = ON;

-- Linhas da CETURBES. 'monitorada' = 1 indica linhas com sensor
-- de lotação (piloto); só elas têm viagens e leituras.
CREATE TABLE linhas (
  id                  INTEGER PRIMARY KEY,
  numero              TEXT    NOT NULL UNIQUE,          -- ex: '562'
  nome                TEXT    NOT NULL,                 -- rótulo oficial da linha
  tipo                TEXT    NOT NULL DEFAULT 'convencional'
                      CHECK (tipo IN ('convencional','circular','expresso','noturno')),
  capacidade_padrao   INTEGER NOT NULL DEFAULT 80,
  monitorada          INTEGER NOT NULL DEFAULT 0 CHECK (monitorada IN (0,1)),
  ativa               INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0,1))
);

CREATE TABLE onibus (
  id               INTEGER PRIMARY KEY,
  placa            TEXT    NOT NULL UNIQUE,
  modelo           TEXT,
  capacidade       INTEGER NOT NULL DEFAULT 80,
  linha_padrao_id  INTEGER REFERENCES linhas(id) ON DELETE SET NULL,
  status           TEXT    NOT NULL DEFAULT 'ativo'
                   CHECK (status IN ('ativo','manutencao','inativo'))
);

CREATE TABLE paradas (
  id                       INTEGER PRIMARY KEY,
  nome                     TEXT    NOT NULL,
  codigo                   TEXT    UNIQUE,
  latitude                 REAL    NOT NULL,
  longitude                REAL    NOT NULL,
  municipio                TEXT    NOT NULL,
  ativa                    INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0,1)),
  coordenadas_aproximadas  INTEGER NOT NULL DEFAULT 0 CHECK (coordenadas_aproximadas IN (0,1))
);

CREATE TABLE linha_paradas (
  id         INTEGER PRIMARY KEY,
  linha_id   INTEGER NOT NULL REFERENCES linhas(id)  ON DELETE CASCADE,
  parada_id  INTEGER NOT NULL REFERENCES paradas(id) ON DELETE CASCADE,
  ordem      INTEGER NOT NULL,
  sentido    TEXT    NOT NULL DEFAULT 'ida' CHECK (sentido IN ('ida','volta')),
  UNIQUE (linha_id, parada_id, sentido)
);

CREATE TABLE viagens (
  id           INTEGER PRIMARY KEY,
  onibus_id    INTEGER NOT NULL REFERENCES onibus(id),
  linha_id     INTEGER NOT NULL REFERENCES linhas(id),
  sentido      TEXT    NOT NULL DEFAULT 'ida' CHECK (sentido IN ('ida','volta')),
  data_inicio  TEXT    NOT NULL,
  data_fim     TEXT,
  status       TEXT    NOT NULL DEFAULT 'concluida'
               CHECK (status IN ('em_andamento','concluida','cancelada'))
);
CREATE INDEX idx_viagens_onibus ON viagens(onibus_id);
CREATE INDEX idx_viagens_linha  ON viagens(linha_id);
CREATE INDEX idx_viagens_inicio ON viagens(data_inicio);

-- Leituras do sensor de ocupação, uma por parada em cada viagem.
CREATE TABLE registros_ocupacao (
  id              INTEGER PRIMARY KEY,
  viagem_id       INTEGER NOT NULL REFERENCES viagens(id),
  parada_id       INTEGER NOT NULL REFERENCES paradas(id),
  momento         TEXT    NOT NULL,
  embarcaram      INTEGER NOT NULL DEFAULT 0,
  desembarcaram   INTEGER NOT NULL DEFAULT 0,
  ocupacao_atual  INTEGER NOT NULL,        -- passageiros a bordo após a parada
  percentual      REAL    NOT NULL         -- ocupacao_atual / capacidade * 100
);
CREATE INDEX idx_reg_viagem  ON registros_ocupacao(viagem_id, momento);
CREATE INDEX idx_reg_parada  ON registros_ocupacao(parada_id);
CREATE INDEX idx_reg_momento ON registros_ocupacao(momento);

-- ATENCAO >= 75%, CRITICO >= 90% (mesma regra do trigger original).
CREATE TABLE alertas (
  id                   INTEGER PRIMARY KEY,
  viagem_id            INTEGER NOT NULL REFERENCES viagens(id),
  linha_id             INTEGER NOT NULL REFERENCES linhas(id),
  parada_id            INTEGER REFERENCES paradas(id),
  tipo                 TEXT    NOT NULL CHECK (tipo IN ('ATENCAO','CRITICO')),
  percentual           REAL    NOT NULL,
  mensagem             TEXT    NOT NULL,
  criado_em            TEXT    NOT NULL,
  resolvido            INTEGER NOT NULL DEFAULT 0 CHECK (resolvido IN (0,1)),
  resolvido_em         TEXT,
  em_precaucao         INTEGER NOT NULL DEFAULT 0 CHECK (em_precaucao IN (0,1)),
  precaucao_descricao  TEXT
);
CREATE INDEX idx_alertas_linha_criado ON alertas(linha_id, criado_em);

-- Agregado por hora. parada_id NULL = linha inteira.
CREATE TABLE resumos_hora (
  id                   INTEGER PRIMARY KEY,
  linha_id             INTEGER NOT NULL REFERENCES linhas(id),
  parada_id            INTEGER REFERENCES paradas(id),
  data_hora            TEXT    NOT NULL,      -- 'YYYY-MM-DD HH:00:00'
  total_registros      INTEGER NOT NULL,
  media_percentual     REAL    NOT NULL,
  max_percentual       REAL    NOT NULL,
  min_percentual       REAL    NOT NULL,
  total_embarcaram     INTEGER NOT NULL,
  total_desembarcaram  INTEGER NOT NULL,
  leituras_acima_75    INTEGER NOT NULL       -- leituras com percentual >= 75
);
CREATE INDEX idx_rh_data_hora ON resumos_hora(data_hora);
CREATE INDEX idx_rh_linha     ON resumos_hora(linha_id, data_hora);

CREATE TABLE resumos_dia (
  id                     INTEGER PRIMARY KEY,
  linha_id               INTEGER NOT NULL REFERENCES linhas(id),
  data                   TEXT    NOT NULL,    -- 'YYYY-MM-DD'
  media_percentual       REAL    NOT NULL,
  max_percentual         REAL    NOT NULL,
  hora_pico              TEXT,                -- 'HH:MM:SS'
  total_viagens          INTEGER NOT NULL,
  total_alertas_atencao  INTEGER NOT NULL,
  total_alertas_critico  INTEGER NOT NULL,
  total_embarcaram       INTEGER NOT NULL,
  total_desembarcaram    INTEGER NOT NULL,
  UNIQUE (linha_id, data)
);

-- Clima por hora (sintético, sem fonte externa).
CREATE TABLE clima_hora (
  data_hora      TEXT PRIMARY KEY,            -- 'YYYY-MM-DD HH:00:00'
  chuva_mm       REAL NOT NULL,
  temperatura_c  REAL NOT NULL,
  condicao       TEXT NOT NULL CHECK (condicao IN ('seco','garoa','chuva','chuva_forte'))
);

CREATE TABLE calendario (
  data           TEXT PRIMARY KEY,
  dia_semana     TEXT NOT NULL,
  tipo_dia       TEXT NOT NULL CHECK (tipo_dia IN ('util','sabado','domingo','feriado')),
  feriado_nome   TEXT
);

-- ------------------------------------------------------------
--  Views
-- ------------------------------------------------------------

CREATE VIEW v_ocupacao_atual AS
SELECT v.id AS viagem_id, l.numero AS linha_numero, l.nome AS linha_nome,
       o.placa AS onibus_placa, p.nome AS parada_atual,
       r.ocupacao_atual, r.percentual, r.momento AS ultima_leitura,
       CASE WHEN r.percentual >= 90 THEN 'CRITICO'
            WHEN r.percentual >= 75 THEN 'ATENCAO'
            WHEN r.percentual >= 50 THEN 'MEDIO'
            ELSE 'VAZIO' END AS status_ocupacao
FROM viagens v
JOIN linhas l ON l.id = v.linha_id
JOIN onibus o ON o.id = v.onibus_id
JOIN registros_ocupacao r ON r.viagem_id = v.id
JOIN paradas p ON p.id = r.parada_id
WHERE v.status = 'em_andamento'
  AND r.momento = (SELECT MAX(r2.momento) FROM registros_ocupacao r2 WHERE r2.viagem_id = v.id);

CREATE VIEW v_alertas_abertos AS
SELECT a.id, a.tipo, l.numero AS linha_numero, l.nome AS linha_nome,
       p.nome AS parada_nome, a.percentual, a.mensagem, a.criado_em,
       a.em_precaucao, a.precaucao_descricao
FROM alertas a
JOIN linhas l ON l.id = a.linha_id
LEFT JOIN paradas p ON p.id = a.parada_id
WHERE a.resolvido = 0;

CREATE VIEW v_relatorio_linha_hora AS
SELECT l.numero AS linha_numero, l.nome AS linha_nome, rh.data_hora,
       date(rh.data_hora) AS data,
       CAST(strftime('%H', rh.data_hora) AS INTEGER) AS hora,
       rh.media_percentual, rh.max_percentual,
       rh.total_embarcaram, rh.total_desembarcaram, rh.leituras_acima_75
FROM resumos_hora rh
JOIN linhas l ON l.id = rh.linha_id
WHERE rh.parada_id IS NULL;

-- Paradas com maior ocupação média nos últimos 30 dias de dados.
CREATE VIEW v_relatorio_parada_problema AS
SELECT l.numero AS linha_numero, p.nome AS parada_nome, p.municipio,
       COUNT(*) AS total_leituras,
       ROUND(AVG(r.percentual), 1) AS media_percentual,
       MAX(r.percentual) AS max_percentual,
       SUM(r.embarcaram) AS total_embarcaram,
       SUM(r.desembarcaram) AS total_desembarcaram,
       SUM(r.percentual >= 90) AS leituras_criticas,
       SUM(r.percentual >= 75) AS leituras_atencao
FROM registros_ocupacao r
JOIN viagens v ON v.id = r.viagem_id
JOIN linhas  l ON l.id = v.linha_id
JOIN paradas p ON p.id = r.parada_id
WHERE r.momento >= datetime((SELECT MAX(momento) FROM registros_ocupacao), '-30 days')
GROUP BY l.id, p.id;

-- Lotação por linha e hora junto com o clima da mesma hora.
CREATE VIEW v_lotacao_clima AS
SELECT l.numero AS linha_numero, rh.data_hora,
       rh.media_percentual, rh.max_percentual,
       c.chuva_mm, c.temperatura_c, c.condicao
FROM resumos_hora rh
JOIN linhas l ON l.id = rh.linha_id
LEFT JOIN clima_hora c ON c.data_hora = rh.data_hora
WHERE rh.parada_id IS NULL;
