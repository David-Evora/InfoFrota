# Arquitetura do InfoFrota AI

## Implementado atualmente

1. **Entrada:** pergunta em linguagem natural em português pela CLI ou pelo endpoint `POST /perguntar`.
2. **Contexto:** prompt montado a partir do esquema SQLite e de regras do domínio; o RAG recupera tabelas/views, valores categóricos e regras relevantes.
3. **Geração:** provedor LLM gera SQL em formato estruturado.
4. **Interpretação:** assistente extrai e normaliza a consulta SQL.
5. **Proteção:** consulta passa por checagem de instrução única, authorizer SQLite e conexão `mode=ro`.
6. **Execução:** banco limita linhas retornadas e interrompe consultas que excedem o timeout configurado.
7. **Reparo:** em caso de erro SQL de execução, o modelo pode receber o erro e tentar corrigir a consulta uma vez.
8. **Resposta:** resultados apresentados em formato tabular e, opcionalmente, resumidos em texto.
9. **API:** FastAPI expõe `/saude`, `/perguntar`, `/alertas` e `/resumo`.
10. **Automação:** n8n consulta `/alertas` periodicamente e envia notificações para um webhook configurado localmente.

## Componentes principais

| Caminho | Responsabilidade |
|---|---|
| `infofrota_ai/assistant.py` | Orquestra pergunta, LLM, execução e reparo |
| `infofrota_ai/db.py` | Acesso SQLite e proteção de consultas |
| `infofrota_ai/prompts.py` | Esquema, instruções e exemplos do prompt |
| `infofrota_ai/llm.py` | Provedores Anthropic e OpenAI-compatible |
| `infofrota_ai/rag.py` | Índice BM25 para esquema, valores e regras |
| `infofrota_ai/api.py` | Endpoints HTTP |
| `infofrota_ai/hf_llm.py` | Carregamento local de modelo Hugging Face e adaptador PEFT |
| `infofrota_ai/evaluate.py` | Execução do benchmark e geração de relatórios |
| `scripts/generate_data.py` | Geração de banco com dados sintéticos |
| `n8n/alerta-critico.json` | Workflow de notificação de alertas |

## Topologia Docker

```text
n8n ── HTTP interno (http://api:8000) ──> FastAPI
                                         ├── SQLite experimental
                                         └── provedor LLM externo

n8n ── webhook ──> Discord/Slack
```

O Compose atual publica a interface do n8n em localhost e mantém a API sem porta publicada no host. A chave do provedor LLM é carregada no contêiner da API por arquivo de ambiente local.

## Ainda não implementado ou validado

- Captação real de passageiros por câmera/sensor.
- Conectividade embarcada e sincronização offline.
- Integração com dados operacionais autorizados.
- Integração do dashboard estático à API.
- Autenticação/autorização e hardening completos para produção.
- Validação de desempenho e segurança em ambiente operacional real.

## Fronteira de segurança

O módulo SQLite foi projetado para executar apenas leituras, usando conexão em modo somente leitura, authorizer e limites de execução. Isso reduz riscos de comandos gerados pelo modelo, mas não substitui revisão de segurança, isolamento de infraestrutura, autenticação, controle de acesso e testes antes de qualquer implantação real.
