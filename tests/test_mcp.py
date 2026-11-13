import asyncio
import unittest

try:
    from infofrota_ai import mcp_server
    TEM_MCP = True
except ImportError:       # opcional (requirements-mcp.txt)
    TEM_MCP = False


@unittest.skipUnless(TEM_MCP, "mcp não instalado")
class McpTest(unittest.TestCase):
    def test_ferramentas_registradas(self):
        nomes = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
        self.assertEqual(nomes, {"consultar_esquema", "executar_sql"})

    def test_executar_sql(self):
        r = mcp_server.executar_sql("SELECT COUNT(*) AS n FROM linhas WHERE monitorada = 1")
        self.assertEqual(r["linhas"], [[16]])
        self.assertIn("sintéticos", r["nota"])

    def test_escrita_bloqueada(self):
        r = mcp_server.executar_sql("DELETE FROM linhas")
        self.assertIn("bloqueado", r["erro"])

    def test_esquema(self):
        self.assertIn("alertas", mcp_server.consultar_esquema("alertas por linha"))
