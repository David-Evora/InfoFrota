# Agente x consulta única: openai-openai/gpt-oss-20b | 3 perguntas de vários passos

Mesmo modelo nos dois. Acerto = todos os valores esperados aparecem no texto final. Dados sintéticos; poucas perguntas, então diferenças pequenas são ruído.

| | Acertos | Chamadas ao modelo (média) |
|---|---|---|
| Consulta única | 1/3 | 1.33 |
| Agente | 2/3 | 5.67 (1.33 consultas SQL) |

## Perguntas com falha em pelo menos um modo (2)

### M01 Qual linha tem mais alertas críticos e em que hora do dia esses alertas mais acontecem nessa linha?
- esperado: ['562', '17|17h|17:00']
- consulta única: falhou | agente: ok
- consulta única: None

### M02 Qual a linha com maior lotação média no período e qual parada concentra mais alertas críticos nela?
- esperado: ['562', 'Reta da Penha']
- consulta única: falhou | agente: falhou
- agente: Não é possível determinar a linha com maior lotação média nem a parada com mais alertas críticos sem consultar os dados.
- consulta única: None
