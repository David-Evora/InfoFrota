# Dados do projeto

## Rótulos das linhas

O arquivo `linhas_ceturbes.csv` contém identificadores e rótulos
das linhas de transporte coletivo.

- **Conjunto:** [Rótulos das Linhas](https://dados.es.gov.br/dataset/rotulos-das-linhas)
- **Órgão responsável:** CETURB-ES
- **Portal:** Dados Abertos do Espírito Santo
- **Licença indicada:** CC0
- **Arquivo:** `linhas_ceturbes.csv`
- **Colunas utilizadas:** `Linha` e `Rotulo`

O CSV está incluído neste repositório.

A licença CC0 aqui mencionada refere-se especificamente ao conjunto
de dados citado, não a todos os dados da CETURB-ES.

## Banco de dados

O banco `infofrota.db` é gerado localmente pelo script:

```bash
python scripts/generate_data.py