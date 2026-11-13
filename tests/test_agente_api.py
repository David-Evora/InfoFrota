import json
import os
import unittest

try:
    from fastapi.testclient import TestClient
    from infofrota_ai.api import create_app
    TEM_FASTAPI = True
except ImportError:
    TEM_FASTAPI = False

from infofrota_ai.agente import Agente


class Roteiro:
    nome = "roteiro"

    def __init__(self, saidas):
        self.saidas = list(saidas)

    def complete(self, system, messages):
        if isinstance(self.saidas[0], Exception):
            raise self.saidas[0]
        return self.saidas.pop(0)


def acao(ferramenta, entrada):
    return json.dumps({"pensamento": "x", "ferramenta": ferramenta, "entrada": entrada})


@unittest.skipUnless(TEM_FASTAPI, "fastapi não instalado")
class AgenteApiTest(unittest.TestCase):
    def setUp(self):
        for k in ("INFOFROTA_API_KEY", "INFOFROTA_LIMITE_POR_MIN", "INFOFROTA_WEB"):
            os.environ.pop(k, None)

    def cliente(self, saidas):
        return TestClient(create_app(agente=Agente(Roteiro(saidas))))

    def test_agente_ok(self):
        r = self.cliente([acao("sql", "SELECT COUNT(*) FROM linhas"), acao("responder", "16 linhas.")]).post(
            "/agente", json={"pergunta": "Quantas linhas existem?"})
        corpo = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(corpo["texto"], "16 linhas.")
        self.assertEqual([p["ferramenta"] for p in corpo["passos"]], ["sql", "responder"])

    def test_validacao(self):
        self.assertEqual(self.cliente([acao("responder", "x")]).post("/agente", json={"pergunta": "oi"}).status_code, 422)

    def test_falha_do_modelo_vira_502(self):
        r = self.cliente([RuntimeError("fora do ar")]).post("/agente", json={"pergunta": "Quantas linhas?"})
        self.assertEqual(r.status_code, 502)

    def test_chave_de_api(self):
        os.environ["INFOFROTA_API_KEY"] = "segredo"
        c = self.cliente([acao("responder", "ok")])
        self.assertEqual(c.post("/agente", json={"pergunta": "Quantas linhas?"}).status_code, 401)
        self.assertEqual(c.post("/agente", json={"pergunta": "Quantas linhas?"}, headers={"X-API-Key": "segredo"}).status_code, 200)
