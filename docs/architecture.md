# Arquitetura geral do InfoFrota

Este documento descreve a arquitetura proposta para a plataforma completa e diferencia o que já existe do que ainda precisa ser validado ou integrado.

## Visão conceitual

```text
CAMADA DE CAPTAÇÃO (planejada)
Câmera embarcada / unidade compacta → contagem de fluxo e estimativa de ocupação
                    │
                    ▼
CONECTIVIDADE E SINCRONIZAÇÃO (planejada)
Rede disponível / conectividade própria → buffer local → sincronização
                    │
                    ▼
CAMADA DE DADOS
MySQL da plataforma operacional → linhas, veículos, viagens, registros e alertas
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
CAMADA ANALÍTICA          CAMADA DE IA
Agregações, relatórios    InfoFrota AI (Text-to-SQL)
calendário e clima        LLM + LoRA; RAG planejado
          │                   │
          └─────────┬─────────┘
                    ▼
APLICAÇÃO
Dashboard web → indicadores, linhas, frota, alertas e relatórios
                    │
                    ▼
APOIO AO PLANEJAMENTO
Análise de demanda e subsídios para decisões operacionais
```

O diagrama é uma visão-alvo. Os blocos de captação, conectividade, integração de produção e inferência via interface ainda não estão conectados em um sistema operacional.

## Componentes e situação

| Componente | Descrição | Situação |
|---|---|---|
| Captação embarcada | Estimar embarques, desembarques e ocupação por meio de visão computacional | Conceito em estudo; hardware, posicionamento e precisão ainda não validados |
| Conectividade | Enviar registros e sincronizar dados após períodos offline | Requisito arquitetural; integração pendente |
| Banco operacional | Modelagem MySQL com tabelas de domínio, triggers, stored procedures, scheduled events e views agregadas | Modelagem desenvolvida; DDL integral ainda não publicado; não é o banco SQLite do experimento de IA |
| Dashboard | MVP frontend vanilla HTML/CSS/JavaScript | Protótipo de interface; sem backend operacional |
| InfoFrota AI | Assistente Python que gera SQL para uma base SQLite controlada | Implementado via CLI; não integrado ao dashboard |
| RAG | Recuperar esquema, relacionamentos e valores para melhorar o contexto do LLM | Planejado |
| Orquestração/API | Integrar chamadas, recuperação, inferência e interface | Planejado; n8n em avaliação |

## Banco operacional e banco experimental

A modelagem MySQL da plataforma foi pensada para representar o domínio operacional e inclui mecanismos de automação e agregação. O DDL integral não consta do pacote público atual e deverá ser adicionado após revisão. O módulo InfoFrota AI usa uma **adaptação em SQLite** para experimentação controlada: simplifica o ambiente, usa dados sintéticos e permite avaliar consultas Text-to-SQL de forma reproduzível. O schema em `db/schema.sql` é o schema SQLite do módulo de IA, não a modelagem MySQL integral da plataforma.

## Fluxo pretendido dos dados

1. Uma unidade embarcada estima o fluxo de passageiros e a ocupação do veículo.
2. Os registros são associados a veículo, linha, viagem, horário e ponto/local de referência.
3. O sistema transmite os registros; em falhas de conectividade, mantém dados temporariamente para sincronização posterior, caso a solução seja validada.
4. A camada de dados armazena eventos e gera agregações por linha, horário, dia e parada.
5. O dashboard apresenta indicadores e histórico; análises podem considerar calendário e clima.
6. O InfoFrota AI permite explorar dados por perguntas em linguagem natural, depois de integrado a uma camada de contexto e API.

## Segurança e privacidade a considerar

Antes de qualquer teste com passageiros ou operação real, a equipe deverá avaliar minimização de dados, processamento local, retenção, descarte, controle de acesso, criptografia, logs, segurança física dos dispositivos e base legal aplicável. A demonstração atual não coleta imagens, não identifica passageiros e não transmite dados.

## Arquitetura específica do InfoFrota AI

Consulte [`architecture-infofrota-ai.md`](architecture-infofrota-ai.md) para o fluxo já implementado de pergunta → prompt/esquema → LLM → validação → SQLite somente leitura → resultado.
