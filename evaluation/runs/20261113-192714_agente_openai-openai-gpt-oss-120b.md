# Agente x consulta única: openai-openai/gpt-oss-120b | 1 perguntas multi-etapas

Mesmo modelo nos dois modos. Acerto = todos os valores esperados aparecem no texto final. Dados sintéticos; conjuntos pequenos ou selecionados para diagnóstico não são avaliação independente.

| | Acertos | Chamadas ao modelo (média) |
|---|---|---|
| Consulta única | 0/1 | 1.0 |
| Agente | 1/1 | 3.0 (2.0 consultas SQL) |

## Perguntas com falha em pelo menos um modo (1)

### M02 Qual a linha com maior lotação média no período e qual parada concentra mais alertas críticos nela?
- esperado: ['562', 'Reta da Penha']
- consulta única: falhou | agente: ok
- consulta única: None
