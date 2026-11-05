"""Execução segura de SQL gerado por modelo.

Três camadas, para que um SQL malicioso ou errado não consiga alterar o banco:
  1. o arquivo é aberto em modo somente leitura (mode=ro);
  2. um authorizer do SQLite só permite SELECT/READ/FUNCTION;
  3. a consulta precisa começar com SELECT ou WITH e ser uma única instrução.
Além disso há limite de linhas e de tempo.
"""
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "infofrota.db"


class SQLBloqueado(Exception):
    """A consulta tenta algo que não é leitura."""


class SQLErro(Exception):
    """A consulta é permitida, mas falhou ao executar."""


@dataclass
class Resultado:
    colunas: list
    linhas: list
    truncado: bool = False


_PERMITIDOS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
if hasattr(sqlite3, "SQLITE_RECURSIVE"):
    _PERMITIDOS.add(sqlite3.SQLITE_RECURSIVE)
_FUNCOES_PROIBIDAS = {"load_extension"}


def _authorizer(action, arg1, arg2, dbname, source):
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _FUNCOES_PROIBIDAS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK if action in _PERMITIDOS else sqlite3.SQLITE_DENY


def limpar_sql(sql: str) -> str:
    sql = (sql or "").strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip().rstrip(";").strip()


def _sem_comentarios_iniciais(sql: str) -> str:
    while True:
        novo = re.sub(r"^\s*(--[^\n]*\n?|/\*.*?\*/)", "", sql, count=1, flags=re.S)
        if novo == sql:
            return sql.lstrip()
        sql = novo


def conectar(db_path=DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.set_authorizer(_authorizer)
    return con


def executar(sql: str, db_path=DB_PATH, max_linhas: int = 200,
             timeout_s: float = 5.0) -> Resultado:
    sql = limpar_sql(sql)
    if not sql:
        raise SQLErro("consulta vazia")
    if not re.match(r"(?is)(select|with)\b", _sem_comentarios_iniciais(sql)):
        raise SQLBloqueado("só é permitido SELECT (ou WITH ... SELECT)")

    con = conectar(db_path)
    inicio = time.monotonic()
    con.set_progress_handler(lambda: 1 if time.monotonic() - inicio > timeout_s else 0, 50_000)
    try:
        cur = con.execute(sql)
        colunas = [d[0] for d in cur.description] if cur.description else []
        linhas = cur.fetchmany(max_linhas + 1)
    except sqlite3.ProgrammingError as e:
        raise SQLBloqueado(f"apenas uma instrução por consulta ({e})") from e
    except sqlite3.DatabaseError as e:
        msg = str(e)
        if "authoriz" in msg.lower():
            raise SQLBloqueado(f"operação não permitida ({msg})") from e
        if "interrupt" in msg.lower():
            raise SQLErro(f"consulta demorou mais de {timeout_s:.0f}s") from e
        raise SQLErro(msg) from e
    finally:
        con.close()
    truncado = len(linhas) > max_linhas
    return Resultado(colunas, [list(r) for r in linhas[:max_linhas]], truncado)
