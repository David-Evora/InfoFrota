# Versões do conjunto de avaliação e do prompt

Resultados de versões diferentes **não são comparáveis diretamente**. Todo relatório traz a versão das perguntas e do prompt no cabeçalho.

## Perguntas v2.1 · prompt v2 (05/11/2026)

Segunda execução do llama3.1 (v2): 30/56 (53,6%), exata 44,6%. Achado: em M15 o modelo devolveu ida e volta em colunas (`[[289, 350]]`) com valores corretos e foi reprovado porque a referência esperava uma linha por sentido. Outras quatro perguntas de comparação (M09, D03, D08, D12) tinham a mesma ambiguidade de formato.
- Texto de M09, M15, D03, D08 e D12 agora pede explicitamente uma linha para cada caso. SQLs de referência e resultados esperados **não mudaram** (verificado).
- Prompt v2 sem alteração; as respostas em cache das outras 51 perguntas continuam válidas.

## Perguntas v2 · prompt v2 (05/11/2026)

Motivo: a primeira execução com llama3.1 (v1) mostrou defeitos na própria avaliação, além dos erros do modelo.

Perguntas (as perguntas em si não mudaram, só a forma de corrigir):
- **Ordem das linhas só conta quando a pergunta pede** ("da mais para a menos lotada", "em ordem"): M01 e M18. Antes, 24 perguntas exigiam ordem, e o llama foi reprovado em F15, M08, M12 e M20 com valores corretos, só em outra ordem.
- **SQLs de referência com as colunas mínimas pedidas** (16 perguntas: F02, M02, M04, M06, M07, M08, M13, M14, M16, M17, D04, D09, D10, D11, D14, D15). Antes, a referência trazia colunas que a pergunta não pedia (ex.: F02 pedia "quais linhas" e a referência incluía o nome), e quem respondia só o que foi pedido era reprovado.
- **Métrica principal agora aceita colunas extras** (a exata continua no relatório). Os valores esperados não mudaram: verificado automaticamente que cada resultado novo está contido no anterior.

Prompt (v2): glossário com a granularidade de cada tabela e regra para não filtrar datas quando a pergunta não cita período. Motivado por erros do llama (colunas inventadas, filtros de data que cortavam o último dia). Não menciona nenhuma pergunta da avaliação.

## Perguntas v1 · prompt v1 (04/11/2026)
Versão inicial. Baseline llama3.1: 21/56 (37,5%).
