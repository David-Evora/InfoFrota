import json
import sqlite3
import unittest

from unittest import mock

from infofrota_ai.agente import Agente, ComEspera, _interpretar
from infofrota_ai.avaliar_agente import QUESTOES, contem
from infofrota_ai.db import DB_PATH
from infofrota_ai.llm import LLMErro


class Roteiro:
    """LLM falso: devolve as saídas em ordem e guarda o que recebeu."""
    nome = "roteiro"

    def __init__(self, saidas):
        self.saidas, self.vistas = list(saidas), []

    def complete(self, system, messages):
        self.vistas.append([m["content"] for m in messages])
        return self.saidas.pop(0) if len(self.saidas) > 1 else self.saidas[0]


def acao(ferramenta, entrada):
    return json.dumps({"pensamento": "x", "ferramenta": ferramenta, "entrada": entrada})


class TestAgente(unittest.TestCase):
    def test_sql_depois_responder(self):
        llm = Roteiro([acao("sql", "SELECT COUNT(*) AS n FROM linhas"), acao("responder", "16 linhas.")])
        r = Agente(llm).perguntar("quantas linhas?")
        self.assertEqual(r.texto, "16 linhas.")
        self.assertIsNone(r.erro)
        self.assertIn("OBSERVAÇÃO", llm.vistas[1][-1])
        self.assertIn("16", llm.vistas[1][-1])

    def test_escrita_bloqueada(self):
        n = lambda: sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM linhas").fetchone()[0]
        antes = n()
        llm = Roteiro([acao("sql", "DELETE FROM linhas"), acao("responder", "não é possível")])
        r = Agente(llm).perguntar("apague as linhas")
        self.assertIn("bloqueado", r.passos[0]["observacao"])
        self.assertEqual(n(), antes)

    def test_formato_invalido_recebe_correcao(self):
        llm = Roteiro(["não sei", acao("responder", "ok")])
        r = Agente(llm).perguntar("oi")
        self.assertEqual(r.texto, "ok")
        self.assertIn("Formato inválido", llm.vistas[1][-1])

    def test_tool_use_failed_e_refeito(self):
        class Falha(Roteiro):
            def complete(self, system, messages):
                if not self.vistas:
                    self.vistas.append(messages)
                    raise LLMErro('HTTP 400 {"code":"tool_use_failed"}')
                return super().complete(system, messages)
        r = Agente(Falha([acao("responder", "ok")])).perguntar("x")
        self.assertEqual(r.texto, "ok")
        self.assertIn("Formato inválido", r.passos[0]["observacao"])

    def test_429_espera_e_repete(self):
        class Limite:
            nome, n = "x", 0
            def complete(self, system, messages):
                self.n += 1
                if self.n == 1:
                    raise LLMErro("HTTP 429 ... Please try again in 1m2.5s.")
                return "ok"
        llm = Limite()
        with mock.patch("infofrota_ai.agente.time.sleep") as dormir:
            self.assertEqual(ComEspera(llm).complete("s", []), "ok")
        dormir.assert_called_once_with(63.5)

    def test_limite_de_passos(self):
        llm = Roteiro([acao("sql", "SELECT 1")])
        r = Agente(llm, max_passos=3).perguntar("loop")
        self.assertIsNone(r.texto)
        self.assertIn("limite", r.erro)
        self.assertEqual(len(llm.vistas), 4)
        self.assertIn("LIMITE DE PASSOS", llm.vistas[-1][-1])

    def test_limite_forca_resposta(self):
        llm = Roteiro([acao("sql", "SELECT 1"), acao("sql", "SELECT 1"), acao("responder", "feito")])
        r = Agente(llm, max_passos=2).perguntar("x")
        self.assertEqual(r.texto, "feito")

    def test_ferramenta_esquema(self):
        llm = Roteiro([acao("esquema", "alertas por linha"), acao("responder", "ok")])
        r = Agente(llm).perguntar("x")
        self.assertIn("alertas", r.passos[0]["observacao"])

    def test_interpretar(self):
        self.assertIsNone(_interpretar("sem json"))
        self.assertIsNone(_interpretar('{"ferramenta": "apagar", "entrada": "x"}'))
        self.assertEqual(_interpretar('texto {"ferramenta": "sql", "entrada": " SELECT 1 "} fim')["entrada"], "SELECT 1")


class TestPerguntasAgente(unittest.TestCase):
    def test_contem(self):
        self.assertTrue(contem("Vitória lidera", ["vitoria"]))
        self.assertTrue(contem("às 17h", ["17|17h"]))
        self.assertFalse(contem("são 1562 alertas", ["562"]))
        self.assertFalse(contem("média 6.5", ["6"]))

    def test_referencias_batem_com_esperado(self):
        questoes = json.loads(QUESTOES.read_text(encoding="utf-8"))
        self.assertEqual(len(questoes), 13)
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        for q in questoes:
            saida = [con.execute(s).fetchall() for s in q["passos_ref"]]
            self.assertTrue(contem(json.dumps(saida, ensure_ascii=False, default=str), q["esperado"]), q["id"])


if __name__ == "__main__":
    unittest.main()
