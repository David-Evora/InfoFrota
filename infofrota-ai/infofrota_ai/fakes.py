"""Modelos falsos para autoteste do avaliador (sem chave de API).

 * OracleLLM devolve o SQL de referência: o avaliador precisa dar 100%.
 * NaiveLLM sempre devolve a mesma consulta: o avaliador precisa dar nota baixa.
 Se um dos dois falhar, o problema está no avaliador, não no modelo.
"""
import json


class OracleLLM:
    nome = "oraculo"

    def __init__(self, questoes):
        self.por_pergunta = {q["pergunta"]: q for q in questoes}

    def complete(self, system, messages):
        for m in reversed(messages):
            q = self.por_pergunta.get(m["content"]) if m["role"] == "user" else None
            if q:
                if q["tipo"] == "sql":
                    return json.dumps({"pode_responder": True, "sql": q["sql"], "motivo": ""})
                return json.dumps({"pode_responder": False, "sql": "", "motivo": "fora do escopo"})
        return json.dumps({"pode_responder": False, "sql": "", "motivo": "desconhecida"})


class NaiveLLM:
    nome = "ingenuo"

    def complete(self, system, messages):
        return json.dumps({"pode_responder": True, "sql": "SELECT COUNT(*) FROM linhas",
                           "motivo": ""})


class EscritaLLM:
    """Obedece qualquer pedido, inclusive de escrita: testa a guarda de SQL."""
    nome = "escrita"

    def complete(self, system, messages):
        return json.dumps({"pode_responder": True, "sql": "DELETE FROM alertas WHERE resolvido = 1",
                           "motivo": ""})
