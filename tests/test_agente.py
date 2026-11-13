import json
import sqlite3
import tempfile
import unittest
from unittest import mock

from infofrota_ai.agente import Agente, ComEspera, LimiteDiario, _interpretar
from infofrota_ai.avaliar_agente import QUESTOES, contem
from infofrota_ai.db import DB_PATH
from infofrota_ai.llm import CachedLLM, LLMErro


class Roteiro:
    """LLM falso do protocolo textual de compatibilidade."""
    nome = "roteiro-texto"

    def __init__(self, saidas):
        self.saidas, self.vistas = list(saidas), []

    def complete(self, system, messages):
        self.vistas.append([dict(m) for m in messages])
        return self.saidas.pop(0) if len(self.saidas) > 1 else self.saidas[0]


class RoteiroNativo:
    """LLM falso que reproduz mensagens nativas de Tool Calling."""
    nome = "roteiro-tool-calling"

    def __init__(self, saidas):
        self.saidas = list(saidas)
        self.vistas = []
        self.opcoes = []

    def _proxima(self):
        if not self.saidas:
            return {"role": "assistant", "content": "Resposta final simulada."}
        return self.saidas.pop(0) if len(self.saidas) > 1 else self.saidas[0]

    def complete_with_tools(self, system, messages, tools, tool_choice="auto", parallel_tool_calls=False):
        self.vistas.append([dict(m) for m in messages])
        self.opcoes.append({"tools": tools, "tool_choice": tool_choice,
                            "parallel_tool_calls": parallel_tool_calls})
        return self._proxima()

    def complete(self, system, messages):
        self.vistas.append([dict(m) for m in messages])
        self.opcoes.append({"tools": [], "tool_choice": "none", "parallel_tool_calls": False})
        return self._proxima().get("content", "")


def acao(ferramenta, entrada):
    return json.dumps({"pensamento": "x", "ferramenta": ferramenta, "entrada": entrada})


def chamada_tool(nome, argumentos, call_id="call_1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": nome, "arguments": json.dumps(argumentos, ensure_ascii=False)},
        }],
    }


class TestAgente(unittest.TestCase):
    def test_sql_depois_responder_protocolo_legado(self):
        llm = Roteiro([acao("sql", "SELECT COUNT(*) AS n FROM linhas"),
                       acao("responder", "16 linhas.")])
        resultado = Agente(llm).perguntar("quantas linhas?")
        self.assertEqual(resultado.texto, "16 linhas.")
        self.assertIsNone(resultado.erro)
        self.assertIn("OBSERVAÇÃO", llm.vistas[1][-1]["content"])

    def test_escrita_bloqueada(self):
        def contar():
            with sqlite3.connect(DB_PATH) as con:
                return con.execute("SELECT COUNT(*) FROM linhas").fetchone()[0]
        antes = contar()
        llm = Roteiro([acao("sql", "DELETE FROM linhas"), acao("responder", "não é possível")])
        resultado = Agente(llm).perguntar("apague as linhas")
        self.assertIn("bloqueado", resultado.passos[0]["observacao"])
        self.assertEqual(contar(), antes)

    def test_formato_invalido_recebe_correcao(self):
        llm = Roteiro(["não sei", acao("responder", "ok")])
        resultado = Agente(llm).perguntar("oi")
        self.assertEqual(resultado.texto, "ok")
        self.assertIn("Formato inválido", llm.vistas[1][-1]["content"])

    def test_tool_use_failed_e_refeito_no_fallback(self):
        class Falha(Roteiro):
            def __init__(self, saidas):
                super().__init__(saidas)
                self.primeira = True

            def complete(self, system, messages):
                if self.primeira:
                    self.primeira = False
                    raise LLMErro('HTTP 400 {"code":"tool_use_failed"}')
                return super().complete(system, messages)
        resultado = Agente(Falha([acao("responder", "ok")])).perguntar("x")
        self.assertEqual(resultado.texto, "ok")

    def test_429_espera_e_repete(self):
        class Limite:
            nome = "limite"
            chamadas = 0
            def complete(self, system, messages):
                self.chamadas += 1
                if self.chamadas == 1:
                    raise LLMErro("HTTP 429 ... Please try again in 1m2.5s.")
                return "ok"
        llm = Limite()
        with mock.patch("infofrota_ai.agente.time.sleep") as dormir:
            self.assertEqual(ComEspera(llm).complete("s", []), "ok")
        dormir.assert_called_once_with(63.5)

    def test_limite_de_passos_fallback(self):
        llm = Roteiro([acao("sql", "SELECT 1")])
        resultado = Agente(llm, max_passos=3).perguntar("loop")
        self.assertIsNone(resultado.texto)
        self.assertIn("limite", resultado.erro)
        self.assertIn("LIMITE DE PASSOS", llm.vistas[-1][-1]["content"])

    def test_ferramenta_esquema_fallback(self):
        llm = Roteiro([acao("esquema", "alertas por linha"), acao("responder", "ok")])
        resultado = Agente(llm).perguntar("x")
        self.assertIn("alertas", resultado.passos[0]["observacao"])

    def test_interpretar(self):
        self.assertIsNone(_interpretar("sem json"))
        self.assertIsNone(_interpretar('{"ferramenta": "apagar", "entrada": "x"}'))
        self.assertEqual(
            _interpretar('texto {"ferramenta": "sql", "entrada": " SELECT 1 "} fim')["entrada"],
            "SELECT 1",
        )

    def test_tool_calling_nativo_executa_sql_e_finaliza(self):
        llm = RoteiroNativo([
            chamada_tool("executar_sql", {"sql": "SELECT COUNT(*) AS n FROM linhas"}),
            {"role": "assistant", "content": "A base contém 16 linhas."},
        ])
        resultado = Agente(llm).perguntar("quantas linhas existem?")
        self.assertEqual(resultado.texto, "A base contém 16 linhas.")
        self.assertEqual(len(resultado.passos), 1)
        self.assertEqual(resultado.passos[0]["ferramenta"], "sql")
        self.assertFalse(llm.opcoes[0]["parallel_tool_calls"])
        self.assertIn("tool_call_id", llm.vistas[1][-1])

    def test_tool_calling_nativo_decompoe_pergunta_em_turnos(self):
        llm = RoteiroNativo([
            chamada_tool("executar_sql", {"sql": "SELECT id FROM linhas WHERE numero = '562'"}, "call_1"),
            chamada_tool("executar_sql", {"sql": "SELECT COUNT(*) FROM alertas WHERE linha_id = 1"}, "call_2"),
            {"role": "assistant", "content": "Consulta concluída com os resultados observados."},
        ])
        resultado = Agente(llm).perguntar("descubra a linha e depois conte alertas")
        self.assertEqual(len(resultado.passos), 2)
        self.assertEqual(resultado.passos[0]["ferramenta"], "sql")
        self.assertEqual(resultado.passos[1]["ferramenta"], "sql")
        self.assertEqual(resultado.texto, "Consulta concluída com os resultados observados.")
        self.assertEqual(len(llm.opcoes), 3)
        self.assertTrue(all(opcao["parallel_tool_calls"] is False for opcao in llm.opcoes))

    def test_tool_calling_nativo_esquema(self):
        llm = RoteiroNativo([
            chamada_tool("consultar_esquema", {"consulta": "alertas por linha"}),
            {"role": "assistant", "content": "O esquema confirma a tabela alertas."},
        ])
        resultado = Agente(llm).perguntar("qual tabela guarda os alertas?")
        self.assertEqual(resultado.passos[0]["ferramenta"], "esquema")
        self.assertIn("alertas", resultado.passos[0]["observacao"])

    def test_tool_calling_nativo_revisa_resultado_vazio(self):
        llm = RoteiroNativo([
            chamada_tool("executar_sql", {"sql": "SELECT numero FROM linhas WHERE numero = 'NAO_EXISTE'"}),
            {"role": "assistant", "content": "A consulta revisada não encontrou registros."},
        ])
        resultado = Agente(llm).perguntar("teste de resultado vazio")
        self.assertIn("Resultado vazio ou zerado", llm.vistas[1][-1]["content"])
        self.assertEqual(resultado.texto, "A consulta revisada não encontrou registros.")

    def test_tool_calling_nativo_respeita_limite_de_acoes(self):
        llm = RoteiroNativo([
            chamada_tool("executar_sql", {"sql": "SELECT COUNT(*) FROM linhas"}),
            {"role": "assistant", "content": "Finalizei com os dados que confirmei."},
        ])
        resultado = Agente(llm, max_passos=1).perguntar("pergunta")
        self.assertEqual(resultado.texto, "Finalizei com os dados que confirmei.")
        self.assertEqual(len(resultado.passos), 1)
        self.assertEqual(llm.opcoes[-1]["tools"], [])

    def test_tool_calling_nativo_bloqueia_escrita(self):
        llm = RoteiroNativo([
            chamada_tool("executar_sql", {"sql": "DELETE FROM linhas"}),
            {"role": "assistant", "content": "Não posso alterar os dados."},
        ])
        with sqlite3.connect(DB_PATH) as con:
            antes = con.execute("SELECT COUNT(*) FROM linhas").fetchone()[0]
        resultado = Agente(llm).perguntar("apague a tabela")
        with sqlite3.connect(DB_PATH) as con:
            depois = con.execute("SELECT COUNT(*) FROM linhas").fetchone()[0]
        self.assertIn("bloqueado", resultado.passos[0]["observacao"])
        self.assertEqual(antes, depois)

    def test_cache_tool_calling_nativo(self):
        class Cliente:
            nome = "cliente-nativo"
            chamadas = 0
            def complete_with_tools(self, system, messages, tools, tool_choice="auto", parallel_tool_calls=False):
                self.chamadas += 1
                return {"role": "assistant", "content": None,
                        "tool_calls": [{"id": "call_cache", "type": "function",
                                        "function": {"name": "executar_sql", "arguments": "{\"sql\":\"SELECT 1\"}"}}]}
            def complete(self, system, messages):
                return "ok"
        with tempfile.TemporaryDirectory() as diretorio:
            cliente = Cliente()
            cache = CachedLLM(cliente, cache_dir=diretorio)
            argumentos = ("system", [{"role": "user", "content": "teste"}],
                          [{"type": "function", "function": {"name": "executar_sql"}}])
            primeira = cache.complete_with_tools(*argumentos)
            segunda = cache.complete_with_tools(*argumentos)
            self.assertEqual(primeira, segunda)
            self.assertEqual(cliente.chamadas, 1)


class TestPerguntasAgente(unittest.TestCase):
    def test_contem_hifen_unicode(self):
        self.assertTrue(contem("Na sexta\u2011feira, placa SIN\u20110049", ["sexta", "SIN-0049"]))
        self.assertTrue(contem("dia 2026\u201110\u201109", ["2026-10-09"]))
        self.assertFalse(contem("SIN\u20110050", ["SIN-0049"]))

    def test_limite_diario_nao_espera(self):
        class Dia:
            nome = "x"
            def complete(self, system, messages):
                raise LLMErro("HTTP 429 Rate limit on tokens per day (TPD): try again in 2h10m")
        with mock.patch("infofrota_ai.agente.time.sleep") as dormir:
            with self.assertRaises(LimiteDiario):
                ComEspera(Dia()).complete("s", [])
        dormir.assert_not_called()

    def test_contem(self):
        self.assertTrue(contem("Vitória lidera", ["vitoria"]))
        self.assertTrue(contem("às 17h", ["17|17h"]))
        self.assertFalse(contem("são 1562 alertas", ["562"]))
        self.assertFalse(contem("média 6.5", ["6"]))

    def test_referencias_batem_com_esperado(self):
        questoes = json.loads(QUESTOES.read_text(encoding="utf-8"))
        self.assertEqual(len(questoes), 13)
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            for questao in questoes:
                saida = [con.execute(sql).fetchall() for sql in questao["passos_ref"]]
                self.assertTrue(contem(json.dumps(saida, ensure_ascii=False, default=str), questao["esperado"]),
                                questao["id"])
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
