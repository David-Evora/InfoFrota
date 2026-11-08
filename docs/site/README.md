# Site do InfoFrota

Este é o único frontend do InfoFrota. É uma página de apresentação estática, construída com HTML, CSS e JavaScript puros, sem etapa de build, framework ou dependência de CDN. A API FastAPI também serve esse mesmo site na raiz (`/`).

## Como executar com a API

Na raiz do repositório:

```bash
python -m infofrota_ai.api
```

Acesse `http://127.0.0.1:8000/`. Os endpoints da API (`/saude`, `/perguntar`, `/alertas` e `/resumo`) continuam disponíveis na mesma origem.

## Como executar somente o site estático

Na raiz do repositório:

```bash
python -m http.server -d docs/site 8080
```

Acesse `http://127.0.0.1:8080/`. Sem a API, o site funciona em modo de demonstração; a interação com o backend não fica disponível.

## Publicação no GitHub Pages

O workflow `.github/workflows/deploy-pages.yml` publica o conteúdo de `docs/site/` na raiz do GitHub Pages. A origem do Pages deve estar configurada como **GitHub Actions** em Settings → Pages.

## Estrutura

- `index.html`: marcação, metadados de SEO e Open Graph, sprite de ícones embutido.
- `assets/css/`: tokens de design, base, componentes e seções.
- `assets/js/`: núcleo, navegação e módulos de cada seção, incluindo catálogo de funcionalidades e arquitetura interativa.
- `assets/data/snapshot.js`: instantâneo gerado por `scripts/build_site_snapshot.py` a partir do banco sintético. Para atualizar: `python scripts/generate_data.py && python scripts/build_site_snapshot.py`.
- `assets/img/`: favicon, imagem Open Graph e recursos visuais locais.
- `assets/fonts/`: fontes locais; consulte `assets/NOTICE.md` para os avisos de licença.

## O que é real e o que é simulado

Real, vindo do repositório:

- Os números dos gráficos, a tabela de resultados e o contexto recuperado pelo RAG nas demonstrações são calculados ou executados sobre o banco SQLite sintético, com o índice BM25 e a guarda de SQL do próprio repositório.
- O catálogo de funcionalidades cita arquivos existentes, conferidos por `tests/test_site.py`.
- Os nós do workflow n8n espelham `n8n/alerta-critico.json`.
- O modo ao vivo da demonstração de IA só aparece quando `GET /saude` responde na mesma origem. Então o campo de pergunta chama `POST /perguntar` da API. A chave do modelo permanece no backend.
- Os resultados do benchmark são os registrados em `docs/experiments.md`.

Simulado e identificado como tal na página:

- As conversas pré-gravadas do assistente usam SQL e texto preparados para demonstração; o modelo de linguagem não é chamado nesse modo.
- A execução visual do workflow n8n usa alertas do snapshot; não consulta a API nem dispara webhook.
- Os veículos ilustrados não representam posições GPS reais.
- As capturas do painel são demonstrações com dados sintéticos.

## Limitações

- Os dados operacionais exibidos são sintéticos. A página não mostra operação real, clientes, parceiros, depoimentos ou métricas de desempenho em campo.
- A demonstração ao vivo depende de a API estar disponível na mesma origem e sem uma chave obrigatória que o navegador não possa fornecer.
- A deduplicação do workflow n8n ainda precisa ser validada com o workflow ativo; por isso aparece como em validação.
- O site de apresentação não substitui a infraestrutura de backend: o GitHub Pages hospeda somente os arquivos estáticos.
