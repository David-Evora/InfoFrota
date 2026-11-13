"""Clientes de LLM para o InfoFrota AI.

Todos expõem nome e complete(system, messages). Clientes OpenAI-compatíveis
são estendidos com complete_with_tools() para Tool Calling nativo.
"""
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "evaluation" / "cache"


class LLMErro(RuntimeError):
    pass


class AnthropicLLM:
    def __init__(self, model=None, api_key=None, base_url=None, max_tokens=1024):
        import anthropic
        self.model = model or os.environ.get("INFOFROTA_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens
        self.nome = f"anthropic-{self.model}"
        self._client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

    def complete(self, system, messages):
        args = dict(model=self.model, max_tokens=self.max_tokens, system=system, messages=messages)
        try:
            resposta = self._client.messages.create(temperature=0, **args)
        except Exception as erro:
            if "temperature" not in str(erro).lower():
                raise LLMErro(str(erro)) from erro
            resposta = self._client.messages.create(**args)
        return "".join(bloco.text for bloco in resposta.content if getattr(bloco, "type", "") == "text")


class OpenAICompatLLM:
    def __init__(self, model, base_url=None, api_key=None, max_tokens=1024, timeout=120):
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.max_tokens, self.timeout = max_tokens, timeout
        self.nome = f"openai-{model}"

    def _post(self, payload):
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=corpo,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "infofrota-ai/1.0",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resposta:
                dados = json.load(resposta)
            return dados["choices"][0]
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", "replace")[:500]
            raise LLMErro(f"falha ao chamar {self.base_url}: HTTP {erro.code} {detalhe}") from erro
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as erro:
            raise LLMErro(f"falha ao chamar {self.base_url}: {erro}") from erro

    def complete(self, system, messages):
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        escolha = self._post(payload)
        return escolha["message"].get("content") or ""

    def complete_with_tools(self, system, messages, tools, tool_choice="auto", parallel_tool_calls=False):
        """Executa um turno de chat completions com ferramentas locais nativas."""
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}] + messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
        }
        escolha = self._post(payload)
        mensagem = escolha["message"]
        if not isinstance(mensagem, dict):
            raise LLMErro("resposta de Tool Calling sem objeto message válido")
        return mensagem


class CachedLLM:
    def __init__(self, llm, cache_dir=CACHE_DIR):
        self.llm, self.nome = llm, llm.nome
        self.supports_tool_calling = getattr(llm, "supports_tool_calling", callable(getattr(llm, "complete_with_tools", None)))
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _ler_ou_executar(self, chave_dados, executar_chamada):
        chave = hashlib.sha256(json.dumps(chave_dados, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        arquivo = self.dir / f"{chave}.json"
        if arquivo.exists():
            return json.loads(arquivo.read_text(encoding="utf-8"))["resposta"]
        resposta = executar_chamada()
        arquivo.write_text(json.dumps({"modelo": self.nome, "resposta": resposta}, ensure_ascii=False), encoding="utf-8")
        return resposta

    def complete(self, system, messages):
        # Mantém a mesma chave histórica da consulta única.
        return self._ler_ou_executar(
            [self.nome, system, messages],
            lambda: self.llm.complete(system, messages),
        )

    def complete_with_tools(self, system, messages, tools, tool_choice="auto", parallel_tool_calls=False):
        metodo = getattr(self.llm, "complete_with_tools", None)
        if metodo is None:
            raise LLMErro("o cliente subjacente não oferece Tool Calling nativo")
        # Namespace separado: não colide com o cache histórico de texto/JSON.
        return self._ler_ou_executar(
            [self.nome, "native-tool-calling", system, messages, tools, tool_choice, parallel_tool_calls],
            lambda: metodo(system, messages, tools, tool_choice, parallel_tool_calls),
        )


def llm_do_ambiente(provider=None, model=None, base_url=None):
    provider = (provider or os.environ.get("INFOFROTA_PROVIDER", "anthropic")).lower()
    if provider == "anthropic":
        return AnthropicLLM(model=model, base_url=base_url)
    if provider in ("openai", "openai-compat"):
        modelo = model or os.environ.get("INFOFROTA_MODEL")
        if not modelo:
            raise LLMErro("informe --model (ou INFOFROTA_MODEL) para o provider openai")
        return OpenAICompatLLM(modelo, base_url=base_url)
    if provider == "hf":
        from .hf_llm import HFLLM
        base, _, adaptador = (model or os.environ.get("INFOFROTA_MODEL", "")).partition("::")
        if not base:
            raise LLMErro("use --model BASE[::ADAPTADOR] com o provider hf")
        return HFLLM(base, adaptador or None)
    raise LLMErro(f"provider desconhecido: {provider}")
