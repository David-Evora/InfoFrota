# Dados locais

O gerador `scripts/generate_data.py` espera encontrar `linhas_ceturbes.csv` neste diretório.

O arquivo não é incluído no repositório público. Adicione aqui uma cópia obtida de fonte que permita seu uso, com as colunas:

- `Linha`: identificador da linha;
- `Rotulo`: nome/descrição da linha.

O CSV é ignorado pelo Git (`data/linhas_ceturbes.csv`). Não adicione ao repositório bancos de dados operacionais, dados pessoais, credenciais ou conjuntos de dados sem autorização.

Depois de adicionar o CSV, execute `python scripts/generate_data.py` na raiz do projeto para criar `data/infofrota.db` localmente.
