# Alerta de lotação crítica no n8n

O workflow `alerta-critico.json` consulta a API a cada cinco minutos:

`GET http://api:8000/alertas?tipo=CRITICO&janela_horas=24&limite=10`

Se houver alertas, monta uma mensagem e envia para o webhook configurado (Discord ou Slack, conforme o formato usado).

## Importação

1. Inicie a API e o n8n com `docker compose up -d --build`.
2. Acesse `http://localhost:5678`.
3. Importe `alerta-critico.json` em **Workflows > Import from File**.
4. No nó **Configuração**, confirme `api_base_url` como `http://api:8000`.
5. Insira localmente a URL do webhook em `webhook_url`. Não faça commit dessa URL.
6. Deixe `api_key` vazia, a menos que tenha configurado `INFOFROTA_API_KEY` no backend. Essa chave é interna e não é a chave Groq.
7. Execute um teste e, depois de validar, ative o workflow.

## Deduplicação

A versão atual `alerta-critico.json` fornecida neste pacote filtra alertas pelo ID e grava os IDs após a confirmação de sucesso do webhook. Ela usa o armazenamento estático do workflow. A persistência deve ser validada na versão instalada do n8n com o workflow ativo; testes manuais não devem ser usados para concluir que o histórico foi persistido.

A primeira execução de produção após importar a v2 pode enviar uma notificação inicial para os alertas ainda não registrados.

## Dados demonstrativos

A base atual usa dados sintéticos. A rota `/alertas` usa por padrão o horário do último alerta no banco como referência temporal. Por isso, alertas demonstrativos podem continuar aparecendo em execuções sucessivas. Isso não significa que novos eventos reais estejam chegando.

## Segurança

- A chave Groq/OpenAI-compatible fica apenas no `.env.api`, dentro do backend.
- Nunca coloque a chave do provedor LLM em nós do n8n.
- O campo `api_key` é opcional e corresponde somente a `INFOFROTA_API_KEY`.
- Não versione URL de webhook do Discord/Slack.
- A API deve permanecer em rede privada até que autenticação, TLS e controles de acesso apropriados sejam definidos.
