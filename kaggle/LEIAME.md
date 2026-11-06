# Treino LoRA no Kaggle (GPU)

## Preparação dos dados

O arquivo `data/linhas_ceturbes.csv` já está incluído no repositório.

Ao criar o Dataset para o Kaggle, inclua esse arquivo junto com
o código do projeto. Não é necessário adicionar um segundo Dataset
exclusivamente para os rótulos das linhas.

Não inclua:
- A pasta `.git`
- Ambientes virtuais (`.venv`)
- Banco SQLite gerado (`data/*.db`)
- Pesos e checkpoints de modelos
## Avaliar com RAG (sem retreinar)
Depois de aplicar este patch no repo e subir o dataset de novo, rode as 4 combinações no mesmo prompt (`--prompt compacto --shots 0`):
1. base · 2. base `--rag` · 3. base+LoRA (`BASE::/kaggle/working/lora`) · 4. base+LoRA `--rag`.
O LoRA foi treinado sem contexto recuperado: se o 4 não superar o 3, isso é um resultado (o modelo precisaria ser treinado com o contexto).

## Treino com contexto recuperado (uma célula, em segundo plano)
1. Suba o repo atualizado como dataset (inclui `training_rag/`).
2. Notebook novo: GPU T4 x2, Internet On, input = o dataset. Numa única célula: `%run kaggle/rodar_tudo.py` não funciona antes de o repo existir, então cole o conteúdo de `kaggle/rodar_tudo.py` inteiro na célula.
3. **Save Version > Save & Run All (Commit)**. Leva cerca de 3 horas e pode fechar a aba.
4. Na aba Output da versão, baixe `runs/` e `lora_rag_adapter.zip`.
