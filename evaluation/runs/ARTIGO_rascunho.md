# Text-to-SQL em português com RAG de esquema e LoRA: o que aprendi medindo um assistente sobre dados sintéticos

> Rascunho. Troque os trechos entre colchetes pelo que for seu. Tudo aqui vem do repositório; não acrescente números que não estejam lá.

## 1. O problema
Perguntas operacionais sobre uma frota de ônibus (quais linhas mais lotam, em que horário, se chover) viram SQL. O projeto InfoFrota é um experimento independente sobre uma base **sintética**, com rótulos reais de linhas da CETURB-ES (CSV aberto, CC0).

## 2. Arquitetura em uma imagem
Pergunta, RAG de esquema (BM25), LLM, guarda somente leitura, SQLite, resposta. Cite os três níveis da guarda: instrução única SELECT/WITH, authorizer do SQLite e conexão `mode=ro`, com limite de 200 linhas e 5 s.

## 3. Como medir sem se enganar
- Benchmark congelado de 56 perguntas (v2.1) com SQL de referência.
- O índice RAG nunca inclui o benchmark (teste automatizado).
- Dados de treino por famílias de pergunta, com filtros anti-vazamento: Jaccard 0,8 mascarando entidades e números, esqueleto de SQL, famílias próximas excluídas. Similaridade máxima com o teste: 0,71.

## 4. Resultados
| Condição | Acertos |
|---|---:|
| Base, prompt compacto | 19/56 |
| LoRA, prompt compacto | 36/56 |
| Base + RAG, prompt ultra | 28/56 |
| LoRA com contexto + RAG, prompt ultra | 39/56 |

Diga claramente: 56 perguntas, diferença de 1 ou 2 acertos é ruído; a segunda rodada nasceu da análise de erros da primeira; o nível difícil ficou em 3 de 15; a pergunta D06 tem defeito conhecido que não foi corrigido depois de ver o resultado.

## 5. O que deu errado e o que mudou

Durante os experimentos, foram identificadas falhas relacionadas à interpretação do esquema do banco, aos relacionamentos entre tabelas e ao tratamento de datas. Também foram avaliados comportamentos de recusa para perguntas que não podem ser respondidas com os dados disponíveis.

### 5.1. Erro de relacionamento entre tabelas (JOIN)

**Pergunta:** Qual hora do dia tem a maior lotação média em dias úteis?

O modelo tentou acessar `calendario.tipo_dia` sem realizar a junção com a tabela `calendario`.

SQL gerado:

```sql
SELECT data_hora, AVG(media_percentual)
FROM resumos_hora
WHERE calendario.tipo_dia = 'util'
GROUP BY data_hora;
```

**Erro:** `no such column: calendario.tipo_dia`

A consulta correta exige relacionar `resumos_hora` e `calendario` utilizando a data:

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

**Resultado esperado:** 7 horas.

Fonte: `evaluation/runs/20261106-072516_Llama-3.1-8B-Instruct_0shot_ultra_rag.md`

### 5.2. Erro na interpretação de filtros de data

**Pergunta:** Quantas viagens concluídas houve em 20/10/2026?

O modelo utilizou `data_fim` como referência, embora a pergunta solicitasse a quantidade de viagens iniciadas naquela data.

SQL gerado:

```sql
SELECT COUNT(*)
FROM viagens
WHERE data_fim = '2026-10-20'
  AND status = 'concluida';
```

SQL correto:

```sql
SELECT COUNT(*)
FROM viagens
WHERE date(data_inicio) = '2026-10-20'
  AND status = 'concluida';
```

**Resultado obtido:** 0 viagens.

**Resultado esperado:** 1.025 viagens.

Esse caso demonstra que uma consulta pode ser sintaticamente válida e ainda produzir um resultado incorreto por interpretar equivocadamente o significado de uma coluna.

Fonte: `evaluation/runs/20261105_Llama-3.1-8B-Instruct_0shot_compacto.md`

### 5.3. Recusa de perguntas fora do escopo

**Pergunta:** Qual a posição GPS atual do ônibus SIN-0001?

O banco experimental não possui informações de posicionamento GPS em tempo real. Ele contém registros de ocupação associados a viagens e paradas.

O comportamento esperado é recusar a solicitação, explicar a ausência desses dados e não gerar uma consulta SQL inventando informações.

Esse comportamento faz parte dos testes de limite do benchmark, identificado como L02 em `evaluation/questions.json`.

Na avaliação com Llama 3.1 8B, utilizando prompt Ultra e RAG, o modelo obteve **6 acertos em 6 perguntas de limite (100%)**.

Fonte: `evaluation/questions.json` e `evaluation/runs/20261106-072516_Llama-3.1-8B-Instruct_0shot_ultra_rag.md`

### 5.4. O que mudou entre os experimentos

Os experimentos demonstraram evolução com a adoção de estratégias de recuperação de contexto (RAG) e compactação do prompt.

| Configuração | Acertos | Acurácia |
|---|---:|---:|
| Prompt compacto | 19/56 | 33,9% |
| Prompt compacto + RAG | 25/56 | 44,6% |
| Prompt Ultra + RAG | 28/56 | 50,0% |

As principais mudanças foram:

- **RAG:** recuperação de tabelas, colunas, valores categóricos e regras relevantes antes da geração de SQL.
- **Prompt Ultra:** redução do contexto enviado ao modelo, mantendo o esquema e as regras essenciais do domínio.
- **Segurança:** manutenção da execução somente leitura, com validação da consulta, authorizer do SQLite e limites de execução.
- **Avaliação:** utilização de um conjunto congelado de 56 perguntas, evitando utilizar as perguntas de avaliação como exemplos de treinamento ou contexto de recuperação.

Apesar da evolução, permaneceram dificuldades em consultas complexas, especialmente em junções entre múltiplas tabelas, agregações e filtros temporais.

**Conclusão:** a combinação de RAG e um prompt mais compacto melhorou os resultados do modelo, mas não eliminou erros de interpretação do esquema e de construção de consultas. A avaliação também demonstrou a importância de separar perguntas respondíveis, solicitações fora do escopo e tentativas de escrita, garantindo que o assistente não invente informações nem altere o banco de dados.

*Observação: os resultados apresentados são experimentais, obtidos sobre uma base sintética e um conjunto controlado de perguntas. Não representam desempenho operacional em dados reais.*

## 6. Do notebook à API
FastAPI com quatro rotas, Docker Compose com n8n e alerta crítico por webhook. Testado manualmente: API com Groq e o workflow n8n. O modelo da demonstração (Groq) não é o modelo medido.

## 7. Limites
Dados simulados, 56 perguntas, sem teste em operação real, adaptadores fora do repositório. Próximo passo possível: v2.2 do benchmark com o D06 corrigido, mantendo os números antigos.

Links: repositório, notebook no Kaggle [link], modelo no Hugging Face [link].
