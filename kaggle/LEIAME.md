# Treino LoRA no Kaggle (GPU)

O repositório público não inclui o CSV de linhas, o banco SQLite nem os pesos do adaptador. Para executar o treino, use dois inputs no Kaggle:

1. **Código:** compacte a pasta `infofrota-ai` sem `.git`, `.venv`, `data/*.db`, `data/linhas_ceturbes.csv` e arquivos de modelo; envie como Dataset do Kaggle. O pacote já contém `training/`, `kaggle/` e os scripts.
2. **Dados locais:** crie um segundo Dataset (preferencialmente privado) contendo o arquivo `linhas_ceturbes.csv`, desde que você tenha autorização para utilizá-lo. Não publique esse CSV sem verificar os termos da fonte.

No Kaggle:

1. Crie um Notebook e adicione os dois Datasets em **Add Input**.
2. Em Settings, escolha **GPU T4 x2** e habilite **Internet**.
3. Cole `kaggle/train_lora.py` em células (cada `# %%` marca uma seção).
4. Execute as células em ordem. O script copia o CSV do segundo input para `data/` apenas no ambiente temporário e gera o banco.
5. Ao final, baixe `lora_adapter.zip` e os relatórios da aba Output.

O adaptador e os checkpoints não devem ser enviados ao repositório de código.
