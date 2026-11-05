import json, re, unittest
from pathlib import Path
from infofrota_ai import prompts
from infofrota_ai.assistant import interpretar
from infofrota_ai.db import DB_PATH, executar

ROOT = Path(__file__).resolve().parent.parent
LIN = [json.loads(l) for l in (ROOT / "training/dataset.jsonl").read_text(encoding="utf-8").splitlines()]
TESTE = json.loads((ROOT / "evaluation/questions.json").read_text(encoding="utf-8"))


def esq(sql):
    return re.sub(r"\s+", " ", re.sub(r"'[^']*'|\b\d+(\.\d+)?\b", "?", sql.lower())).strip()


class TreinoTest(unittest.TestCase):
    def test_sql_valido(self):
        for e in LIN:
            if e["pode_responder"]:
                executar(e["sql"], DB_PATH)

    def test_sem_vazamento(self):
        perg = {q["pergunta"].lower() for q in TESTE}
        sqls = {esq(q["sql"]) for q in TESTE if q.get("sql")}
        for e in LIN:
            self.assertNotIn(e["pergunta"].lower(), perg)
            if e["pode_responder"]:
                self.assertNotIn(esq(e["sql"]), sqls)

    def test_modo_limpo(self):
        self.assertFalse([e for e in LIN if e["proximo"]])

    def test_recusas(self):
        r = [e for e in LIN if not e["pode_responder"]]
        self.assertTrue(0.04 < len(r) / len(LIN) < 0.2)
        self.assertTrue(all(e["motivo"] and not e["sql"] for e in r))

    def test_chat(self):
        sysm = prompts.montar_system(DB_PATH, compacto=True)  # o treino v1 usou o modo compacto
        for arq in ("train_chat.jsonl", "val_chat.jsonl"):
            for l in (ROOT / "training" / arq).read_text(encoding="utf-8").splitlines():
                m = json.loads(l)["messages"]
                self.assertEqual([x["role"] for x in m], ["system", "user", "assistant"])
                self.assertEqual(m[0]["content"], sysm)
                d = interpretar(m[2]["content"])
                self.assertIn("pode_responder", d)


if __name__ == "__main__":
    unittest.main()
