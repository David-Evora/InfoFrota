---
title: "Text-to-SQL em português com RAG e LoRA: o que aprendi medindo um assistente sobre dados sintéticos"
published: false
description: "Benchmark congelado de 56 perguntas, RAG de esquema, QLoRA no Llama 3.1 8B e uma guarda SQL somente leitura. Com os números, os erros e os limites."
tags: ai, sql, python, braziliandevs
---

Montei um assistente que transforma perguntas em português sobre uma frota de ônibus em SQL, e passei mais tempo **medindo** do que construindo. Este texto conta o que funcionou, o que errou e o que os números não provam.

> **Aviso:** o InfoFrota é um experimento independente, sem vínculo com a CETURB-ES. Os dados são **sintéticos**; só os rótulos de linhas vêm de um CSV aberto (CC0) da CETURBES. Nada aqui representa desempenho em operação real.

## 1. O problema

Perguntas operacionais sobre uma frota ("quais linhas mais lotam?", "em que horário?", "e se chover?") viram consultas SQL. Escolhi um banco SQLite sintético (16 linhas monitoradas, 30 dias, de 05/10 a 03/11/2026) para poder controlar tudo e comparar configurações de forma justa.

## 2. Arquitetura

Pergunta → RAG de esquema (BM25) → LLM → guarda somente leitura → SQLite → resposta.

- **RAG de esquema:** recupera tabelas, colunas, valores categóricos e regras relevantes antes de gerar o SQL.
- **Guarda em 3 camadas:** só aceita uma instrução `SELECT`/`WITH`; usa o authorizer do SQLite; abre a conexão com `mode=ro`. Ainda há limite de 200 linhas e 5 s por consulta.

## 3. Como medir sem se enganar

- **Benchmark congelado** de 56 perguntas (v2.1: 15 fáceis, 20 médias, 15 difíceis e 6 de limite), cada uma com SQL de referência.
- **O índice do RAG nunca inclui o benchmark.** Há um teste automatizado para isso.
- **Dados de treino por famílias de perguntas**, com filtros anti-vazamento: similaridade de Jaccard 0,8 (mascarando entidades e números), comparação do esqueleto do SQL e exclusão de famílias próximas. A similaridade máxima com o teste foi 0,71.
- Uma pergunta conta como acerto quando o **resultado** da consulta contém o esperado, mesmo que o SQL seja diferente.

## 4. Resultados

Llama 3.1 8B Instruct, 0 exemplos no prompt:

| Configuração | Prompt | Acertos | % |
|---|---|---:|---:|
| Base | compacto | 19/56 | 33,9 |
| Base + RAG | compacto | 25/56 | 44,6 |
| Base + RAG | ultra | 28/56 | 50,0 |
| LoRA | compacto | 36/56 | 64,3 |
| LoRA com contexto (sem RAG) | ultra | 33/56 | 58,9 |
| LoRA com contexto + RAG | ultra | 39/56 | 69,6 |

Como ler isso com honestidade:

- **São só 56 perguntas.** Uma diferença de 1 ou 2 acertos é ruído.
- **O resultado limpo é o LoRA compacto (36/56)**, definido antes de qualquer ajuste. A segunda rodada (LoRA treinado com contexto) foi planejada **depois** de analisar os erros da primeira, então o 39/56 não é um teste cego.
- **O nível difícil continua baixo:** 3 de 15 no melhor caso.
- **Defeito conhecido no teste:** a referência da pergunta D06 traz uma coluna `id` extra. Corrigindo, o LoRA compacto iria a 37/56. Não alterei os números publicados; a correção ficará para uma v2.2 do benchmark.

## 5. Onde o modelo erra

### 5.1. Esquece o JOIN

**Pergunta:** Qual hora do dia tem a maior lotação média em dias úteis?

O modelo filtrou por uma coluna de outra tabela sem fazer a junção:

```sql
SELECT data_hora, AVG(media_percentual)
FROM resumos_hora
WHERE calendario.tipo_dia = 'util'
GROUP BY data_hora;
```

Erro: `no such column: calendario.tipo_dia`. A consulta correta relaciona as tabelas pela data:

```sql
SELECT CAST(strftime('%H', rh.data_hora) AS INTEGER) AS hora
FROM resumos_hora rh
JOIN calendario k ON k.data = date(rh.data_hora)
WHERE rh.parada_id IS NULL
  AND k.tipo_dia = 'util'
GROUP BY hora
ORDER BY AVG(rh.media_percentual) DESC
LIMIT 1;
```

Resultado esperado: 7 h.
Fonte: `evaluation/runs/20261106-072516_Llama-3.1-8B-Instruct_0shot_ultra_rag.md`

### 5.2. SQL válido, resposta errada

**Pergunta:** Quantas viagens concluídas houve em 20/10/2026?

```sql
SELECT COUNT(*)
FROM viagens
WHERE data_fim = '2026-10-20'
  AND status = 'concluida';
```

A consulta roda sem erro, mas usa `data_fim`; o benchmark considera a data de início, e `data_fim` guarda data e hora. Correção:

```sql
SELECT COUNT(*)
FROM viagens
WHERE date(data_inicio) = '2026-10-20'
  AND status = 'concluida';
```

Obtido: 0 viagens. Esperado: 1.025.
Esse é o erro que mais me preocupa: **sintaticamente válido e silenciosamente errado**. Só um benchmark com resposta de referência pega isso.
Fonte: `evaluation/runs/20261105_Llama-3.1-8B-Instruct_0shot_compacto.md`

### 5.3. Perguntas que não deveriam virar SQL

**Pergunta:** Qual a posição GPS atual do ônibus SIN-0001?

O banco não tem GPS em tempo real, só ocupação por viagem e parada. O comportamento certo é recusar e explicar, sem inventar uma consulta. O benchmark tem 6 perguntas de limite assim (por exemplo, L02 em `evaluation/questions.json`). Com Llama 3.1 8B, prompt ultra e RAG, o modelo acertou as 6. É um bom sinal, mas são apenas 6 perguntas.

## 6. Do notebook à API

- **API FastAPI** com 4 rotas: `/saude`, `/perguntar`, `/alertas` e `/resumo`.
- **Docker Compose** com a API e o n8n.
- **n8n:** um workflow verifica alertas críticos a cada 5 minutos, evita duplicados por ID e envia um webhook (Discord/Slack).

A chave da API do provedor fica só no backend. Testei manualmente a API e o workflow. Atenção: o modelo da demonstração (Groq) **não é** o modelo medido no benchmark.

## 7. Limites

- Dados simulados; nenhum teste em operação real.
- Só 56 perguntas, e o nível difícil segue fraco.
- O D06 tem defeito conhecido, ainda não corrigido.
- Os adaptadores LoRA ficam fora do repositório (estão no Hugging Face).
- Usei assistentes de IA durante o desenvolvimento, inclusive para parte da infraestrutura (Docker, CI).

Próximo passo possível: v2.2 do benchmark com o D06 corrigido, mantendo os números antigos publicados.

## Links

- Repositório: [github.com/David-Evora/InfoFrota](https://github.com/David-Evora/InfoFrota)
- Notebook no Kaggle: [notebook-portifolio-infofrota](https://www.kaggle.com/code/davidevora/notebook-portifolio-infofrota)
- Adaptador LoRA no Hugging Face: [infofrota-text2sql-lora](https://huggingface.co/David-Evora/infofrota-text2sql-lora)
