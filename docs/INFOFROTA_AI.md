# InfoFrota AI

**Assistente experimental de Text-to-SQL para exploração de dados de transporte coletivo.** O módulo recebe perguntas em português, recupera contexto do esquema e das regras do domínio, gera consultas SQL com um modelo de linguagem, valida a consulta e executa leitura em SQLite.

> **Estado — novembro de 2026:** núcleo Text-to-SQL, CLI, RAG de esquema e API FastAPI implementados. A API possui rotas para saúde, perguntas, alertas e resumo. A infraestrutura de desenvolvimento inclui Docker Compose e um workflow n8n para consulta periódica de alertas e notificação por webhook. O dashboard continua sendo uma demonstração estática; não está integrado à API. A captação embarcada e a operação com dados reais não estão implementadas.

## 1. Componentes implementados

- Assistente Text-to-SQL em Python.
- Provedores Anthropic e APIs compatíveis com OpenAI Chat Completions.
- Recuperação RAG de tabelas/views, valores categóricos e regras do domínio.
- Validação de SQL e execução SQLite somente leitura.
- Benchmark experimental com perguntas em português e relatórios.
- API FastAPI com `/saude`, `/perguntar`, `/alertas` e `/resumo`.
- Dockerfile e Docker Compose para executar API e n8n.
- Workflow n8n de consulta periódica de alertas críticos e envio para webhook.

## 2. Fluxo de pergunta

```text
Pergunta em português
        |
        v
RAG: tabelas, valores e regras relevantes
        |
        v
Prompt + contexto recuperado
        |
        v
LLM (provedor configurado)
        |
        v
Interpretação e validação de SQL
        |
        v
SQLite em modo somente leitura
        |
        v
Resultado tabular (+ texto opcional)
```

O RAG usa o banco e descrições do domínio. O conjunto congelado de avaliação não deve ser usado como fonte de recuperação nem como dado de treinamento.

## 3. Dados

A base experimental é majoritariamente sintética. Frota, viagens, leituras de ocupação, alertas e clima são gerados localmente. O arquivo `data/linhas_ceturbes.csv` contém rótulos provenientes do conjunto público Rótulos das Linhas; a licença indicada para esse conjunto específico é CC0. Consulte `data/README.md`.

Os resultados dos benchmarks são experimentais e limitados ao schema e às perguntas controladas. Não representam desempenho em produção nem sobre dados operacionais reais.

## 4. API

Instalação local:

```bash
pip install -r requirements-api.txt
python -m infofrota_ai.api
```

Rotas:

| Método | Rota | Uso |
|---|---|---|
| GET | `/saude` | Estado do serviço e período dos dados |
| POST | `/perguntar` | Pergunta em português → SQL e resultado |
| GET | `/alertas` | Alertas filtrados por tipo, janela e limite |
| GET | `/resumo` | Resumo de um dia por linha |

Corpo de `POST /perguntar`:

```json
{
  "pergunta": "Quais linhas têm mais alertas críticos?",
  "texto": false
}
```

`pergunta` é obrigatória, com 3 a 500 caracteres. `texto` é opcional e, quando verdadeiro, solicita também uma resposta textual.

### Variáveis de ambiente

A configuração do provedor é feita no backend. No ambiente Docker, o arquivo local `.env.api` é carregado pelo Compose. O modelo de arquivo está em `.env.example`.

- `INFOFROTA_PROVIDER`: provedor, por exemplo `openai-compat`.
- `INFOFROTA_MODEL`: identificador do modelo no provedor.
- `OPENAI_BASE_URL`: URL-base compatível com OpenAI.
- `OPENAI_API_KEY`: chave privada do provedor LLM.
- `INFOFROTA_PROMPT`, `INFOFROTA_RAG`, `INFOFROTA_SHOTS`: opções do assistente.
- `INFOFROTA_DB`: caminho da base SQLite.
- `INFOFROTA_API_KEY`: chave interna opcional para exigir `X-API-Key` nos endpoints protegidos.
- `INFOFROTA_LIMITE_POR_MIN`: limite de chamadas a `/perguntar` por minuto e por IP.

A chave `OPENAI_API_KEY` fica exclusivamente no backend; não deve ser copiada para nós do n8n. `INFOFROTA_API_KEY`, se habilitada, é uma chave interna distinta.

## 5. Docker e n8n

Com Docker Desktop e Docker Compose:

```powershell
Copy-Item .env.example .env.api
notepad .env.api
python scripts/generate_data.py
docker compose up -d --build
docker compose ps
```

O n8n fica em `http://localhost:5678`. A API é acessada internamente pelo n8n em `http://api:8000`; a porta 8000 não é publicada no host na configuração Compose atual.

O workflow de alertas fica em `n8n/alerta-critico.json`. Importe pelo n8n, configure localmente a URL do webhook no nó **Configuração**, teste e ative. Não versione URLs reais de webhook.

O workflow consulta `GET /alertas` a cada cinco minutos, filtra alertas críticos e envia notificações. A versão com deduplicação usa o armazenamento estático do workflow; confirme o comportamento de persistência na versão instalada do n8n e teste com o workflow ativo antes de depender dela em operação contínua.

## 6. Segurança e limites

- As consultas ao banco experimental são somente leitura, com authorizer, limite de linhas e timeout.
- A API e o n8n estão isolados em rede Docker de desenvolvimento.
- A configuração atual não deve ser considerada pronta para produção.
- Antes de produção, revisar autenticação, autorização, TLS, exposição de rede, logs, retenção, backups, atualização de imagens e política de credenciais.
- Não colocar chaves ou URLs secretas de webhook no código ou no Git.

## 7. Avaliação e treinamento

Consulte `evaluation/`, `training/REPORT.md`, `docs/experiments.md` e `kaggle/LEIAME.md`. Os adaptadores e checkpoints treinados podem não estar incluídos no repositório por tamanho; confira as instruções de reprodução.

## 8. Licença

O código e a documentação originais deste repositório estão sob MIT. Materiais de terceiros, datasets, bibliotecas, modelos e serviços externos permanecem sujeitos a seus próprios termos. Consulte `LICENSE` e `data/README.md`.
