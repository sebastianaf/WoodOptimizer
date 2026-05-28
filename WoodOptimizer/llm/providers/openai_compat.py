from __future__ import annotations
import json
import urllib.request
import urllib.error
from .base import BaseProvider, LLMResponse, ToolCall


class OpenAICompatProvider(BaseProvider):
    """
    Provider for any OpenAI-compatible API (/v1/chat/completions).
    Works with: OpenAI, DeepSeek, Groq, LM Studio, Together AI, Mistral, etc.
    """

    def __init__(self, url: str = "https://api.openai.com", api_key: str = ""):
        # Strip trailing /v1 so we never double it when building endpoints
        base = url.rstrip("/")
        self.url = base[:-3] if base.endswith("/v1") else base
        self.api_key = api_key

    def _endpoint(self, path: str) -> str:
        return f"{self.url}/v1{path}"

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

        payload: dict = {"model": model, "messages": msgs}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            data = self._post(self._endpoint("/chat/completions"), payload)
        except Exception as e:
            return LLMResponse(error=str(e))

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        text = msg.get("content") or ""
        raw_calls = msg.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                id=tc.get("id", str(i)),
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"].get("arguments") or "{}"),
            )
            for i, tc in enumerate(raw_calls)
        ]
        return LLMResponse(text=text, tool_calls=tool_calls)

    def list_models(self) -> list[str]:
        try:
            data = self._get(self._endpoint("/models"))
            return sorted(m["id"] for m in data.get("data", []))
        except Exception:
            return []

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, url: str, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
