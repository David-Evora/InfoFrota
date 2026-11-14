import importlib.util
import unittest
from pathlib import Path

from infofrota_ai.agente import Agente
from infofrota_ai.llm import LLMErro

_spec = importlib.util.spec_from_file_location("space_app", Path(__file__).resolve().parent.parent / "space" / "app.py")
space = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(space)


class Roteiro:
    nome = "roteiro"

    def __init__(self, saidas):
        self.saidas = list(saidas)

    def complete(self, system, messages):
        s = self.saidas.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def acao(ferramenta, entrada):
    import json
    return json.dumps({"pensamento": "x", "ferramenta": ferramenta, "entrada": entrada})


class SpaceTest(unittest.TestCase):
    def setUp(self):
        space._estado["dia"] = (None, 0)
        space._estado["ips"].clear()

    def test_responde_e_mostra_passos(self):
        ag = Agente(Roteiro([acao("sql", "SELECT COUNT(*) FROM linhas"), acao("responder", "16 linhas.")]))
        texto, passos = space.responder("Quantas linhas existem?", "1.1.1.1", ag)
        self.assertIn("16 linhas.", texto)
        self.assertIn("SELECT COUNT(*) FROM linhas", passos)

    def test_pergunta_curta_e_longa(self):
        self.assertIn("Escreva", space.responder("oi", "ip", Agente(Roteiro([])))[0])
        self.assertIn("passa de", space.responder("x" * 301, "ip", Agente(Roteiro([])))[0])

    def test_limite_por_ip(self):
        for _ in range(10):
            self.assertEqual(space.liberar("ip-a", 1000.0), "")
        self.assertIn("por hora", space.liberar("ip-a", 1001.0))
        self.assertEqual(space.liberar("ip-b", 1001.0), "")
        self.assertEqual(space.liberar("ip-a", 1000.0 + 3601), "")

    def test_limite_diario(self):
        import os
        os.environ["INFOFROTA_SPACE_LIMITE_DIA"] = "2"
        try:
            self.assertEqual(space.liberar("a", 5000.0), "")
            self.assertEqual(space.liberar("b", 5001.0), "")
            self.assertIn("hoje", space.liberar("c", 5002.0))
        finally:
            os.environ.pop("INFOFROTA_SPACE_LIMITE_DIA")

    def test_falha_do_modelo_nao_vaza_detalhe(self):
        ag = Agente(Roteiro([LLMErro("HTTP 401 chave sk-secreta")]))
        texto, _ = space.responder("Quantas linhas existem?", "ip", ag)
        self.assertNotIn("sk-secreta", texto)
