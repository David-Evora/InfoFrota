# InfoFrota

**Plataforma em desenvolvimento para inteligência operacional do transporte coletivo na Grande Vitória (Transcol).** O InfoFrota propõe reunir dados de ocupação, frota, linhas, horários e fatores externos em uma visão integrada para apoiar o planejamento e a tomada de decisão.

<p align="center">
  <a href="https://david-evora.github.io/InfoFrota/">Abrir demonstração visual (após ativar Pages)</a>
  ·
  <a href="docs/architecture.md">Arquitetura geral</a>
  ·
  <a href="docs/INFOFROTA_AI.md">Documentação do InfoFrota AI</a>
</p>

> **Estado público do projeto — 05/11/2026:** iniciativa em fase de prototipagem. Há um MVP de interface web em HTML/CSS/JavaScript, uma modelagem MySQL planejada para a plataforma operacional e um módulo experimental InfoFrota AI funcional via CLI, com avaliação Text-to-SQL e fine-tuning LoRA. A demonstração web publicada neste repositório é estática e usa exclusivamente dados ilustrativos; não está conectada a sensores, à CETURB/ES ou a um banco operacional.

## 1. O problema e a proposta

O planejamento do transporte coletivo depende de compreender não apenas onde os ônibus estão, mas também **quantas pessoas estão utilizando cada linha, em quais horários e em quais regiões**. Informações de ocupação, quando disponíveis de forma estruturada e analisadas junto a variáveis como calendário e clima, podem apoiar decisões sobre distribuição da frota, reforço de viagens e identificação de períodos críticos.

O InfoFrota propõe uma plataforma para:

- acompanhar indicadores de ocupação por linha, veículo, região e faixa horária;
- identificar padrões de demanda, horários de pico e possíveis situações de superlotação;
- reunir histórico operacional para relatórios e análises comparativas;
- explorar relações entre demanda, calendário e condições climáticas;
- apoiar o planejamento de linhas e alocação de frota com informações consolidadas;
- oferecer uma camada de inteligência artificial para consultar os dados em linguagem natural.

O objetivo é transformar registros operacionais em informação acessível para análise e apoio à decisão. O InfoFrota é uma proposta independente em desenvolvimento, não um sistema oficial da CETURB/ES e não possui endosso institucional declarado.

## 2. Como a solução está sendo pensada

### Captação e atualização de ocupação — conceito em estudo

A proposta atual considera uma pequena unidade embarcada, com câmera posicionada em ponto estratégico no interior do ônibus e processamento baseado em hardware compacto (por exemplo, ESP32, sujeito à validação de viabilidade). A lógica de contagem, posicionamento, privacidade, instalação e desempenho em condições de lotação ainda precisa ser validada em protótipo físico.

A comunicação poderá aproveitar a conectividade já disponível em parte da frota ou exigir conectividade própria. O desenho também considera armazenamento local temporário e sincronização posterior em cenários de instabilidade de internet. **Nenhum sensor ou fluxo de transmissão em operação real é disponibilizado por este repositório.**

### Tratamento e análise

Os registros seriam organizados para relacionar veículo, linha, viagem, horário e local de referência. A camada analítica foi pensada para consolidar indicadores por hora, dia, linha e parada, permitindo visualizar picos, comparar períodos e cruzar os dados com calendário e clima.

### Interface e apoio à decisão

O dashboard proposto reúne visão geral da operação, detalhamento por linha e veículo, alertas, histórico e relatórios. Em uma etapa posterior, a camada de IA permitirá formular perguntas em português e obter consultas aos dados, respeitando regras de segurança e acesso.

## 3. Módulos do projeto

| Módulo | Objetivo | Situação atual |
|---|---|---|
| Monitoramento de ocupação | Obter estimativas de embarque, desembarque e ocupação ao longo das viagens | Conceito e requisitos em avaliação; captura física ainda não validada |
| Banco e camada analítica | Organizar linhas, veículos, viagens, registros, alertas e agregações | Modelagem MySQL desenvolvida como base de projeto; o schema SQLite do módulo de IA é uma adaptação experimental |
| Dashboard operacional | Apresentar indicadores, linhas, frota, alertas e relatórios | MVP frontend em HTML, CSS e JavaScript; demonstração pública com dados ilustrativos |
| Análises e apoio ao planejamento | Identificar horários de pico e padrões de demanda, incluindo relações com clima e calendário | Escopo analítico definido; validação operacional pendente |
| **InfoFrota AI** | Permitir consultas aos dados em linguagem natural com Text-to-SQL | **Módulo experimental implementado via CLI; avaliação e fine-tuning LoRA realizados** |
| Integração e automação | Integrar interface, API, recuperação de contexto e fluxos de processamento | Próxima etapa: RAG, API e orquestração com n8n |

## 4. InfoFrota AI: resultado experimental

O InfoFrota AI é um módulo do projeto que investiga o uso de modelos de linguagem para converter perguntas em português em consultas SQL sobre uma base de dados controlada.

Em uma avaliação zero-shot com prompt compacto e 56 perguntas (benchmark v2.1), o Llama 3.1 8B Instruct apresentou os seguintes resultados:

| Modelo | Acertos | Acurácia principal | Correspondência exata |
|---|---:|---:|---:|
| Llama 3.1 8B Instruct (base) | 19/56 | 33,9% | 30,4% |
| Llama 3.1 8B Instruct + LoRA | 36/56 | **64,3%** | **58,9%** |

O resultado com LoRA representa ganho de **30,4 pontos percentuais** na métrica principal, nas mesmas condições de avaliação. O conjunto v2.1 é separado dos dados de fine-tuning; os relatórios documentam limitações e casos conhecidos do teste. A comparação é experimental e restrita ao banco e às perguntas controladas, não representa desempenho em produção ou sobre dados reais de transporte.

Detalhes de instalação, execução, avaliação, treinamento e limitações estão em [`docs/INFOFROTA_AI.md`](docs/INFOFROTA_AI.md), [`docs/experiments.md`](docs/experiments.md) e [`training/REPORT.md`](training/REPORT.md).

## 5. Tecnologias e ferramentas

- **Frontend:** HTML5, CSS3 e JavaScript (Vanilla JS) para o MVP de interface.
- **Banco de dados:** MySQL na modelagem da plataforma operacional; SQLite no ambiente experimental do InfoFrota AI.
- **IA e dados:** Python, Llama 3.1 8B Instruct, Hugging Face, PEFT, QLoRA/LoRA e SQL.
- **Treinamento e avaliação:** Kaggle, scripts de geração de datasets e benchmark Text-to-SQL.
- **Integração planejada:** API, RAG e n8n.

## 6. Indicadores e impacto esperado

Uma estimativa preliminar da equipe apontou potencial de aproximadamente **7% de redução em custos associados à alocação de frota/combustível**, baseada em uma hipótese de melhor aproveitamento de rotas em sete linhas. Esse número **não é resultado medido, não foi validado em operação e não deve ser interpretado como economia alcançada**. A validação depende de dados reais, metodologia comparativa e avaliação com o operador.

## 7. Contexto de desenvolvimento

O InfoFrota é desenvolvido colaborativamente por uma equipe de quatro integrantes; David Évora atua como vice-líder técnico. O projeto foi apresentado em evento de inovação e houve contato inicial com o Núcleo de Inteligência e Análise de Dados (NIAD) da CETURB/ES, que solicitou informações sobre a obtenção, o tratamento e o uso dos dados para avaliar o possível encaminhamento interno. Esse contato não significa aprovação, contratação, parceria formal ou implantação.

## 8. Demonstração visual

A página estática em [`docs/index.html`](docs/index.html) permite navegar por uma representação inicial do dashboard: visão geral, linhas, frota, relatórios e assistente de IA. Os valores, alertas, veículos, curvas e posições exibidos são **fictícios e ilustrativos**. Os controles servem para demonstrar a experiência de navegação; não consultam serviços externos nem executam SQL.

Para visualizar localmente, basta abrir `docs/index.html` no navegador. Para publicar com GitHub Pages:

1. Abra **Settings → Pages** no repositório.
2. Em **Build and deployment**, selecione **Deploy from a branch**.
3. Escolha a branch `main` e a pasta `/docs`.
4. Salve. Após a publicação, o endereço esperado é `https://david-evora.github.io/InfoFrota/`.

## 9. Próximas etapas

1. Validar tecnicamente a solução de captação de ocupação e os requisitos de instalação, privacidade e conectividade.
2. Consolidar o dicionário de dados e documentar a relação entre a modelagem MySQL da plataforma e a base SQLite experimental.
3. Evoluir o dashboard e conectar a interface a uma API real, com autenticação e controle de acesso.
4. Implementar RAG para recuperar esquema, relacionamentos e valores categóricos relevantes para o Text-to-SQL.
5. Integrar os componentes e fluxos de processamento com n8n, avaliando latência, segurança e observabilidade.
6. Comparar os resultados do assistente sem RAG e com RAG usando o benchmark congelado e avaliações adicionais sem vazamento.
7. Validar indicadores e hipóteses de impacto com dados autorizados e metodologia acordada com o operador.

## 10. Estrutura do repositório

```text
InfoFrota/
├── README.md                   # visão geral da plataforma
├── docs/
│   ├── index.html              # demonstração web estática (GitHub Pages)
│   ├── assets/                 # CSS e JavaScript da demonstração
│   ├── architecture.md         # arquitetura geral
│   ├── architecture-infofrota-ai.md
│   ├── INFOFROTA_AI.md         # documentação do módulo de IA
│   └── experiments.md          # avaliação LoRA
├── infofrota_ai/               # código Python do módulo Text-to-SQL
├── db/                         # schema SQLite experimental
├── scripts/                    # geração de dados e datasets
├── evaluation/                 # benchmark e relatórios
├── training/                  # datasets e relatório do LoRA
├── kaggle/                    # script e instruções de treinamento
└── tests/                      # testes automatizados
```

## Dados, privacidade e responsabilidade

- Os dados operacionais usados nos experimentos de IA são majoritariamente sintéticos e não representam a operação real do Transcol.
- O CSV com rótulos das linhas não é distribuído. Só utilize uma cópia cuja origem e autorização de uso possam ser verificadas.
- Não publique dados pessoais, imagens de passageiros, placas identificáveis, credenciais, tokens ou dados operacionais não autorizados.
- Qualquer futura solução com câmeras deve passar por avaliação de privacidade, segurança, retenção, acesso e conformidade legal antes de testes em campo.
- A demonstração web não representa monitoramento em tempo real e não está integrada a sensores ou sistemas da CETURB/ES.

## Licença

Nenhuma licença foi definida até o momento. A visualização pública do código não concede automaticamente permissão para reutilização, modificação ou redistribuição. Uma licença deverá ser escolhida antes de abrir contribuições ou autorizar reutilização por terceiros.
