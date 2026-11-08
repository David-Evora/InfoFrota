import json
import os
import unittest

try:
    from fastapi.testclient import TestClient
    from infofrota_ai.api import create_app
    TEM_FASTAPI = True
except ImportError:       # a API é opcional (requirements-api.txt)
    TEM_FASTAPI = False

from infofrota_ai.assistant import Assistente


class LLMFixo:
    nome = "fixo"

    def __init__(self, saida):
        self.saida = saida

    def complete(self, system, messages):
        if isinstance(self.saida, Exception):
            raise self.saida
        return self.saida


def resposta(sql, pode=True, motivo=""):
    return json.dumps({"pode_responder": pode, "sql": sql, "motivo": motivo})


@unittest.skipUnless(TEM_FASTAPI, "fastapi não instalado")
class ApiTest(unittest.TestCase):
    def setUp(self):
        for k in ("INFOFROTA_API_KEY", "INFOFROTA_LIMITE_POR_MIN", "INFOFROTA_WEB"):
            os.environ.pop(k, None)

    def cliente(self, saida):
        return TestClient(create_app(Assistente(LLMFixo(saida), shots=0)))

    def test_saude_sem_modelo(self):
        r = TestClient(create_app()).get("/saude").json()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["linhas_monitoradas"], 16)

    def test_perguntar_ok(self):
        r = self.cliente(resposta("SELECT COUNT(*) FROM linhas WHERE monitorada = 1")).post(
            "/perguntar", json={"pergunta": "Quantas linhas são monitoradas?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["linhas"], [[16]])

    def test_escrita_bloqueada(self):
        r = self.cliente(resposta("DELETE FROM linhas")).post("/perguntar", json={"pergunta": "apague as linhas"}).json()
        self.assertTrue(r["bloqueado"])
        self.assertEqual(r["linhas"], [])

    def test_recusa(self):
        r = self.cliente(resposta("", False, "sem dado")).post("/perguntar", json={"pergunta": "qual o salário?"}).json()
        self.assertFalse(r["pode_responder"])

    def test_validacao(self):
        c = self.cliente(resposta("SELECT 1"))
        self.assertEqual(c.post("/perguntar", json={"pergunta": "oi"}).status_code, 422)
        self.assertEqual(c.post("/perguntar", json={"pergunta": "x" * 501}).status_code, 422)

    def test_falha_do_modelo_vira_502(self):
        r = self.cliente(RuntimeError("fora do ar")).post("/perguntar", json={"pergunta": "Quantas linhas?"})
        self.assertEqual(r.status_code, 502)

    def test_chave_de_api(self):
        os.environ["INFOFROTA_API_KEY"] = "segredo"
        c = self.cliente(resposta("SELECT 1"))
        corpo = {"pergunta": "Quantas linhas?"}
        self.assertEqual(c.post("/perguntar", json=corpo).status_code, 401)
        self.assertEqual(c.post("/perguntar", json=corpo, headers={"X-API-Key": "errada"}).status_code, 401)
        self.assertEqual(c.post("/perguntar", json=corpo, headers={"X-API-Key": "segredo"}).status_code, 200)
        self.assertEqual(c.get("/alertas").status_code, 401)
        self.assertEqual(c.get("/saude").status_code, 200)

    def test_limite_por_minuto(self):
        os.environ["INFOFROTA_LIMITE_POR_MIN"] = "2"
        c = self.cliente(resposta("SELECT 1"))
        codigos = [c.post("/perguntar", json={"pergunta": "Quantas linhas?"}).status_code for _ in range(3)]
        self.assertEqual(codigos, [200, 200, 429])

    def test_alertas(self):
        c = TestClient(create_app())
        r = c.get("/alertas", params={"tipo": "CRITICO", "janela_horas": 24, "limite": 3}).json()
        self.assertLessEqual(len(r["alertas"]), 3)
        self.assertGreater(r["total"], 0)
        self.assertTrue(all(a["tipo"] == "CRITICO" for a in r["alertas"]))
        pct = [a["percentual"] for a in r["alertas"]]
        self.assertEqual(pct, sorted(pct, reverse=True))
        self.assertEqual(c.get("/alertas", params={"tipo": "X"}).status_code, 422)
        self.assertEqual(c.get("/alertas", params={"referencia": "ontem"}).status_code, 422)
        vazio = c.get("/alertas", params={"referencia": "2020-01-01 00:00:00"}).json()
        self.assertEqual(vazio["total"], 0)

    def test_resumo(self):
        c = TestClient(create_app())
        r = c.get("/resumo").json()
        self.assertEqual(len(r["linhas"]), 5)
        self.assertEqual(c.get("/resumo", params={"data": "2020-01-01"}).status_code, 404)
        self.assertEqual(c.get("/resumo", params={"data": "01/11/2026"}).status_code, 422)

    def test_resumo_limite_e_campos_da_linha(self):
        c = TestClient(create_app())
        todas = c.get("/resumo", params={"limite": 50}).json()
        self.assertEqual(len(todas["linhas"]), todas["total_linhas"])
        self.assertTrue(all({"linha", "linha_nome", "tipo", "media_percentual"} <= set(l) for l in todas["linhas"]))
        medias = [l["media_percentual"] for l in todas["linhas"]]
        self.assertEqual(medias, sorted(medias, reverse=True))
        self.assertEqual(c.get("/resumo", params={"limite": 0}).status_code, 422)
        self.assertEqual(c.get("/resumo", params={"limite": 51}).status_code, 422)

    def test_interface_web_na_mesma_origem(self):
        c = TestClient(create_app())
        pagina = c.get("/")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn("InfoFrota", pagina.text)
        self.assertEqual(c.get("/assets/js/core.js").status_code, 200)
        self.assertEqual(c.get("/saude").json()["status"], "ok")      # a API não é encoberta pela interface
        os.environ["INFOFROTA_WEB"] = "0"
        self.assertEqual(TestClient(create_app()).get("/").status_code, 404)


if __name__ == "__main__":
    unittest.main()
