# InfoFrota AI - experimento "LoRA treinado COM contexto recuperado (RAG)" em UMA célula.
# Pensado para Save Version > Save & Run All (Commit): roda no servidor, sem depender da aba.
# Passos: dependências -> repo e banco -> dados de treino com --rag (prompt ultra) -> QLoRA
#         -> avaliações (base ultra, base ultra+rag, LoRA-rag ultra+rag) -> relatórios e adaptador em /kaggle/working.
# Pré-requisitos: Dataset com o repo (infofrota-ai.zip), GPU T4, Internet On.
import glob, os, shutil, subprocess, sys, zipfile

def sh(cmd, check=True, **kw):
    print(f"\n$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True, **kw)
    if check and r.returncode:
        raise SystemExit(f"falhou ({r.returncode}): {cmd}")
    return r.returncode

sh(f"{sys.executable} -m pip install -q -U bitsandbytes peft accelerate transformers datasets")

# repo
achados = glob.glob("/kaggle/input/**/scripts/generate_data.py", recursive=True)
if not achados:
    zips = glob.glob("/kaggle/input/**/*.zip", recursive=True)
    assert zips, "nenhum zip/pasta do repo em /kaggle/input"
    with zipfile.ZipFile(zips[0]) as z:
        z.extractall("/kaggle/work_src")
    achados = glob.glob("/kaggle/work_src/**/scripts/generate_data.py", recursive=True)
assert achados, "generate_data.py não encontrado: dataset incompleto"
SRC = os.path.dirname(os.path.dirname(achados[0]))
REPO = "/kaggle/working/infofrota-ai"
shutil.copytree(SRC, REPO, dirs_exist_ok=True)
os.chdir(REPO)
sh(f"{sys.executable} scripts/generate_data.py")
sh(f"{sys.executable} scripts/build_train_set.py --prompt ultra --rag --saida training_rag")
sh(f"{sys.executable} -m unittest discover -s tests")          # falha cedo se algo estiver quebrado

BASE = "unsloth/Llama-3.1-8B-Instruct"
LORA = "/kaggle/working/lora_rag"
# treino (processo separado: a GPU é liberada ao terminar)
sh(f"TREINO=training_rag OUT_LORA={LORA} {sys.executable} kaggle/train_lora.py")
shutil.make_archive("/kaggle/working/lora_rag_adapter", "zip", LORA)

# avaliações (cada uma em processo próprio; uma falha não impede as outras)
ev = f"{sys.executable} -m infofrota_ai.evaluate --provider hf --prompt ultra --shots 0"
sh(f"{ev} --model {BASE}", check=False)
sh(f"{ev} --model {BASE} --rag", check=False)
sh(f"{ev} --model {BASE}::{LORA} --rag", check=False)
sh(f"{ev} --model {BASE}::{LORA}", check=False)                   # LoRA-rag SEM contexto: mostra a dependência

shutil.copytree("evaluation/runs", "/kaggle/working/runs", dirs_exist_ok=True)
print("\nFIM. Baixe /kaggle/working/runs e lora_rag_adapter.zip na aba Output.")
