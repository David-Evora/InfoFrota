"""API HTTP do InfoFrota AI (FastAPI), pensada para o n8n e para o site web.

Rodar:   pip install -r requirements-api.txt
         python -m infofrota_ai.api              # http://127.0.0.1:8000

Endpoints
  GET  /saude      estado do serviço e período dos dados
  POST /perguntar  pergunta em português -> SQL -> resultado (+ texto opcional)
  GET  /alertas    alertas numa janela de tempo (sem LLM; para o n8n consultar)
  GET  /resumo     resumo de um dia por linha (sem LLM)

Configuração por variáveis de ambiente
  INFOFROTA_PROVIDER / INFOFROTA_MODEL / INFOFROTA_BASE_URL   provedor do modelo
  INFOFROTA_PROMPT (ultra)   INFOFROTA_RAG (1)   INFOFROTA_SHOTS (0)
  INFOFROTA_API_KEY          se definida, exige o cabeçalho X-API-Key
  INFOFROTA_CORS             origens permitidas, separadas por vírgula
  INFOFROTA_LIMITE_POR_MIN   pedidos a /perguntar por minuto por IP (30)
  INFOFROTA_DB               caminho do banco SQLite
  INFOFROTA_WEB              pasta do site servida em "/" (padrão: docs/site; "0" desliga)

O único frontend do projeto é docs/site/index.html, servido pela própria API na raiz.
A página não guarda credenciais: a chave do provedor LLM permanece no backend.
O modelo só é carregado no primeiro /perguntar; /saude, /alertas e /resumo funcionam sem ele.
Os dados são sintéticos; o "agora" dos alertas é o momento do último alerta do banco.
"""
import hmac
import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import prompts
from .assistant import Assistente
from .db import DB_PATH, conectar
from .llm import llm_do_ambiente

DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATAHORA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$")


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500, description="Pergunta em português")
    texto: bool = Field(False, description="Se verdadeiro, devolve também uma resposta em texto (uma chamada extra ao modelo)")


def _linhas(con, sql, params=()):
    cur = con.execute(sql, params)
    nomes = [c[0] for c in cur.description]
    return [dict(zip(nomes, r)) for r in cur.fetchall()]


def create_app(assistente: Optional[Assistente] = None, db_path=None) -> FastAPI:
    db_path = db_path or os.environ.get("INFOFROTA_DB") or DB_PATH
    app = FastAPI(
        title="InfoFrota AI",
        version="1.0",
        description="Text-to-SQL sobre a lotação de ônibus da Grande Vitória. " + prompts.NOTA_DADOS,
    )
    estado = {"bot": assistente, "lock": threading.Lock(), "acessos": defaultdict(deque)}

    origens = [o.strip() for o in os.environ.get("INFOFROTA_CORS", "").split(",") if o.strip()]
    if origens:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origens,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    def autenticar(x_api_key: Optional[str] = Header(None)):
        chave = os.environ.get("INFOFROTA_API_KEY")
        if chave and not (x_api_key and hmac.compare_digest(x_api_key, chave)):
            raise HTTPException(401, "X-API-Key ausente ou inválida")

    def assistente_pronto() -> Assistente:
        if estado["bot"] is None:
            try:
                llm = llm_do_ambiente()
                estado["bot"] = Assistente(
                    llm,
                    db_path=db_path,
                    shots=int(os.environ.get("INFOFROTA_SHOTS", "0")),
                    compacto=prompts.MODOS[os.environ.get("INFOFROTA_PROMPT", "ultra")],
                    rag=os.environ.get("INFOFROTA_RAG", "1") not in ("0", "false", ""),
                )
            except Exception as e:  # configuração ausente, chave inválida, modelo indisponível
                raise HTTPException(503, f"modelo não configurado: {e}")
        return estado["bot"]

    def limitar(request: Request):
        limite = int(os.environ.get("INFOFROTA_LIMITE_POR_MIN", "30"))
        fila, agora = estado["acessos"][request.client.host if request.client else "?"], time.monotonic()
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= limite:
            raise HTTPException(429, "muitos pedidos; tente novamente em instantes")
        fila.append(agora)

    @app.get("/saude")
    def saude():
        ini, fim, n = prompts._periodo(db_path)
        bot = estado["bot"]
        return {
            "status": "ok",
            "periodo": [ini, fim],
            "linhas_monitoradas": n,
            "modelo": getattr(getattr(bot, "llm", None), "nome", None),
            "nota": prompts.NOTA_DADOS,
        }

    @app.post("/perguntar", dependencies=[Depends(autenticar), Depends(limitar)])
    def perguntar(corpo: PerguntaIn):
        bot = assistente_pronto()
        try:
            with estado["lock"]:  # um modelo local não atende dois pedidos ao mesmo tempo
                resp = bot.perguntar(corpo.pergunta.strip(), responder_em_texto=corpo.texto)
        except Exception as e:
            raise HTTPException(502, f"falha ao consultar o modelo: {e}")
        return asdict(resp)

    @app.get("/alertas", dependencies=[Depends(autenticar)])
    def alertas(
        tipo: Optional[str] = Query(None, pattern="^(ATENCAO|CRITICO)$"),
        janela_horas: int = Query(24, ge=1, le=720),
        limite: int = Query(50, ge=1, le=200),
        referencia: Optional[str] = Query(None, description="AAAA-MM-DD HH:MM:SS; padrão: último alerta do banco"),
    ):
        if referencia and not DATAHORA_RE.match(referencia):
            raise HTTPException(422, "referencia deve ser AAAA-MM-DD HH:MM:SS")
        con = conectar(db_path)
        try:
            ref = (referencia or "").replace("T", " ") or con.execute("SELECT MAX(criado_em) FROM alertas").fetchone()[0]
            if not ref:
                return {"referencia": None, "janela_horas": janela_horas, "total": 0, "alertas": []}
            filtro = "a.criado_em > datetime(?, ?) AND a.criado_em <= ?" + (" AND a.tipo = ?" if tipo else "")
            args = [ref, f"-{janela_horas} hours", ref] + ([tipo] if tipo else [])
            total = con.execute(f"SELECT COUNT(*) FROM alertas a WHERE {filtro}", args).fetchone()[0]
            lista = _linhas(
                con,
                f"""
                SELECT a.id, l.numero AS linha, l.nome AS linha_nome, p.nome AS parada, a.tipo,
                       ROUND(a.percentual, 1) AS percentual, a.criado_em, a.mensagem,
                       a.em_precaucao, a.precaucao_descricao, a.resolvido
                FROM alertas a JOIN linhas l ON l.id = a.linha_id LEFT JOIN paradas p ON p.id = a.parada_id
                WHERE {filtro} ORDER BY a.percentual DESC, a.id LIMIT ?""",
                args + [limite],
            )
        finally:
            con.close()
        return {"referencia": ref, "janela_horas": janela_horas, "total": total, "alertas": lista}

    @app.get("/resumo", dependencies=[Depends(autenticar)])
    def resumo(
        data: Optional[str] = Query(None, description="AAAA-MM-DD; padrão: último dia do banco"),
        limite: int = Query(5, ge=1, le=50, description="Quantas linhas devolver, da mais cheia para a menos cheia"),
    ):
        if data and not DATA_RE.match(data):
            raise HTTPException(422, "data deve ser AAAA-MM-DD")
        con = conectar(db_path)
        try:
            dia = data or con.execute("SELECT MAX(data) FROM resumos_dia").fetchone()[0]
            linhas = _linhas(
                con,
                """
                SELECT l.numero AS linha, l.nome AS linha_nome, l.tipo, ROUND(d.media_percentual, 1) AS media_percentual,
                       ROUND(d.max_percentual, 1) AS max_percentual, d.hora_pico,
                       d.total_alertas_atencao, d.total_alertas_critico
                FROM resumos_dia d JOIN linhas l ON l.id = d.linha_id
                WHERE d.data = ? ORDER BY d.media_percentual DESC""",
                (dia,),
            )
        finally:
            con.close()
        if not linhas:
            raise HTTPException(404, f"sem dados para {dia}")
        return {
            "data": dia,
            "linhas": linhas[:limite],
            "total_linhas": len(linhas),
            "totais": {
                "atencao": sum(r["total_alertas_atencao"] or 0 for r in linhas),
                "critico": sum(r["total_alertas_critico"] or 0 for r in linhas),
            },
        }

    # Único frontend do projeto: o site de apresentação em docs/site/, servido na raiz.
    # Os endpoints da API foram registrados antes do mount e continuam acessíveis.
    web = os.environ.get("INFOFROTA_WEB", "")
    if web != "0":
        pasta = Path(web) if web else Path(__file__).resolve().parent.parent / "docs" / "site"
        if (pasta / "index.html").is_file():
            app.mount("/", StaticFiles(directory=pasta, html=True), name="web")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("INFOFROTA_HOST", "127.0.0.1"),
                port=int(os.environ.get("INFOFROTA_PORT", "8000")))
