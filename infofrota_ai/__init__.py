"""InfoFrota AI: assistente de texto para SQL sobre o banco do InfoFrota."""
import os
from pathlib import Path


def _carregar_env():
    raiz = Path(__file__).resolve().parent.parent
    arq = next((a for a in (raiz / ".env.api", raiz / ".env") if a.is_file()), None)
    if arq is None:
        return
    for linha in arq.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.removeprefix("export ").strip(), valor.strip().strip("\"'"))


_carregar_env()