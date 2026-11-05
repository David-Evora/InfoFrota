# Arquitetura do InfoFrota AI

## Implementado atualmente

1. **Entrada:** pergunta em linguagem natural em português pela CLI.
2. **Contexto:** o prompt é montado a partir do esquema SQLite e de regras do domínio.
3. **Geração:** um provedor LLM gera SQL em formato estruturado.
4. **Interpretação:** o assistente extrai e normaliza a consulta SQL.
5. **Proteção:** a consulta passa por checagem de instrução única, authorizer SQLite e conexão `mode=ro`.
6. **Execução:** o banco limita o número de linhas retornadas e interrompe consultas que excedem o timeout configurado.
7. **Reparo:** em caso de erro SQL de execução, o modelo pode receber o erro e tentar corrigir a consulta uma vez.
8. **Resposta:** os resultados são apresentados em formato tabular e podem ser resumidos em texto pelo provedor.

## Componentes principais

| Caminho | Responsabilidade |
|---|---|
| `infofrota_ai/assistant.py` | Orquestra pergunta, LLM, execução e reparo |
| `infofrota_ai/db.py` | Acesso SQLite e proteção de consultas |
| `infofrota_ai/prompts.py` | Esquema, instruções e exemplos do prompt |
| `infofrota_ai/llm.py` | Provedores Anthropic e OpenAI-compatible |
| `infofrota_ai/hf_llm.py` | Carregamento local de modelo Hugging Face e adaptador PEFT |
| `infofrota_ai/evaluate.py` | Execução do benchmark e geração de relatórios |
| `scripts/generate_data.py` | Geração de banco com dados sintéticos |
| `scripts/build_train_set.py` | Construção do conjunto de fine-tuning e filtros anti-vazamento |

## Planejado, ainda não implementado

```text
UI → API/orquestração (n8n) → recuperação RAG → LLM + LoRA
   → validação SQL → SQLite/banco → resultado para UI
```

RAG, n8n, API e UI são etapas futuras. O desenho acima é uma proposta de evolução, não uma descrição de funcionalidades já disponíveis.

## Fronteira de segurança

O módulo SQLite foi projetado para executar apenas leituras, usando conexão em modo somente leitura, authorizer e limites de execução. Isso reduz riscos de comandos gerados pelo modelo, mas não substitui revisão de segurança, isolamento de infraestrutura, autenticação, controle de acesso e testes antes de qualquer implantação real.
