from __future__ import annotations
import json
import urllib.request
import urllib.error
from .base import BaseProvider, LLMResponse, ToolCall


class OllamaProvider(BaseProvider):
    """
    Proveedor para Ollama local (http://localhost:11434).
    Usa la API /api/chat con soporte de tool_calls (Ollama >= 0.3).
    Sin API key, gratis, corre localmente.
    """

    def __init__(self, url: str = "http://localhost:11434"):
        self.url = url.rstrip("/")

    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs

        payload: dict = {"model": model, "messages": msgs, "stream": False}
        if tools:
            payload["tools"] = tools

        try:
            data = self._post(f"{self.url}/api/chat", payload)
        except Exception as e:
            return LLMResponse(text="", error=str(e))

        msg = data.get("message", {})
        text = msg.get("content", "") or ""
        raw_calls = msg.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                id=str(i),
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments") or {},
            )
            for i, tc in enumerate(raw_calls)
        ]
        return LLMResponse(text=text, tool_calls=tool_calls)

    def list_models(self) -> list[str]:
        try:
            data = self._get(f"{self.url}/api/tags")
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _post(self, url: str, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
