# Agente x consulta única: openai-openai/gpt-oss-20b | 13 perguntas de vários passos

Mesmo modelo nos dois. Acerto = todos os valores esperados aparecem no texto final. Dados sintéticos; poucas perguntas, então diferenças pequenas são ruído.

| | Acertos | Chamadas ao modelo (média) |
|---|---|---|
| Consulta única | 7/13 | 1.62 |
| Agente | 6/13 | 6.15 (1.15 consultas SQL) |

## Perguntas com falha em pelo menos um modo (9)

### M01 Qual linha tem mais alertas críticos e em que hora do dia esses alertas mais acontecem nessa linha?
- esperado: ['562', '17|17h|17:00']
- consulta única: falhou | agente: ok
- consulta única: None

### M02 Qual a linha com maior lotação média no período e qual parada concentra mais alertas críticos nela?
- esperado: ['562', 'Reta da Penha']
- consulta única: falhou | agente: falhou
- agente: Não é possível determinar a linha com maior lotação média nem a parada com mais alertas críticos sem consultar os dados.
- consulta única: None

### M04 Em qual hora do dia a lotação média das linhas monitoradas é mais alta e qual linha tem mais alertas críticos nessa hora?
- esperado: ['07|7h|7:00|07h|07:00', '562']
- consulta única: falhou | agente: ok
- consulta única: None

### M07 Qual linha teve mais viagens canceladas e quantos alertas críticos ela teve no período?
- esperado: ['536', '63']
- consulta única: falhou | agente: falhou
- agente: A linha 536 teve 38 viagens canceladas e 57 alertas críticos no período.
- consulta única: None

### M08 Quais placas de ônibus em manutenção têm como linha padrão a linha com mais alertas críticos?
- esperado: ['SIN-0049']
- consulta única: ok | agente: falhou
- agente: Nenhum ônibus em manutenção tem a linha padrão com mais alertas críticos.

### M09 No dia com mais alertas críticos, qual foi a data, qual foi o dia da semana e qual linha liderou?
- esperado: ['2026-10-09|09/10|9 de outubro', 'sexta', '591']
- consulta única: falhou | agente: falhou
- agente: Data: 2026-10-23, Dia da semana: sexta, Linha líder: 591
- consulta única: None

### M11 Qual linha teve a maior lotação média no último dia, qual foi a hora de pico dela nesse dia e quantos alertas críticos ela teve nesse dia?
- esperado: ['562', '07|7h|7:00|07h|07:00', '6']
- consulta única: ok | agente: falhou
- agente: Linha 562 teve a maior lotação média no último dia, com hora de pico às 07:00:00 e 0 alertas críticos registrados nesse dia.

### M12 Quantos alertas críticos a linha com mais alertas críticos teve nas horas 07, 08 e 09 (das 07:00 às 09:59)?
- esperado: ['562', '60']
- consulta única: falhou | agente: falhou
- agente: sem resposta final dentro do limite de passos
- consulta única: A linha com mais alertas críticos teve 60 alertas críticos nas horas 07, 08 e 09.

### M13 Quantas viagens canceladas existem no total e qual linha tem mais?
- esperado: ['450', '536']
- consulta única: ok | agente: falhou
- agente: sem resposta final dentro do limite de passos
