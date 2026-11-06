# InfoFrota

**Plataforma em desenvolvimento para inteligência operacional do transporte coletivo na Grande Vitória (Transcol).** O InfoFrota propõe reunir dados de ocupação, frota, linhas, horários e fatores externos em uma visão integrada para apoiar o planejamento e a tomada de decisão.

> **Estado do projeto — novembro de 2026:** o repositório reúne um MVP de interface web estática, uma base experimental SQLite com dados sintéticos, o módulo InfoFrota AI (Text-to-SQL com RAG de esquema), uma API FastAPI e uma integração de automação com n8n para consulta periódica de alertas e notificação via webhook (Discord/Slack). A infraestrutura de desenvolvimento pode ser executada com Docker Compose. A captação embarcada de passageiros e a operação com dados reais continuam em fase de estudo e validação.

## 1. Objetivo

O InfoFrota busca transformar registros de transporte coletivo em informações acessíveis para análise e apoio à decisão. A proposta contempla:

- acompanhamento de indicadores de ocupação por linha, veículo, região e faixa horária;
- identificação de padrões de demanda, horários de pico e situações críticas;
- consolidação de histórico operacional para relatórios e análises comparativas;
- exploração de relações entre demanda, calendário e condições climáticas;
- consultas em linguagem natural sobre a base experimental por meio do InfoFrota AI.

O InfoFrota é um projeto independente em desenvolvimento. Não é um sistema oficial da CETURB/ES e não possui endosso institucional declarado.

## 2. Estado dos módulos

| Módulo | Situação |
|---|---|
| Captação embarcada | Conceito em estudo; hardware, posicionamento, privacidade e precisão ainda precisam ser validados |
| Banco operacional | Modelagem MySQL desenvolvida como base de projeto; não confundir com o SQLite experimental do módulo de IA |
| Base experimental | SQLite gerado localmente com dados sintéticos |
| Dashboard | MVP frontend em HTML, CSS e JavaScript; demonstração estática com dados ilustrativos |
| InfoFrota AI | Assistente Python Text-to-SQL, com RAG de esquema e avaliação experimental |
| API | FastAPI com `/saude`, `/perguntar`, `/alertas` e `/resumo` |
| Automação | Workflow n8n de consulta de alertas críticos e envio de notificação por webhook |
| Integração operacional | Ainda não conectada a sensores, frota real ou sistemas da CETURB/ES |

## 3. Arquitetura de desenvolvimento

```text
n8n (Docker)
   |
   | HTTP interno: http://api:8000
   v
FastAPI (Docker) ----> SQLite experimental (somente leitura)
   |
   v
Provedor LLM (Groq ou outro compatível com OpenAI API)

n8n Schedule Trigger ---> GET /alertas ---> filtro/formatacao ---> Discord/Slack webhook
```

No `compose.yaml`, a API é exposta somente à rede Docker (`expose: 8000`), sem publicar a porta 8000 no host. O n8n acessa a API pelo nome do serviço `api`. A interface do n8n é publicada em `127.0.0.1:5678`.

A chave do provedor LLM deve permanecer no ambiente do backend (`.env.api`), nunca em nós ou credenciais do n8n. `INFOFROTA_API_KEY`, quando habilitada, é uma chave interna opcional para autenticar chamadas à API e é diferente da chave Groq.

## 4. Executar com Docker Compose

Requisitos: Docker Desktop com Docker Compose e o arquivo local `data/infofrota.db` gerado pelo projeto.

1. Clone o repositório e entre na pasta:

   ```bash
   git clone https://github.com/David-Evora/InfoFrota.git
   cd InfoFrota
   ```

2. Crie o arquivo local de ambiente:

   ```powershell
   Copy-Item .env.example .env.api
   notepad .env.api
   ```

   Preencha a chave do provedor LLM e confira o modelo e a URL-base compatíveis com sua conta.

3. Gere a base experimental se ela ainda não existir:

   ```bash
   python scripts/generate_data.py
   ```

4. Inicie os serviços:

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

5. Acesse o n8n em `http://localhost:5678`. A API permanece interna à rede Docker; de dentro do n8n, use `http://api:8000`.

Para consultar logs:

```bash
docker compose logs --tail 80 api
docker compose logs --tail 80 n8n
```

O workflow n8n está em `n8n/alerta-critico.json`. Importe-o pela opção **Import from File**, revise os valores do nó **Configuração**, teste e então ative. O webhook de notificação deve ser inserido localmente na instância; não publique URLs de webhook no Git.

## 5. API

A documentação interativa da API fica em `/docs` quando executada localmente. Os endpoints atuais são:

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/saude` | Estado do serviço e período dos dados |
| POST | `/perguntar` | Recebe pergunta em português e retorna resultado Text-to-SQL |
| GET | `/alertas` | Consulta alertas por tipo, janela e limite |
| GET | `/resumo` | Retorna resumo diário por linha |

Exemplo de corpo para `POST /perguntar`:

```json
{
  "pergunta": "Quais linhas têm mais alertas críticos?",
  "texto": false
}
```

A rota `/perguntar` exige pergunta entre 3 e 500 caracteres. `texto` é opcional e, quando verdadeiro, solicita também uma resposta em linguagem natural.

## 6. InfoFrota AI, RAG e avaliação

O módulo recebe perguntas em português, recupera contexto do esquema SQLite e das regras do domínio, solicita SQL ao provedor LLM, valida a consulta e executa leitura no banco experimental. A proteção inclui execução SQLite em modo somente leitura, authorizer, limite de linhas e timeout.

O RAG de esquema recupera tabelas/views, valores categóricos e regras relevantes. O benchmark congelado e os relatórios experimentais ficam em `evaluation/`; não use perguntas de avaliação como fonte de recuperação ou treinamento, para evitar vazamento.

Os resultados de avaliação são experimentais e restritos à base e às perguntas controladas. Não representam desempenho em produção ou sobre dados reais de transporte.

Consulte:
- [`docs/INFOFROTA_AI.md`](docs/INFOFROTA_AI.md)
- [`docs/architecture-infofrota-ai.md`](docs/architecture-infofrota-ai.md)
- [`docs/experiments.md`](docs/experiments.md)
- [`training/REPORT.md`](training/REPORT.md)

## 7. Dados e limitações

O banco `data/infofrota.db` é gerado localmente e não deve ser versionado. Frota, viagens, leituras de ocupação, clima e alertas são dados sintéticos.

O arquivo `data/linhas_ceturbes.csv` contém rótulos de linhas provenientes do conjunto público [Rótulos das Linhas](https://dados.es.gov.br/dataset/rotulos-das-linhas), cuja licença indicada para esse conjunto específico é CC0. Essa licença não deve ser confundida com a licença do código do projeto.

Não adicione dados pessoais, imagens de passageiros, credenciais ou dados operacionais sem autorização. A proposta de câmera embarcada ainda exige avaliação técnica, de privacidade, retenção e base legal antes de qualquer teste com passageiros.

## 8. Segurança

- Não versione `.env.api`, tokens, chaves, arquivos `.pem` ou `.key`.
- Mantenha a chave do provedor LLM exclusivamente no backend.
- Não publique a porta da API sem uma necessidade arquitetural e controles apropriados.
- Se habilitar `INFOFROTA_API_KEY`, configure a mesma chave interna no cliente autorizado; não reutilize a chave Groq.
- Faça backup do volume `n8n_data` e dos dados locais relevantes.
- A configuração atual é de desenvolvimento; antes de produção, revise autenticação, autorização, TLS, atualização de imagens, logs, retenção, backups e exposição de rede.

## 9. Estrutura do repositório

```text
InfoFrota/
├── LICENSE
├── README.md
├── .env.example
├── Dockerfile.api
├── compose.yaml
├── data/                  # CSV público e banco SQLite local ignorado
├── db/                    # schema SQLite experimental
├── docs/                  # arquitetura, experimentos e documentação
├── evaluation/            # benchmark e relatórios
├── infofrota_ai/          # assistente, RAG, API e provedores
├── n8n/                   # workflows e instruções de importação
├── scripts/               # geração de dados e datasets
├── tests/                 # testes automatizados
└── training/              # datasets e relatório de fine-tuning
```

## 10. Licença

O código e a documentação originais deste repositório são disponibilizados sob a licença MIT. Consulte [`LICENSE`](LICENSE).

A licença MIT não substitui licenças ou termos aplicáveis a materiais de terceiros distribuídos no repositório. Em particular, o conjunto de rótulos das linhas indicado como CC0 mantém sua identificação própria. Modelos, pesos, adaptadores, bibliotecas, serviços externos e conjuntos de dados podem possuir termos independentes.

## 11. Situação institucional

O InfoFrota é uma iniciativa independente de prototipagem e pesquisa. Contatos, apresentações ou envio de documentos a órgãos públicos não significam aprovação, contratação, parceria formal, implantação ou endosso institucional.
