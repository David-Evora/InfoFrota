#!/usr/bin/env python3
"""Monta a pasta do Hugging Face Space (padrão: ../infofrota-space), pronta para git push no Space.

    python scripts/montar_space.py [pasta_de_saida]

Copia só o necessário: pacote infofrota_ai (sem a API, o cliente HF e caches), o gerador de dados, o CSV
público e o schema. O banco é gerado na subida do Space; nenhuma chave é copiada.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "infofrota-space"
IGNORAR = {"api.py", "hf_llm.py", "mcp_server.py", "__pycache__"}


def copiar(origem: Path, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, destino)


for arq in ("app.py", "README.md", "requirements.txt"):
    copiar(ROOT / "space" / arq, SAIDA / arq)
for arq in (ROOT / "infofrota_ai").glob("*.py"):
    if arq.name not in IGNORAR:
        copiar(arq, SAIDA / "infofrota_ai" / arq.name)
copiar(ROOT / "scripts" / "generate_data.py", SAIDA / "scripts" / "generate_data.py")
copiar(ROOT / "data" / "linhas_ceturbes.csv", SAIDA / "data" / "linhas_ceturbes.csv")
copiar(ROOT / "db" / "schema.sql", SAIDA / "db" / "schema.sql")
print(f"Space montado em {SAIDA}")
