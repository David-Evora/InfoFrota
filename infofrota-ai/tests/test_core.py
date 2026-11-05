"""Testes do núcleo. Rode com:  python -m unittest discover -s tests -v
(precisa do banco: python scripts/generate_data.py)"""
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from infofrota_ai import prompts
from infofrota_ai.assistant import Assistente, RespostaInvalida, interpretar
from infofrota_ai.compare import DIFERENTE, EXTRAS, OK, comparar
from infofrota_ai.db import DB_PATH, SQLBloqueado, SQLErro, executar
from infofrota_ai.evaluate import QUESTOES, executar_avaliacao
from infofrota_ai.fakes import EscritaLLM, NaiveLLM, OracleLLM
from infofrota_ai.llm import CachedLLM, OpenAICompatLLM

QUESTOES_JSON = json.loads(QUESTOES.read_text(encoding="utf-8"))


def hash_banco():
    return hashlib.sha256(DB_PATH.read_bytes()).hexdigest()


class TestGuarda(unittest.TestCase):
    PERIGOSOS = [
        "DELETE FROM alertas",
        "UPDATE linhas SET nome = 'x'",
        "INSERT INTO linhas (numero, nome) VALUES ('999', 'x')",
        "DROP TABLE alertas",
        "CREATE TABLE t (a INT)",
        "PRAGMA writable_schema = 1",
        "ATTACH DATABASE '/tmp/x.db' AS x",
        "SELECT 1; DELETE FROM alertas",
        "WITH x AS (SELECT 1) DELETE FROM alertas",
        "REPLACE INTO linhas (numero, nome) VALUES ('999', 'x')",
        "VACUUM",
        "-- comentário\nDELETE FROM alertas",
        "/* c */ DROP TABLE alertas",
        "SELECT load_extension('x')",
    ]

    def test_bloqueia_escrita_e_nao_altera_o_banco(self):
        antes = hash_banco()
        for sql in self.PERIGOSOS:
            with self.subTest(sql=sql):
                with self.assertRaises((SQLBloqueado, SQLErro)):
                    executar(sql)
        self.assertEqual(antes, hash_banco())

    def test_permite_leitura(self):
        self.assertEqual(executar("SELECT COUNT(*) FROM linhas").linhas, [[165]])
        self.assertEqual(executar("```sql\nSELECT 1 AS a;\n```").linhas, [[1]])
        self.assertEqual(executar("-- ok\nSELECT 2").linhas, [[2]])
        self.assertEqual(executar("WITH x AS (SELECT 3 AS a) SELECT a FROM x").linhas, [[3]])
        self.assertEqual(executar("WITH RECURSIVE c(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM c "
                                  "WHERE n < 5) SELECT SUM(n) FROM c").linhas, [[15]])
        self.assertTrue(executar("SELECT * FROM v_lotacao_clima LIMIT 1").linhas)

    def test_limite_de_linhas(self):
        r = executar("SELECT id FROM registros_ocupacao", max_linhas=10)
        self.assertEqual(len(r.linhas), 10)
        self.assertTrue(r.truncado)

    def test_timeout(self):
        sql = ("WITH RECURSIVE c(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM c WHERE n < 1000000000) "
               "SELECT COUNT(*) FROM c")
        with self.assertRaises(SQLErro) as ctx:
            executar(sql, timeout_s=0.5)
        self.assertIn("demorou", str(ctx.exception))

    def test_erro_de_sql_e_distinto_de_bloqueio(self):
        with self.assertRaises(SQLErro):
            executar("SELECT coluna_que_nao_existe FROM linhas")


class TestInterpretar(unittest.TestCase):
    def test_json_puro(self):
        r = interpretar('{"pode_responder": true, "sql": "SELECT 1;", "motivo": ""}')
        self.assertEqual((r["pode_responder"], r["sql"]), (True, "SELECT 1"))

    def test_json_em_cerca_e_com_texto(self):
        r = interpretar('Claro!\n```json\n{"pode_responder": true, "sql": "SELECT 1"}\n```')
        self.assertEqual(r["sql"], "SELECT 1")

    def test_recusa(self):
        r = interpretar('{"pode_responder": false, "sql": "", "motivo": "sem GPS"}')
        self.assertFalse(r["pode_responder"])
        self.assertEqual(r["motivo"], "sem GPS")

    def test_sql_solto_e_cerca_sql(self):
        self.assertEqual(interpretar("SELECT 1")["sql"], "SELECT 1")
        self.assertEqual(interpretar("```sql\nSELECT 2;\n```")["sql"], "SELECT 2")

    def test_invalido(self):
        with self.assertRaises(RespostaInvalida):
            interpretar("não sei")


class TestComparar(unittest.TestCase):
    def test_ordem_das_linhas(self):
        esp = [["a", 1], ["b", 2]]
        self.assertEqual(comparar(esp, [["b", 2], ["a", 1]], ordenada=False)[0], OK)
        self.assertEqual(comparar(esp, [["b", 2], ["a", 1]], ordenada=True)[0], DIFERENTE)

    def test_ordem_das_colunas_e_nomes_nao_importam(self):
        self.assertEqual(comparar([["a", 1]], [[1, "a"]])[0], OK)

    def test_colunas_extras(self):
        self.assertEqual(comparar([["a"]], [["a", 9]])[0], EXTRAS)
        self.assertEqual(comparar([["a"]], [[9, "a"]])[0], EXTRAS)

    def test_tolerancia_so_para_decimais(self):
        self.assertEqual(comparar([[28.9]], [[28.93]])[0], OK)
        self.assertEqual(comparar([[15123.0]], [[15123.4]])[0], OK)
        self.assertEqual(comparar([[28.9]], [[29.5]])[0], DIFERENTE)
        self.assertEqual(comparar([[5]], [[6]])[0], DIFERENTE)
        self.assertEqual(comparar([[111127]], [[111128]])[0], DIFERENTE)
        self.assertEqual(comparar([[5]], [[5.0]])[0], OK)

    def test_vazio_e_nulo_sao_equivalentes(self):
        self.assertEqual(comparar([[None]], [])[0], OK)
        self.assertEqual(comparar([[None]], [[None]])[0], OK)
        self.assertEqual(comparar([[None]], [[3]])[0], DIFERENTE)
        self.assertEqual(comparar([[3]], [])[0], DIFERENTE)

    def test_linhas_a_mais_ou_a_menos(self):
        self.assertEqual(comparar([["a"], ["b"]], [["a"]])[0], DIFERENTE)
        self.assertEqual(comparar([["a"]], [["a"], ["b"]])[0], DIFERENTE)

    def test_nao_aceita_coluna_repetida_como_acerto(self):
        # esperado (a, b); obtido (a, a) não pode casar
        self.assertEqual(comparar([["a", "b"]], [["a", "a"]])[0], DIFERENTE)


class TestPrompts(unittest.TestCase):
    def test_exemplos_nao_vazam_para_a_avaliacao(self):
        perguntas = {q["pergunta"] for q in QUESTOES_JSON}
        sqls = {q["sql"] for q in QUESTOES_JSON if q["sql"]}
        for pergunta, resposta in prompts.EXEMPLOS:
            self.assertNotIn(pergunta, perguntas)
            self.assertNotIn(resposta["sql"], sqls)

    def test_system_tem_esquema_e_periodo(self):
        s = prompts.montar_system()
        for trecho in ("CREATE TABLE registros_ocupacao", "CREATE VIEW v_lotacao_clima",
                       "2026-11-03", "ATENCAO", "pode_responder", "TABELAS (o que cada linha",
                       "NÃO filtre por data"):
            self.assertIn(trecho, s)
        self.assertNotIn("sqlite_sequence", s)

    def test_prompt_nao_cita_perguntas_da_avaliacao(self):
        s = prompts.montar_system().lower()
        for q in QUESTOES_JSON:
            self.assertNotIn(q["pergunta"].lower().rstrip("?"), s)

    def test_exemplos_sao_sql_valido(self):
        for _, resposta in prompts.EXEMPLOS:
            if resposta["pode_responder"]:
                executar(resposta["sql"])


class SequenciaLLM:
    nome = "sequencia"

    def __init__(self, *respostas):
        self.respostas, self.chamadas = list(respostas), []

    def complete(self, system, messages):
        self.chamadas.append(messages)
        return self.respostas.pop(0)


def j(sql, pode=True, motivo=""):
    return json.dumps({"pode_responder": pode, "sql": sql, "motivo": motivo})


class TestAssistente(unittest.TestCase):
    def test_reparo_apos_erro_de_sql(self):
        llm = SequenciaLLM(j("SELECT nome_errado FROM linhas"), j("SELECT COUNT(*) FROM linhas"))
        r = Assistente(llm).perguntar("quantas linhas?", responder_em_texto=False)
        self.assertEqual((r.erro, r.linhas, r.tentativas), (None, [[165]], 2))
        self.assertIn("falhou com o erro", llm.chamadas[1][-1]["content"])

    def test_desiste_apos_o_reparo(self):
        llm = SequenciaLLM(j("SELECT x FROM linhas"), j("SELECT y FROM linhas"))
        r = Assistente(llm).perguntar("?", responder_em_texto=False)
        self.assertIsNotNone(r.erro)
        self.assertEqual(r.tentativas, 2)

    def test_recusa_nao_executa(self):
        r = Assistente(SequenciaLLM(j("", False, "sem GPS"))).perguntar("gps?", False)
        self.assertFalse(r.pode_responder)
        self.assertEqual(r.motivo, "sem GPS")

    def test_escrita_e_bloqueada_sem_reparo(self):
        llm = SequenciaLLM(j("DELETE FROM alertas"))
        antes = hash_banco()
        r = Assistente(llm).perguntar("apague", False)
        self.assertTrue(r.bloqueado)
        self.assertEqual(len(llm.chamadas), 1)
        self.assertEqual(antes, hash_banco())

    def test_texto_final_usa_segunda_chamada(self):
        llm = SequenciaLLM(j("SELECT COUNT(*) FROM linhas"), "São 165 linhas.")
        r = Assistente(llm).perguntar("quantas linhas?")
        self.assertEqual(r.texto, "São 165 linhas.")
        self.assertIn("sintéticos", r.nota)

    def test_saida_invalida(self):
        r = Assistente(SequenciaLLM("hmm")).perguntar("?", False)
        self.assertIn("não reconhecida", r.erro)


class TestAvaliador(unittest.TestCase):
    def test_oraculo_acerta_tudo(self):
        _, resumo = executar_avaliacao(OracleLLM(QUESTOES_JSON))
        self.assertEqual(resumo["TOTAL"]["acertos"], resumo["TOTAL"]["n"])
        self.assertEqual(resumo["TOTAL"]["n"], 56)

    def test_ingenuo_vai_mal(self):
        _, resumo = executar_avaliacao(NaiveLLM())
        self.assertLessEqual(resumo["TOTAL"]["acuracia"], 0.05)

    def test_modelo_de_escrita_e_barrado_pela_guarda(self):
        antes = hash_banco()
        res, _ = executar_avaliacao(EscritaLLM())
        fora = [r for r in res if r["id"] in ("L02", "L03", "L04", "L05", "L06")]
        self.assertTrue(all(r["status"] == "ok_guarda" for r in fora))
        self.assertEqual(antes, hash_banco())

    def test_formato_do_resumo(self):
        _, resumo = executar_avaliacao(OracleLLM(QUESTOES_JSON), apenas={"F01", "M01"})
        self.assertEqual(resumo["TOTAL"]["n"], 2)


class _ServidorFalso(BaseHTTPRequestHandler):
    recebidos = []

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _ServidorFalso.recebidos.append((self.path, corpo, dict(self.headers)))
        texto = j("SELECT COUNT(*) FROM linhas")
        if self.path.endswith("/chat/completions"):
            resp = {"choices": [{"message": {"role": "assistant", "content": texto}}]}
        else:  # API de mensagens da Anthropic
            resp = {"id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"],
                    "content": [{"type": "text", "text": texto}], "stop_reason": "end_turn",
                    "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}
        dados = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, *a):
        pass


class TestClientes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _ServidorFalso)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        _ServidorFalso.recebidos.clear()

    def test_openai_compat_ponta_a_ponta(self):
        llm = OpenAICompatLLM("modelo-x", base_url=self.url + "/v1", api_key="segredo")
        r = Assistente(llm).perguntar("quantas linhas?", responder_em_texto=False)
        self.assertEqual(r.linhas, [[165]])
        caminho, corpo, cab = _ServidorFalso.recebidos[0]
        self.assertTrue(caminho.endswith("/v1/chat/completions"))
        self.assertEqual(corpo["messages"][0]["role"], "system")
        self.assertIn("CREATE TABLE", corpo["messages"][0]["content"])
        self.assertEqual(corpo["temperature"], 0)
        self.assertEqual(cab["Authorization"], "Bearer segredo")

    def test_anthropic_ponta_a_ponta(self):
        try:
            from infofrota_ai.llm import AnthropicLLM
            llm = AnthropicLLM(model="claude-teste", api_key="chave-falsa", base_url=self.url)
        except ImportError:
            self.skipTest("pacote anthropic não instalado")
        r = Assistente(llm).perguntar("quantas linhas?", responder_em_texto=False)
        self.assertEqual(r.linhas, [[165]])
        caminho, corpo, _ = _ServidorFalso.recebidos[0]
        self.assertTrue(caminho.endswith("/v1/messages"))
        self.assertIn("CREATE TABLE", corpo["system"])
        self.assertEqual(corpo["messages"][-1], {"role": "user", "content": "quantas linhas?"})

    def test_cache_evita_segunda_chamada(self):
        with tempfile.TemporaryDirectory() as d:
            llm = CachedLLM(OpenAICompatLLM("m", base_url=self.url + "/v1"), cache_dir=d)
            a = llm.complete("sys", [{"role": "user", "content": "oi"}])
            b = llm.complete("sys", [{"role": "user", "content": "oi"}])
            self.assertEqual(a, b)
            self.assertEqual(len(_ServidorFalso.recebidos), 1)
            llm.complete("sys", [{"role": "user", "content": "outra"}])
            self.assertEqual(len(_ServidorFalso.recebidos), 2)


if __name__ == "__main__":
    unittest.main()
