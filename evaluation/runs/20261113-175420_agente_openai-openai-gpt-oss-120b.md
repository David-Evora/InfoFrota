# Agente x consulta única: openai-openai/gpt-oss-120b | 6 perguntas de vários passos

Mesmo modelo nos dois. Acerto = todos os valores esperados aparecem no texto final. Dados sintéticos; poucas perguntas, então diferenças pequenas são ruído.

| | Acertos | Chamadas ao modelo (média) |
|---|---|---|
| Consulta única | 3/6 | 1.8 |
| Agente | 5/6 | 3.8 (2.4 consultas SQL) |

## Perguntas com falha em pelo menos um modo (3)

### M02 Qual a linha com maior lotação média no período e qual parada concentra mais alertas críticos nela?
- esperado: ['562', 'Reta da Penha']
- consulta única: falhou | agente: falhou
- agente: LLMErro: falha ao chamar https://api.groq.com/openai/v1: HTTP 400 {"error":{"message":"Failed to generate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed","failed_generation":"{\"pensamento\":\"Obter o id da linha 562\",\"ferramenta\":\"sql\",\"entrada\":\"SELECT id FROM linhas WHERE numero = '562';\"}{\"pensamento\":\"Contar alertas críticos por parada na linha 562\",\"ferramenta\":\"sql\",\"entrada\":\"SELECT p.nome AS parada_nome, COUNT(a.id) AS total_criticos FROM alert
- consulta única: None

### M09 No dia com mais alertas críticos, qual foi a data, qual foi o dia da semana e qual linha liderou?
- esperado: ['2026-10-09|09/10|9 de outubro', 'sexta', '591']
- consulta única: falhou | agente: ok
- consulta única: None

### M12 Quantos alertas críticos a linha com mais alertas críticos teve nas horas 07, 08 e 09 (das 07:00 às 09:59)?
- esperado: ['562', '60']
- consulta única: falhou | agente: ok
- consulta única: A linha com mais alertas críticos entre 07:00 e 09:59 registrou **60** alertas críticos.
