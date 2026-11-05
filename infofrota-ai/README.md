# InfoFrota AI

**Assistente experimental de Text-to-SQL para exploração de dados de transporte coletivo.** O projeto recebe perguntas em português, gera consultas SQL com um modelo de linguagem, aplica uma camada de segurança, executa consultas somente leitura em SQLite e apresenta os resultados.

> **Estado do projeto (05/11/2026):** núcleo Text-to-SQL e CLI implementados; conjunto de avaliação v2.1 disponível; fine-tuning experimental com QLoRA/LoRA concluído. RAG, orquestração com n8n, API e interface web ainda estão planejados — não fazem parte da implementação atual.

## Resultado experimental atual

Avaliação zero-shot, com prompt compacto e 56 perguntas na versão v2.1:

| Modelo | Fácil | Médio | Difícil | Limite | Total | Exata |
|---|---:|---:|---:|---:|---:|---:|
| Llama 3.1 8B Instruct (base) | 9/15 | 5/20 | 0/15 | 5/6 | 19/56 (**33,9%**) | 30,4% |
| Llama 3.1 8B Instruct + LoRA | 13/15 | 13/20 | 4/15 | 6/6 | 36/56 (**64,3%**) | 58,9% |

O ganho observado foi de **30,4 pontos percentuais** na métrica principal. O conjunto de teste é separado dos dados usados no fine-tuning; o relatório de treinamento documenta filtros de similaridade e de estrutura SQL.

**Interpretação:** resultado experimental em um banco e conjunto de perguntas controlados. Não representa desempenho em produção nem em dados operacionais reais. Um defeito conhecido na pergunta D06 faz com que uma resposta correta seja contabilizada como erro; os números acima foram mantidos sem ajuste posterior à avaliação. Consulte os relatórios completos em [`evaluation/runs/`](evaluation/runs/) e o histórico em [`evaluation/CHANGELOG.md`](evaluation/CHANGELOG.md).

## O que está implementado

- Assistente Text-to-SQL em Python com interface de linha de comando.
- Integração com provedores Anthropic e APIs compatíveis com OpenAI Chat Completions.
- Esquema SQLite e gerador determinístico de dados sintéticos.
- Avaliação automatizada com 56 perguntas em português e comparação de resultados SQL.
- Geração de exemplos de treinamento com filtros para reduzir sobreposição com o conjunto de teste.
- Fine-tuning QLoRA/LoRA do Llama 3.1 8B Instruct executado no Kaggle.
- Execução SQL somente leitura, com authorizer SQLite, limite de linhas e timeout.
- Uma tentativa de reparo quando a consulta gerada falha por erro de execução.

## Arquitetura atual

```text
Pergunta em português
        |
        v
Prompt + esquema do banco
        |
        v
LLM (provedor configurado)
        |
        v
Interpretação da resposta / SQL
        |
        v
Validação de segurança
        |
        v
SQLite em modo somente leitura
        |
        v
Resultado tabular + resposta textual
```

A arquitetura e os componentes planejados estão descritos em [`docs/architecture.md`](docs/architecture.md).

## Dados e responsabilidade

O banco usado nos experimentos é **majoritariamente sintético**. Frota, viagens, leituras de ocupação, alertas e clima são gerados pelo script `scripts/generate_data.py`, com semente fixa. Esses valores não representam a operação real dos ônibus.

O gerador também utiliza um CSV de linhas e rótulos de transporte (`data/linhas_ceturbes.csv`). Esse arquivo **não é distribuído neste repositório**. Para gerar o banco, obtenha uma cópia que você tenha autorização para usar e coloque-a localmente em `data/linhas_ceturbes.csv`, com as colunas `Linha` e `Rotulo`. Consulte [`data/README.md`](data/README.md). O arquivo local está no `.gitignore` para evitar publicação inadvertida.

As coordenadas de algumas paradas do protótipo são aproximadas; os itinerários e dados de operação simulados não devem ser interpretados como trajetos ou indicadores oficiais.

Este é um projeto independente de prototipagem e pesquisa. Não é um produto oficial nem representa endosso de órgão ou operador de transporte.

## Como preparar o ambiente

Requisitos: Python 3.10 ou superior. O núcleo usa a biblioteca padrão; o pacote `anthropic` é necessário apenas para usar o provedor Anthropic.

```bash
git clone <URL_DO_REPOSITORIO>
cd infofrota-ai
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Coloque o CSV autorizado em `data/linhas_ceturbes.csv` e gere o banco de dados:

```bash
python scripts/generate_data.py
python scripts/build_eval_set.py --show
```

O banco resultante será salvo em `data/infofrota.db` e não deve ser versionado.

## Como executar o assistente

### API compatível com OpenAI

Configure as variáveis de ambiente de acordo com seu servidor/modelo:

```bash
# Exemplo para servidor local compatível com OpenAI
# PowerShell:
$env:OPENAI_BASE_URL = "http://localhost:8000/v1"
$env:OPENAI_API_KEY = "sua-chave-se-for-necessaria"

# Bash:
export OPENAI_BASE_URL="http://localhost:8000/v1"
export OPENAI_API_KEY="sua-chave-se-for-necessaria"
```

Execute uma pergunta:

```bash
python -m infofrota_ai --provider openai --model NOME_DO_MODELO "Quais linhas têm mais alertas críticos?"
```

### Anthropic

Configure `ANTHROPIC_API_KEY` no ambiente e execute:

```bash
python -m infofrota_ai --provider anthropic --model NOME_DO_MODELO "Quais linhas têm mais alertas críticos?"
```

Não coloque chaves de API diretamente no código ou no Git.

## Avaliação

O conjunto de avaliação congelado está em `evaluation/questions.json`. Ele contém 56 perguntas, SQLs de referência e resultados esperados. **Não use esse arquivo como fonte de recuperação do RAG nem como dado de treinamento**, pois isso contaminaria futuras avaliações.

```bash
# Exemplo usando API compatível com OpenAI
python -m infofrota_ai.evaluate --provider openai --model NOME_DO_MODELO \
  --base-url http://localhost:8000/v1 --shots 0

# Testes automatizados (após gerar o banco local)
python -m unittest discover -s tests -v
```

Métricas:
- **Acurácia:** o resultado contém os valores esperados; colunas adicionais não invalidam a resposta.
- **Exata:** o resultado coincide integralmente, sem colunas adicionais.

Resultados de versões diferentes do conjunto de avaliação não são diretamente comparáveis. Consulte o changelog antes de comparar experimentos.

## Treinamento LoRA

O conjunto de treinamento usado na experiência está em `training/`; o relatório de composição e anti-vazamento está em [`training/REPORT.md`](training/REPORT.md). O script de treinamento para Kaggle está em `kaggle/train_lora.py`, com instruções em `kaggle/LEIAME.md`.

O adaptador treinado e os checkpoints **não estão incluídos** neste repositório, por tamanho. O repositório contém os dados e relatórios necessários para documentar a experiência, mas a reprodução do fine-tuning exige ambiente GPU e instalação das dependências descritas no notebook/script. No Kaggle, o CSV de linhas deve ser adicionado como um segundo input, preferencialmente privado; veja `kaggle/LEIAME.md`.

## Próximas etapas

1. Implementar RAG para recuperar esquema, relacionamentos e valores categóricos relevantes.
2. Comparar Text-to-SQL sem RAG e com RAG no mesmo conjunto de avaliação congelado.
3. Integrar o fluxo de processamento e inferência ao n8n.
4. Criar API e interface web para demonstrar o ciclo pergunta → SQL → resultado.
5. Avaliar novamente com perguntas adicionais mantidas fora do conjunto de desenvolvimento.

## Estrutura do repositório

```text
infofrota-ai/
├── data/                 # instruções; banco e CSV local não versionados
├── db/schema.sql         # esquema SQLite
├── docs/                 # arquitetura e histórico experimental
├── evaluation/           # benchmark v2.1 e relatórios
├── infofrota_ai/         # assistente, provedores, SQL e CLI
├── kaggle/               # script e instruções do fine-tuning
├── scripts/              # geração de dados e datasets
├── tests/                # testes automatizados
└── training/             # datasets e relatório do LoRA
```

## Licença

Nenhuma licença de código foi definida até o momento. A publicação do repositório permite consultar o conteúdo, mas não concede automaticamente permissões de reutilização ou redistribuição. Defina uma licença antes de convidar terceiros a reutilizar o projeto.
