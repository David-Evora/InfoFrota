"""Servidor MCP do InfoFrota: expõe ao Claude Desktop, Cursor etc. as mesmas ferramentas do agente.

    pip install -r requirements-mcp.txt
    python -m infofrota_ai.mcp_server            # stdio

Claude Desktop (claude_desktop_config.json):
    {"mcpServers": {"infofrota": {"command": "python", "args": ["-m", "infofrota_ai.mcp_server"],
                                  "cwd": "C:\\\\caminho\\\\para\\\\infofrota-ai"}}}

Sem LLM aqui: quem decide quais ferramentas chamar é o cliente MCP. Toda consulta passa pela guarda
somente leitura de db.py. Dados sintéticos.
"""
import os

from mcp.server.fastmcp import FastMCP

from . import prompts
from .agente import MAX_CHARS_OBS, Agente
from .db import DB_PATH

mcp = FastMCP("infofrota")
_agente = None     # só usa o banco e o índice de esquema; nenhum modelo é carregado


def _ferramentas() -> Agente:
    global _agente
    if _agente is None:
        _agente = Agente(llm=None, db_path=os.environ.get("INFOFROTA_DB") or DB_PATH)
    return _agente


@mcp.tool()
def consultar_esquema(consulta: str) -> str:
    """Tabelas, colunas, valores categóricos e regras do banco InfoFrota relevantes para a consulta.
    Use antes de executar_sql para descobrir estrutura e valores válidos."""
    return _ferramentas().indice.contexto(consulta)


@mcp.tool()
def executar_sql(sql: str) -> dict:
    """Executa UMA consulta SELECT (ou WITH ... SELECT) em SQLite no banco sintético do InfoFrota
    (lotação de ônibus da Grande Vitória). Escritas são bloqueadas. Devolve colunas e linhas, ou o erro."""
    dados = _ferramentas()._usar("sql", sql.strip())
    dados["nota"] = prompts.NOTA_DADOS
    return dados


@mcp.resource("infofrota://regras")
def regras() -> str:
    """Esquema compacto e regras do domínio, o mesmo contexto que o agente recebe."""
    return _ferramentas().system[:MAX_CHARS_OBS * 4]


if __name__ == "__main__":
    mcp.run()
