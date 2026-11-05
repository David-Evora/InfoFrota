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
