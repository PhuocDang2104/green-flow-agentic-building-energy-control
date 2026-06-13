"""LLM provider abstraction — one OpenAI-compatible client covers most providers.

Groq, OpenAI, OpenRouter, Together, Fireworks, local Ollama đều nói "OpenAI
chat-completions" -> chỉ khác base_url + api_key + model. Vì vậy product chỉ cần
1 adapter + 1 registry; "select provider + nhập key + lưu" = chọn tên trong
registry rồi nạp key (đã mã hoá) từ keystore. Anthropic khác shape -> adapter riêng.

Không hardcode key ở đây — key đến từ settings/keystore (DB). Xem llm/keystore.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

# Provider name -> base_url mặc định (OpenAI-compatible). default_model gợi ý.
OPENAI_COMPATIBLE: dict[str, dict] = {
    "groq":       {"base_url": "https://api.groq.com/openai/v1", "default_model": "llama-3.3-70b-versatile"},
    "openai":     {"base_url": "https://api.openai.com/v1",      "default_model": "gpt-4.1-mini"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",   "default_model": "meta-llama/llama-3.3-70b-instruct"},
    "together":   {"base_url": "https://api.together.xyz/v1",    "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "ollama":     {"base_url": "http://localhost:11434/v1",      "default_model": "llama3.1"},
}


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict] = field(default_factory=list)  # [{id, name, arguments(dict)}]
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class LLMProvider:
    """Interface — adapter nào cũng cài chat()."""

    name: str
    model: str

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.2, max_tokens: int = 1024) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, name: str, api_key: str, model: str | None = None,
                 base_url: str | None = None, timeout: float = 60.0):
        spec = OPENAI_COMPATIBLE.get(name, {})
        self.name = name
        self.base_url = (base_url or spec.get("base_url") or "").rstrip("/")
        self.model = model or spec.get("default_model") or "gpt-4.1-mini"
        self._api_key = api_key
        self._timeout = timeout
        if not self.base_url:
            raise ValueError(f"unknown provider '{name}' và không có base_url")

    def chat(self, messages, tools=None, temperature=0.2, max_tokens=1024) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        r = httpx.post(f"{self.base_url}/chat/completions", json=payload,
                       headers={"Authorization": f"Bearer {self._api_key}"},
                       timeout=self._timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"{self.name} HTTP {r.status_code}: {r.text[:600]}")
        data = r.json()
        msg = data["choices"][0]["message"]
        tcs = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tcs.append({"id": tc.get("id"), "name": fn.get("name"), "arguments": args})
        return LLMResponse(
            content=msg.get("content"), tool_calls=tcs,
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            usage=data.get("usage", {}), raw=data,
        )


def make_provider(name: str, api_key: str, model: str | None = None,
                  base_url: str | None = None) -> LLMProvider:
    """Factory: tên provider -> adapter. Mở rộng Anthropic ở đây khi cần."""
    name = (name or "").lower()
    if name in OPENAI_COMPATIBLE or base_url:
        return OpenAICompatibleProvider(name, api_key, model, base_url)
    if name == "anthropic":
        raise NotImplementedError(
            "Anthropic dùng /v1/messages (shape khác) — thêm AnthropicProvider adapter.")
    raise ValueError(f"provider không hỗ trợ: {name}")
