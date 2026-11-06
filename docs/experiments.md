# Registro do experimento Text-to-SQL + LoRA

## Avaliação reportada

- Modelo base: Llama 3.1 8B Instruct.
- Adaptação: QLoRA/LoRA, 3 épocas.
- Dados reportados: 679 exemplos de treino e 59 de validação (738 exemplos no conjunto construído).
- Avaliação: 56 perguntas, benchmark v2.1.
- Condições comparadas: prompt compacto, zero-shot.

| Métrica | Base | Com LoRA |
|---|---:|---:|
| Acertos | 19/56 | 36/56 |
| Acurácia | 33,9% | 64,3% |
| Exata | 30,4% | 58,9% |

O ganho da métrica principal foi de 30,4 pontos percentuais. A métrica exata exige igualdade de resultado; a acurácia aceita colunas adicionais quando os valores esperados estão presentes.

## Cuidados metodológicos

- O benchmark v2.1 é mantido separado do conjunto de fine-tuning.
- `training/REPORT.md` registra os filtros aplicados para reduzir similaridade entre treino e teste.
- Não incluir `evaluation/questions.json` nem os relatórios de referência no índice RAG ou em novos dados de treinamento.
- O defeito conhecido da pergunta D06 foi documentado, mas a pontuação publicada não foi ajustada após a observação do resultado.
- A comparação com avaliações anteriores à versão v2.1 é apenas indicativa, porque houve mudanças no conjunto de perguntas e na correção.

Consulte os relatórios por pergunta em `evaluation/runs/` e o histórico das versões em `evaluation/CHANGELOG.md`.

## RAG de esquema (avaliação)

Mesmas 56 perguntas (v2.1), prompt compacto, zero-shot; o contexto recuperado (`--rag`) é adicionado ao prompt. O índice usa só o banco e regras do domínio, nunca o benchmark.

| Configuração | Fácil | Médio | Difícil | Limite | Total | Exata |
|---|---|---|---|---|---|---|
| Base | 9/15 | 5/20 | 0/15 | 5/6 | 19/56 (33,9%) | 30,4% |
| Base + RAG | 11/15 | 8/20 | 1/15 | 5/6 | 25/56 (44,6%) | 41,1% |
| LoRA | 13/15 | 13/20 | 4/15 | 6/6 | 36/56 (64,3%) | 58,9% |
| LoRA + RAG | 14/15 | 15/20 | 1/15 | 6/6 | 36/56 (64,3%) | 57,1% |

- Base + RAG: 8 perguntas passaram a acertar (D09, F04, F14, M05, M10, M13, M15, M20) e 2 deixaram de acertar (M02, M11).
- LoRA + RAG: 7 passaram a acertar (F10, F14, M04, M05, M10, M16, M17) e 7 deixaram de acertar (D02, D08, D14, F02, M01, M14, M18). O saldo é zero e o nível difícil caiu de 4 para 1 acerto.
- Com 56 perguntas, diferenças de 1 a 2 acertos são ruído. O ganho do modelo base (+6, com 8 melhoras e 2 pioras) é mais consistente que o efeito nulo no LoRA.
- Hipótese não testada: o LoRA foi treinado sem contexto recuperado e por isso não o usa bem. Testá-la exige treinar com o contexto no prompt.

## LoRA treinado com contexto recuperado (prompt `ultra`)

Mesmos 679 exemplos de treino, agora com o contexto recuperado da própria pergunta no prompt (`build_train_set.py --prompt ultra --rag`). Avaliação nas mesmas 56 perguntas (v2.1), zero-shot.

| Configuração (prompt `ultra`) | Fácil | Médio | Difícil | Limite | Total | Exata |
|---|---|---|---|---|---|---|
| Base | 8/15 | 5/20 | 0/15 | 6/6 | 19/56 (33,9%) | 30,4% |
| Base + RAG | 12/15 | 10/20 | 0/15 | 6/6 | 28/56 (50,0%) | 46,4% |
| LoRA (treinado com contexto), sem RAG na avaliação | 9/15 | 16/20 | 3/15 | 5/6 | 33/56 (58,9%) | 55,4% |
| LoRA (treinado com contexto) + RAG | 14/15 | 17/20 | 3/15 | 5/6 | **39/56 (69,6%)** | **66,1%** |

- Nas mesmas condições (`ultra` + RAG), o LoRA tem 39 acertos contra 28 do modelo base (+11).
- O RAG sozinho já ajuda o modelo base: 19 para 28 acertos (+9).
- O LoRA treinado com contexto depende dele: sem o RAG na avaliação cai de 39 para 33.
- Contra o LoRA sem contexto (64,3%, prompt compacto), o ganho é de 3 acertos. Com 56 perguntas isso está dentro do ruído, e as duas configurações diferem em prompt e em RAG ao mesmo tempo. O resultado limpo, definido antes de qualquer ajuste, é o de 64,3%.
- Esta segunda rodada foi planejada depois de analisar os erros da primeira (colunas e valores categóricos sem cobertura). Os dados de treino são os mesmos; só o contexto foi acrescentado.
- Dificuldade: o nível difícil continua baixo (3 de 15). Restam 17 erros: 13 com resultado diferente, 3 com erro de SQL e 1 pergunta de limite respondida (L05).
- Tempo médio de geração: 12,8 s por pergunta em uma T4 (8B em 4 bits, sem otimização de inferência).
