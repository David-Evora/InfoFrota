"""InfoFrota AI: assistente de texto para SQL sobre o banco do InfoFrota."""
import os
from pathlib import Path


def _carregar_env():
    arq = Path(__file__).resolve().parent.parent / ".env"
    if not arq.is_file():
        return
    for linha in arq.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.removeprefix("export ").strip(), valor.strip().strip("\"'"))


_carregar_env()