import json
import unittest

from infofrota_ai.assistant import Assistente
from infofrota_ai.db import DB_PATH
from infofrota_ai.evaluate import QUESTOES
from infofrota_ai.rag import Indice

IDX = Indice(DB_PATH)


class RagTest(unittest.TestCase):
    def ctx(self, p):
        return IDX.contexto(p)

    def test_valores_categoricos(self):
        casos = [("Quais ônibus estão com status de manutenção?", "'manutencao'"),
                 ("Quais alertas tiveram precaução de reforço?", "Ônibus de reforço despachado"),
                 ("Que feriados existem no calendário?", "Finados"),
                 ("Quantas viagens de volta foram canceladas?", "'cancelada'"),
                 ("Qual a temperatura nas horas de chuva forte?", "chuva_forte"),
                 ("Quais alertas críticos estão abertos?", "'CRITICO'")]
        for pergunta, esperado in casos:
            self.assertIn(esperado, self.ctx(pergunta), pergunta)

    def test_tabela_certa(self):
        self.assertIn("- calendario(", self.ctx("Qual o nome do feriado?"))
        self.assertIn("- clima_hora(", self.ctx("Qual foi a temperatura ontem?"))
        self.assertIn("- onibus(", self.ctx("Qual a placa do ônibus?"))

    def test_pergunta_sem_relacao_nao_quebra(self):
        self.assertTrue(self.ctx("zzz qqq").startswith("CONTEXTO"))

    def test_indice_nao_contem_perguntas_de_teste(self):
        perguntas = [q["pergunta"] for q in json.loads(QUESTOES.read_text(encoding="utf-8"))]
        corpus = " ".join(d.texto for d in IDX.docs)
        for p in perguntas:
            self.assertNotIn(p, corpus)

    def test_assistente_injeta_contexto_so_com_rag(self):
        class Grava:
            nome = "grava"

            def __init__(self):
                self.systems = []

            def complete(self, system, messages):
                self.systems.append(system)
                return '{"pode_responder": false, "sql": "", "motivo": "x"}'

        a, b = Grava(), Grava()
        Assistente(a, rag=True).perguntar("Quais ônibus estão em manutenção?", responder_em_texto=False)
        Assistente(b).perguntar("Quais ônibus estão em manutenção?", responder_em_texto=False)
        self.assertIn("CONTEXTO RECUPERADO", a.systems[0])
        self.assertIn("'manutencao'", a.systems[0])
        self.assertNotIn("CONTEXTO RECUPERADO", b.systems[0])


if __name__ == "__main__":
    unittest.main()
