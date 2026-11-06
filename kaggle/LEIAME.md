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

## Avaliar com RAG (sem retreinar)
Depois de aplicar este patch no repo e subir o dataset de novo, rode as 4 combinações no mesmo prompt (`--prompt compacto --shots 0`):
1. base · 2. base `--rag` · 3. base+LoRA (`BASE::/kaggle/working/lora`) · 4. base+LoRA `--rag`.
O LoRA foi treinado sem contexto recuperado: se o 4 não superar o 3, isso é um resultado (o modelo precisaria ser treinado com o contexto).

## Treino com contexto recuperado (uma célula, em segundo plano)
1. Suba o repo atualizado como dataset (inclui `training_rag/`).
2. Notebook novo: GPU T4 x2, Internet On, input = o dataset. Numa única célula: `%run kaggle/rodar_tudo.py` não funciona antes de o repo existir, então cole o conteúdo de `kaggle/rodar_tudo.py` inteiro na célula.
3. **Save Version > Save & Run All (Commit)**. Leva cerca de 3 horas e pode fechar a aba.
4. Na aba Output da versão, baixe `runs/` e `lora_rag_adapter.zip`.
