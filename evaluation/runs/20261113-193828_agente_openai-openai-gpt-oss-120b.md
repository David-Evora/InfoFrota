# Agente x consulta única: openai-openai/gpt-oss-120b | 13 perguntas multi-etapas

Mesmo modelo nos dois modos. Acerto = todos os valores esperados aparecem no texto final. Dados sintéticos; conjuntos pequenos ou selecionados para diagnóstico não são avaliação independente.

| | Acertos | Chamadas ao modelo (média) |
|---|---|---|
| Consulta única | 9/13 | 1.77 |
| Agente | 9/13 | 3.38 (1.85 consultas SQL) |

## Perguntas com falha em pelo menos um modo (6)

### M02 Qual a linha com maior lotação média no período e qual parada concentra mais alertas críticos nela?
- esperado: ['562', 'Reta da Penha']
- consulta única: falhou | agente: ok
- consulta única: None

### M03 Qual dia da semana concentra mais alertas críticos e qual linha lidera nesse dia da semana?
- esperado: ['sexta', '591']
- consulta única: ok | agente: falhou
- agente: Na sexta‑feira ocorre a maior quantidade de alertas críticos, com 154 ocorrências. A linha que mais gera esses alertas críticos nesse dia é a **linha 591**, responsável por 38 dos alertas.

### M04 Em qual hora do dia a lotação média das linhas monitoradas é mais alta e qual linha tem mais alertas críticos nessa hora?
- esperado: ['07|7h|7:00|07h|07:00', '562']
- consulta única: falhou | agente: ok
- consulta única: None

### M08 Quais placas de ônibus em manutenção têm como linha padrão a linha com mais alertas críticos?
- esperado: ['SIN-0049']
- consulta única: ok | agente: falhou
- agente: A linha com o maior número de alertas críticos é a de ID 72. Entre os ônibus em manutenção, apenas o veículo com placa **SIN‑0049** tem essa linha como padrão. Portanto, a placa solicitada é SIN‑0049.

### M09 No dia com mais alertas críticos, qual foi a data, qual foi o dia da semana e qual linha liderou?
- esperado: ['2026-10-09|09/10|9 de outubro', 'sexta', '591']
- consulta única: falhou | agente: falhou
- agente: No dia com mais alertas críticos foi **2026‑10‑09**, que caiu numa **sexta‑feira**. A linha que liderou foi a **591 – Serra / T. Campo Grande via Reta da Penha / BR 262**, com 10 alertas críticos.
- consulta única: None

### M12 Quantos alertas críticos a linha com mais alertas críticos teve nas horas 07, 08 e 09 (das 07:00 às 09:59)?
- esperado: ['562', '60']
- consulta única: falhou | agente: falhou
- agente: A linha que mais recebeu alertas críticos nas horas 07:00 até 09:59 teve **60 alertas críticos**.
- consulta única: A linha com mais alertas críticos entre 07:00 e 09:59 registrou **60** alertas críticos.
