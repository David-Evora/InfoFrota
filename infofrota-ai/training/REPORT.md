# Conjunto de treino do LoRA

Modo: **SEM famílias próximas do teste** · prompt `compacto` · semente 42

Total: **738** exemplos (treino 679, validação 59) · recusas: 60 (8%)

| Nível | Exemplos |
|---|---|
| facil | 217 |
| medio | 331 |
| dificil | 130 |
| limite | 60 |

## Anti-vazamento (contra as 56 perguntas de teste)

- Pergunta de teste idêntica ou parecida (Jaccard ≥ 0.8, com entidades e números mascarados): descartadas.
- SQL com o mesmo esqueleto de um SQL de referência: descartados.
- Similaridade máxima com qualquer pergunta de teste entre os exemplos mantidos: **0.71** (média 0.36).
- Famílias próximas em conceito a perguntas de teste: **excluídas**.

Descartes:

- `duplicada`: 3
- `esqueleto_igual_ao_teste:F04`: 2
- `esqueleto_igual_ao_teste:F06`: 16
- `esqueleto_igual_ao_teste:F11`: 12
- `esqueleto_igual_ao_teste:F12`: 30
- `familia_proxima_excluida`: 23
- `parecida_com_teste:F04`: 1
- `parecida_com_teste:L01`: 48
- `resultado_vazio`: 9

Mais parecidos com o teste (para revisão manual):

- 0.71 · treino: «Quantas paradas a linha 563 tem no sentido ida?» · teste M18
- 0.71 · treino: «Quantas paradas a linha 901 tem no sentido ida?» · teste M18
- 0.71 · treino: «Quantas paradas a linha 508 tem no sentido ida?» · teste M18
- 0.67 · treino: «Qual a lotação média da linha 501 em dias úteis?» · teste L01
- 0.67 · treino: «Qual a lotação média da linha 559 às 8h?» · teste L01
- 0.67 · treino: «Qual a lotação média da linha 562 em dias úteis?» · teste L01
- 0.67 · treino: «Qual a lotação média da linha 563 em dias úteis?» · teste L01
- 0.67 · treino: «Qual a lotação média da linha 901 em dias úteis?» · teste L01

## Cobertura de colunas

44/66 nomes de coluna aparecem em algum SQL de treino. Sem cobertura: capacidade, condicao, feriado_nome, hora_pico, leituras_acima_75, leituras_atencao, leituras_criticas, linha_nome, linha_numero, max_percentual, min_percentual, monitorada, ocupacao_atual, onibus_placa, parada_atual, parada_nome, precaucao_descricao, status_ocupacao, total_alertas_atencao, total_leituras, total_registros, ultima_leitura.

## Exemplos por família

| Família | Exemplos |
|---|---|
| d_acima_media_linha | 16 |
| d_paradas_limiar | 8 |
| d_participacao | 3 |
| d_pivot | 3 |
| d_primeiro_por_dia | 24 |
| d_ranking | 3 |
| d_subconsulta_media | 3 |
| d_top2_por_grupo | 6 |
| d_ultimo_por_onibus | 32 |
| d_variacao_dia | 32 |
| f_alertas_dia | 15 |
| f_alertas_linha_tipo | 30 |
| f_calendario_dia | 20 |
| f_capacidade | 16 |
| f_clima_dia | 24 |
| f_contagem_onibus | 5 |
| f_coord_parada | 30 |
| f_max_lotacao_linha | 16 |
| f_msg_alerta | 8 |
| f_onibus_da_linha | 16 |
| f_paradas_municipio | 7 |
| f_viagens_dia_linha | 30 |
| m_alertas_diasemana | 2 |
| m_alertas_hora | 4 |
| m_distintos | 36 |
| m_duracao_linha | 16 |
| m_embarques_dia_linha | 30 |
| m_linhas_media_acima | 5 |
| m_media_linha_hora | 40 |
| m_media_linha_tipodia | 16 |
| m_modelo | 7 |
| m_municipio | 14 |
| m_paradas_linha | 30 |
| m_periodo | 40 |
| m_precaucao | 16 |
| m_resolucao | 14 |
| m_sentido_linha | 16 |
| m_taxa_cancel | 17 |
| m_top_paradas | 12 |
| m_viagens_lotadas | 16 |
| r_escrita | 12 |
| r_fora_dominio | 8 |
| r_sem_dado | 40 |

## Limites

- Perguntas geradas por modelos de frase (3 a 4 formulações por família): a variedade de linguagem é menor que a de usuários reais.
- A validação usa a mesma distribuição do treino: serve para acompanhar a perda, não para medir generalização. Quem mede é a avaliação de 56 perguntas.
