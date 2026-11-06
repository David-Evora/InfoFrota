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
