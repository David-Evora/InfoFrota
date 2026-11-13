# Agente x consulta única: openai-openai/gpt-oss-20b | 1 perguntas de vários passos

Mesmo modelo nos dois. Acerto = todos os valores esperados aparecem no texto final. Dados sintéticos; poucas perguntas, então diferenças pequenas são ruído.

| | Acertos | Chamadas ao modelo (média) |
|---|---|---|
| Consulta única | 1/1 | None |
| Agente | 0/1 | None (None consultas SQL) |

## Perguntas com falha em pelo menos um modo (1)

### M08 Quais placas de ônibus em manutenção têm como linha padrão a linha com mais alertas críticos?
- esperado: ['SIN-0049']
- consulta única: ok | agente: falhou
- agente: LLMErro: falha ao chamar https://api.groq.com/openai/v1: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed","failed_generation":""}}

