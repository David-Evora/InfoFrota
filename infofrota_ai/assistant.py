"""Pipeline: pergunta -> LLM gera SQL -> guarda -> execução -> (reparo) -> resposta."""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from . import prompts
from .db import DB_PATH, SQLBloqueado, SQLErro, executar, limpar_sql


class RespostaInvalida(ValueError):
    pass


def interpretar(bruto: str) -> dict:
    """Extrai {pode_responder, sql, motivo} da saída do modelo.

    Aceita JSON puro, JSON dentro de cercas ``` e, como último recurso, SQL solto
    (útil para modelos pequenos com LoRA que respondem só com a consulta)."""
    texto = (bruto or "").strip()
    achado = re.search(r"\{.*\}", texto, re.S)
    if achado:
        try:
            dados = json.loads(achado.group(0))
            if isinstance(dados, dict):
                sql = limpar_sql(str(dados.get("sql") or ""))
                pode = dados.get("pode_responder", bool(sql))
                return {"pode_responder": bool(pode) and bool(sql), "sql": sql,
                        "motivo": str(dados.get("motivo") or "")}
        except json.JSONDecodeError:
            pass
    cerca = re.search(r"```(?:sql)?\s*(.*?)```", texto, re.S | re.I)
    candidato = limpar_sql(cerca.group(1) if cerca else texto)
    if re.match(r"(?is)(select|with)\b", candidato):
        return {"pode_responder": True, "sql": candidato, "motivo": ""}
    raise RespostaInvalida(f"saída do modelo não reconhecida: {texto[:120]!r}")


@dataclass
class Resposta:
    pergunta: str
    pode_responder: bool = False
    sql: Optional[str] = None
    colunas: list = field(default_factory=list)
    linhas: list = field(default_factory=list)
    truncado: bool = False
    texto: Optional[str] = None
    motivo: str = ""
    erro: Optional[str] = None
    bloqueado: bool = False
    tentativas: int = 0
    nota: str = prompts.NOTA_DADOS


class Assistente:
    def __init__(self, llm, db_path=DB_PATH, shots=3, max_reparos=1, max_linhas=200, compacto=False, rag=False):
        self.llm, self.db_path = llm, db_path
        self.shots, self.max_reparos, self.max_linhas = shots, max_reparos, max_linhas
        self.compacto, self.system = compacto, prompts.montar_system(db_path, compacto)
        self.indice = None
        if rag:
            from .rag import Indice
            self.indice = Indice(db_path)

    def perguntar(self, pergunta: str, responder_em_texto: bool = True) -> Resposta:
        r = Resposta(pergunta=pergunta)
        msgs = prompts.mensagens_exemplo(self.shots) + [{"role": "user", "content": pergunta}]
        system = self.system if not self.indice else prompts.montar_system(
            self.db_path, self.compacto, self.indice.contexto(pergunta))

        for tentativa in range(self.max_reparos + 1):
            r.tentativas = tentativa + 1
            bruto = self.llm.complete(system, msgs)
            try:
                dados = interpretar(bruto)
            except RespostaInvalida as e:
                r.erro = str(e)
                return r
            r.sql, r.motivo = dados["sql"] or None, dados["motivo"]
            if not dados["pode_responder"]:
                r.pode_responder = False
                return r
            try:
                res = executar(dados["sql"], self.db_path, self.max_linhas)
            except SQLBloqueado as e:
                r.pode_responder, r.bloqueado, r.erro = True, True, str(e)
                return r
            except SQLErro as e:
                r.erro = str(e)
                if tentativa < self.max_reparos:
                    msgs += [{"role": "assistant", "content": bruto},
                             {"role": "user", "content":
                              f"A consulta falhou com o erro: {e}. Corrija e responda no mesmo formato JSON."}]
                    continue
                r.pode_responder = True
                return r
            r.pode_responder, r.erro = True, None
            r.colunas, r.linhas, r.truncado = res.colunas, res.linhas, res.truncado
            break

        if responder_em_texto:
            r.texto = self.llm.complete(prompts.SYSTEM_TEXTO, [{"role": "user", "content":
                      prompts.mensagem_texto(pergunta, r.sql, r.colunas, r.linhas, r.truncado)}]).strip()
        return r
