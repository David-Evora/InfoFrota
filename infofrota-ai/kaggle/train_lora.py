# InfoFrota AI - QLoRA text-to-SQL (Kaggle, GPU T4). Rode célula a célula (# %%) ou como notebook.
# Pré-requisitos no Kaggle: Accelerator = GPU T4 x2 (usa 1), Internet = On,
# e um Dataset com o zip do repo (ver kaggle/LEIAME.md).

# %% 1. dependências
# !pip install -q -U bitsandbytes peft accelerate transformers datasets

# %% 2. repositório e dados
import json, os, shutil, subprocess, sys, glob, zipfile
zips = glob.glob("/kaggle/input/*/*.zip")
assert zips, "adicione o dataset com infofrota-ai.zip"
with zipfile.ZipFile(zips[0]) as z: z.extractall("/kaggle/working")
REPO = next(p for p in glob.glob("/kaggle/working/*") if os.path.exists(p + "/infofrota_ai"))
os.chdir(REPO); sys.path.insert(0, REPO)

# O CSV de linhas não fica no repositório público. Adicione-o como segundo input do Kaggle.
CSV_LOCAL = os.path.join(REPO, "data", "linhas_ceturbes.csv")
if not os.path.exists(CSV_LOCAL):
    csvs = glob.glob("/kaggle/input/*/linhas_ceturbes.csv")
    assert len(csvs) == 1, (
        "Adicione um Dataset de input com exatamente um arquivo "
        "linhas_ceturbes.csv (preferencialmente privado)."
    )
    os.makedirs(os.path.dirname(CSV_LOCAL), exist_ok=True)
    shutil.copy2(csvs[0], CSV_LOCAL)

subprocess.run([sys.executable, "scripts/generate_data.py"], check=True)      # gera o banco
BASE = "unsloth/Llama-3.1-8B-Instruct"   # mesmos pesos do Llama-3.1-8B-Instruct, sem exigir token
OUT = "/kaggle/working/lora"

# %% 3. tokenização (perda só na resposta do assistente)
import torch
from datasets import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          DataCollatorForSeq2Seq, Trainer, TrainingArguments)
tok = AutoTokenizer.from_pretrained(BASE)
tok.pad_token = tok.pad_token or "<|finetune_right_pad_id|>"
MAXLEN = 2600

def carregar(arq):
    out = []
    for l in open(arq, encoding="utf-8"):
        m = json.loads(l)["messages"]
        prompt = tok.apply_chat_template(m[:2], add_generation_prompt=True, tokenize=False)
        resp = m[2]["content"] + "<|eot_id|>"
        p = tok(prompt, add_special_tokens=False)["input_ids"]
        r = tok(resp, add_special_tokens=False)["input_ids"]
        ids = (p + r)[:MAXLEN]
        out.append({"input_ids": ids, "attention_mask": [1] * len(ids),
                    "labels": ([-100] * len(p) + r)[:MAXLEN]})
    return Dataset.from_list(out)

tr, va = carregar("training/train_chat.jsonl"), carregar("training/val_chat.jsonl")
print(len(tr), len(va), "tokens máx:", max(len(x["input_ids"]) for x in tr))

# %% 4. modelo 4 bits + LoRA
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
model = AutoModelForCausalLM.from_pretrained(
    BASE, device_map={"": 0}, torch_dtype=torch.float16,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                           bnb_4bit_use_double_quant=True,
                                           bnb_4bit_compute_dtype=torch.float16))
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model = get_peft_model(model, LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
model.print_trainable_parameters()

# %% 5. treino (~3 épocas)
args = TrainingArguments(
    output_dir="/kaggle/working/ckpt", num_train_epochs=3, per_device_train_batch_size=1,
    gradient_accumulation_steps=16, learning_rate=2e-4, lr_scheduler_type="cosine",
    warmup_ratio=0.05, fp16=True, logging_steps=5, eval_strategy="epoch",
    save_strategy="no", optim="paged_adamw_8bit", report_to="none", seed=42,
    per_device_eval_batch_size=1)
Trainer(model=model, args=args, train_dataset=tr, eval_dataset=va,
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100)).train()
model.save_pretrained(OUT); tok.save_pretrained(OUT)
shutil.make_archive("/kaggle/working/lora_adapter", "zip", OUT)   # baixe este zip em Output
print("adaptador salvo")

# %% 6. avaliação nas 56 perguntas (reinicie o kernel antes se faltar memória)
del model; torch.cuda.empty_cache()
# !python -m infofrota_ai.evaluate --provider hf --model unsloth/Llama-3.1-8B-Instruct::/kaggle/working/lora --prompt compacto --shots 0
# base, mesmo prompt, para comparar:
# !python -m infofrota_ai.evaluate --provider hf --model unsloth/Llama-3.1-8B-Instruct --prompt compacto --shots 0
# !cp -r evaluation/runs /kaggle/working/runs
