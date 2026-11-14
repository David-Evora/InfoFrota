"""Demo pública do agente do InfoFrota (Hugging Face Space, Gradio).

Banco 100% sintético, gerado na subida com semente fixa. A chave do provedor LLM vem só dos Secrets do Space
(OPENAI_API_KEY) e nunca aparece na interface. Limites contra abuso: uma pergunta por vez, teto por IP e por dia.

Secrets/Variables do Space:
    OPENAI_API_KEY (secret)
    INFOFROTA_PROVIDER=openai   INFOFROTA_MODEL=openai/gpt-oss-120b   OPENAI_BASE_URL=https://api.groq.com/openai/v1
    INFOFROTA_SPACE_LIMITE_DIA (150)   INFOFROTA_SPACE_LIMITE_IP_HORA (10)
"""
import os
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from infofrota_ai.agente import Agente, ComEspera, LimiteDiario   # noqa: E402
from infofrota_ai.db import DB_PATH                                  # noqa: E402
from infofrota_ai.llm import LLMErro, llm_do_ambiente                # noqa: E402

EXEMPLOS = [
    "Qual linha tem mais alertas críticos e em que hora eles mais acontecem nessa linha?",
    "Qual município concentra mais alertas críticos e qual linha mais contribui para ele?",
    "Qual parada tem mais alertas críticos e em quantas linhas diferentes?",
]
MAX_CHARS = 300
AVISO = ("Demo com **dados sintéticos** (linhas reais da CETURBES, frota, viagens e lotação gerados por código). "
         "Não representa a operação real. O agente consulta o banco várias vezes; pode levar até 1 minuto "
         "por causa do limite gratuito do provedor.")

_estado = {"agente": None, "dia": (None, 0), "ips": defaultdict(deque), "lock": threading.Lock()}


def garantir_banco():
    if not Path(DB_PATH).exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True)


def _agente() -> Agente:
    if _estado["agente"] is None:
        _estado["agente"] = Agente(ComEspera(llm_do_ambiente(), tentativas=4), max_passos=6)
    return _estado["agente"]


def liberar(ip: str, agora=None) -> str:
    """Devolve "" se a pergunta pode seguir, ou a mensagem de recusa."""
    agora = agora if agora is not None else time.time()
    dia = time.strftime("%Y-%m-%d", time.gmtime(agora))
    data, n = _estado["dia"]
    n = n if data == dia else 0
    if n >= int(os.environ.get("INFOFROTA_SPACE_LIMITE_DIA", "150")):
        return "A demo atingiu o limite de perguntas de hoje. Tente amanhã."
    fila = _estado["ips"][ip]
    while fila and agora - fila[0] > 3600:
        fila.popleft()
    if len(fila) >= int(os.environ.get("INFOFROTA_SPACE_LIMITE_IP_HORA", "10")):
        return "Limite de perguntas por hora atingido para o seu acesso. Tente mais tarde."
    fila.append(agora)
    _estado["dia"] = (dia, n + 1)
    return ""


def formatar_passos(passos) -> str:
    blocos = []
    for i, p in enumerate(passos, 1):
        if p.get("ferramenta") == "sql":
            blocos.append(f"**{i}. SQL**\n```sql\n{p['entrada']}\n```\n`{(p.get('observacao') or '')[:300]}`")
        elif p.get("ferramenta") == "esquema":
            blocos.append(f"**{i}. Esquema:** {p['entrada']}")
    return "\n\n".join(blocos) or "_Sem consultas._"


def responder(pergunta: str, ip: str = "?", agente=None):
    pergunta = (pergunta or "").strip()
    if len(pergunta) < 3:
        return "Escreva uma pergunta.", ""
    if len(pergunta) > MAX_CHARS:
        return f"A pergunta passa de {MAX_CHARS} caracteres.", ""
    recusa = liberar(ip)
    if recusa:
        return recusa, ""
    try:
        with _estado["lock"]:        # uma pergunta por vez: protege a cota do provedor
            r = (agente or _agente()).perguntar(pergunta)
    except LimiteDiario:
        return "A cota diária do provedor de modelo acabou. Tente amanhã.", ""
    except LLMErro:
        return "O provedor de modelo não respondeu agora. Tente de novo em instantes.", ""
    except Exception:
        return "Falha ao configurar o modelo da demo.", ""
    return (r.texto or f"Sem resposta: {r.erro}") + f"\n\n_{r.nota}_", formatar_passos(r.passos)


def construir():
    import gradio as gr

    def ao_enviar(pergunta, request: gr.Request):
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
        return responder(pergunta, ip)

    with gr.Blocks(title="InfoFrota AI — agente de dados") as demo:
        gr.Markdown("# InfoFrota AI — agente de dados\nPergunte em português sobre alertas de lotação de ônibus da Grande Vitória.")
        gr.Markdown(AVISO)
        entrada = gr.Textbox(label="Pergunta", max_length=MAX_CHARS, lines=2)
        botao = gr.Button("Perguntar", variant="primary")
        resposta = gr.Markdown(label="Resposta")
        with gr.Accordion("Passos do agente (consultas SQL)", open=False):
            passos = gr.Markdown()
        gr.Examples(EXEMPLOS, inputs=entrada)
        botao.click(ao_enviar, entrada, [resposta, passos])
        entrada.submit(ao_enviar, entrada, [resposta, passos])
        gr.Markdown("Código: [github.com/David-Evora/InfoFrota](https://github.com/David-Evora/InfoFrota)")
    return demo


if __name__ == "__main__":
    garantir_banco()
    construir().queue(max_size=5).launch()
