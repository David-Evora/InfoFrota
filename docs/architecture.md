# Arquitetura geral do InfoFrota

Este documento separa a arquitetura de desenvolvimento já executável dos componentes operacionais que ainda precisam ser validados.

## 1. Arquitetura de desenvolvimento atual

```text
                         ┌─────────────────────────┐
                         │ n8n (Docker)            │
                         │ Schedule Trigger        │
                         │ consulta /alertas       │
                         └────────────┬────────────┘
                                      │ HTTP interno
                                      │ http://api:8000
                                      ▼
                         ┌─────────────────────────┐
                         │ FastAPI (Docker)        │
                         │ /saude                  │
                         │ /perguntar              │
                         │ /alertas                │
                         │ /resumo                 │
                         └──────┬──────────┬───────┘
                                │          │
                                ▼          ▼
                     ┌──────────────┐  ┌────────────────┐
                     │ SQLite       │  │ Provedor LLM   │
                     │ experimental│  │ Groq/OpenAI    │
                     │ somente leitura│ │ compatible    │
                     └──────────────┘  └────────────────┘

n8n ── webhook HTTP ──> Discord ou Slack
```

A API é acessível pelo n8n na rede interna Docker. A porta 8000 é publicada apenas no loopback do host (`127.0.0.1:8000`), onde a API serve a interface web. A interface do n8n é publicada localmente em `127.0.0.1:5678`.

## 2. Componentes e situação

| Componente | Descrição | Situação |
|---|---|---|
| Captação embarcada | Estimar embarques, desembarques e ocupação por visão computacional | Conceito em estudo; hardware e precisão não validados |
| Conectividade embarcada | Buffer local e sincronização após períodos offline | Requisito arquitetural; integração pendente |
| Banco operacional | Modelagem MySQL para domínio operacional | Modelagem desenvolvida; não é o SQLite experimental |
| Base experimental | SQLite com dados sintéticos | Gerada localmente para desenvolvimento e avaliação |
| Dashboard | HTML, CSS e JavaScript | MVP estático; não consulta a API atualmente |
| InfoFrota AI | Text-to-SQL com RAG de esquema | Implementado em módulo experimental |
| API | FastAPI com quatro rotas | Implementada e executada em Docker |
| Automação | n8n consulta alertas críticos e notifica webhook | Workflow testado manualmente na instância; sem teste automatizado |
| Operação real | Sensores, dados operacionais e sistemas externos | Não implementada nem validada |

## 3. Diferença entre os bancos

A modelagem MySQL representa a proposta de domínio operacional. O módulo InfoFrota AI utiliza um schema SQLite simplificado, com dados sintéticos, para avaliação controlada de Text-to-SQL. `db/schema.sql` corresponde ao banco experimental SQLite, não ao DDL integral da plataforma operacional.

## 4. Segurança e privacidade

O assistente restringe consultas ao SQLite em modo somente leitura, com authorizer, limite de linhas e timeout. Esses controles não substituem autenticação, autorização, isolamento de infraestrutura e revisão de segurança.

Antes de qualquer teste com passageiros ou operação real, avaliar minimização de dados, processamento local, retenção, descarte, controle de acesso, criptografia, logs, segurança física dos dispositivos e base legal aplicável. A demonstração atual não coleta imagens nem identifica passageiros.
