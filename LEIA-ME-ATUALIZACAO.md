# Atualização para manter somente um site no InfoFrota

Este pacote parte da estrutura atual do repositório `David-Evora/InfoFrota` (branch `main`) consultada em 7 de novembro de 2026.

## O que muda

- `docs/site/` passa a ser o único frontend.
- A FastAPI serve `docs/site/` diretamente em `/`.
- Não é recriada a antiga página `docs/index.html`.
- Não é criada uma segunda rota de interface em `/site/`.
- O Docker copia somente `docs/site/`.
- Os testes passam a validar os caminhos reais do novo site.
- As evidências do catálogo e do diagrama deixam de apontar para arquivos da interface antiga.

## Como aplicar

1. Faça uma cópia de segurança ou confirme que seu trabalho local está commitado.
2. Extraia o conteúdo deste ZIP diretamente na raiz da sua cópia local do repositório, mantendo a estrutura de pastas. Autorize substituir os arquivos existentes.
3. Na raiz do projeto, execute o script `APLICAR-AJUSTES-DOCUMENTACAO.ps1` para atualizar referências textuais no README e na documentação e ajustar o caminho-base usado pelo site.
4. Execute os testes:

   ```powershell
   python -m unittest discover -s tests -v
   ```

5. Reconstrua a API Docker:

   ```powershell
   docker compose build api
   docker compose up -d --build
   ```

6. Confira no navegador:
   - `http://127.0.0.1:8000/` — o novo site.
   - `http://127.0.0.1:8000/saude` — a API.
   - `http://127.0.0.1:8000/assets/js/core.js` — um asset estático do novo site.

7. Confira o Git:

   ```powershell
   git status
   git add Dockerfile.api infofrota_ai/api.py tests/test_api.py tests/test_site.py docs/site
   git add README.md docs/INFOFROTA_AI.md
   git commit -m "fix: mantém apenas o novo site do InfoFrota"
   git push origin main
   ```

## GitHub Pages

O workflow atual `.github/workflows/deploy-pages.yml` já publica `docs/site/`. Mantenha Settings → Pages → Build and deployment → Source como **GitHub Actions**. Ao enviar alterações em `docs/site/**`, o workflow publica o novo site em:

`https://david-evora.github.io/InfoFrota/`

## Observações

- Este pacote não apaga `docs/index.html` caso exista localmente; não é necessário recriá-lo nem copiá-lo. Se ainda existir na sua máquina, pode removê-lo depois de confirmar que nenhum arquivo ativo depende dele.
- O script de documentação usa substituições verificadas e não altera o conteúdo das demonstrações nem os arquivos de dados.
- Não faça `git add .` sem revisar `git status`; mantenha `.env.api`, tokens e webhooks fora do commit.
