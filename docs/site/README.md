# Site do InfoFrota

Página de apresentação do projeto, em HTML, CSS e JavaScript puros. Não há etapa de build, framework nem dependência de CDN: fontes e ícones são locais.

## Como rodar

Com a API (serve em `/site/`):

    uvicorn infofrota_ai.api:create_app --factory --port 8000
    # abra http://127.0.0.1:8000/site/

Só o site, sem Python além do servidor estático:

    python -m http.server -d docs 8080
    # abra http://127.0.0.1:8080/site/

Abrir `docs/site/index.html` direto no navegador (file://) também funciona; nesse caso o modo ao vivo fica desligado.

## Estrutura

- `index.html`: marcação, metadados de SEO e Open Graph, sprite de ícones embutido.
- `assets/css/`: `tokens.css` (cores, tipografia, espaço, tema claro e escuro), `base.css`, `components.css`, `sections.css`.
- `assets/js/`: `core.js` (helpers e camada de serviço da API), `ui.js` (tema, navegação, revelação), um arquivo por seção (`hero`, `intro`, `explorer`, `ai`, `dataviz`, `automation`, `architecture`, `showcase`) e `features-data.js` (catálogo de funcionalidades).
- `assets/data/snapshot.js`: instantâneo gerado por `scripts/build_site_snapshot.py` a partir do banco sintético. Para atualizar: `python scripts/generate_data.py && python scripts/build_site_snapshot.py`.
- `assets/img/`: favicon, imagem Open Graph e capturas do painel em `docs/index.html` (tiradas com dados sintéticos e um simulador no lugar do modelo).
- `assets/NOTICE.md`: licenças das fontes (Geist, Instrument Serif) e dos ícones (Lucide).

Os ícones são um subconjunto de Lucide embutido em `index.html`. Ao usar um ícone novo, acrescente o `<symbol>` correspondente ao sprite; `tests/test_site.py` avisa quando falta algum.

## O que é real e o que é simulado

Real, vindo do repositório:

- Todos os números dos gráficos, a tabela de resultados e o contexto recuperado pelo RAG nas demonstrações: calculados ou executados sobre o banco SQLite sintético, com o índice BM25 e a guarda de SQL do próprio repositório.
- O catálogo de funcionalidades, em que cada item cita arquivos existentes (conferidos por `tests/test_site.py`).
- Os oito nós do workflow n8n, que espelham `n8n/alerta-critico.json`.
- O modo ao vivo da demonstração de IA: só aparece quando `GET /saude` responde na mesma origem. Então o campo de pergunta chama `POST /perguntar` da própria API. A chave do modelo fica no backend e nunca passa pelo navegador.
- Os resultados do benchmark de 56 perguntas, copiados de `docs/experiments.md`.

Simulado e identificado como tal na página:

- As cinco conversas pré-gravadas do assistente: o SQL e o texto da resposta foram escritos à mão em `scripts/build_site_snapshot.py`, e o modelo de linguagem não é chamado.
- A execução do workflow n8n: usa alertas do snapshot, não consulta a API e não dispara nenhum webhook.
- Os veículos do hero: ilustração sem GPS.
- As capturas do painel: o assistente respondeu por um simulador local, e o nome do modelo ativo aparece assim.

## Limitações

- Todos os dados são sintéticos. A página não mostra operação real, clientes, parceiros, depoimentos nem métricas de desempenho em campo.
- O modo ao vivo precisa de uma API sem chave obrigatória na mesma origem. Se `INFOFROTA_API_KEY` estiver definida, a página informa que a API exige chave e não tenta enviá-la.
- Não há `sitemap.xml` nem URL canônica, porque o endereço público ainda não existe. Defina-os quando houver um domínio.
- A deduplicação do workflow n8n ainda precisa ser validada com o workflow ativo; por isso aparece como "em validação".
- Nenhum deploy foi feito.
