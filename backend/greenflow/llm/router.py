"""ModelRouter — provider pool with failover + circuit-breaker.

The product rotates across multiple LLM services. The router holds an ordered
pool of providers (primary = the active provider_config, then the rest as
fallbacks, then env Groq as last resort) and a process-level circuit-breaker: a
provider that errors is skipped for a short cooldown, so a rate-limited or
malformed-tool-call provider (e.g. Groq llama HTTP 400 tool_use_failed) fails
over to the next instead of failing the request. The provider/model that
actually answered is recorded on the response for audit.

Memory is unaffected — it's external (Postgres history + RAG). Only the EMBEDDER
must stay pinned; it is deliberately NOT part of this rotation.

`role` is accepted for forward-compat (per-role sub-pools); today every role
shares one pool. To add per-role routing later, give provider_configs a `role`
column and filter the pool in build().
"""

from __future__ import annotations

import time

from greenflow.db import fetch_all
from greenflow.llm.keystore import decrypt_key
from greenflow.llm.provider import LLMProvider, LLMResponse, make_provider

_COOLDOWN_SECONDS = 20.0
_breaker: dict[str, float] = {}  # "provider:model" -> unix ts until skipped (process-global)


class ModelRouter:
    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers

    @classmethod
    def build(cls, conn, settings) -> "ModelRouter":
        """Pool = all configured providers (active first, then by recency) + env
        Groq as a last-resort fallback, de-duplicated by (provider, model)."""
        providers: list[LLMProvider] = []
        rows = fetch_all(conn,
                         "SELECT provider, model, base_url, api_key_enc FROM provider_configs "
                         "ORDER BY is_active DESC, created_at DESC")
        for r in rows:
            if not r["api_key_enc"]:
                continue
            try:
                key = decrypt_key(r["api_key_enc"], settings.llm_keystore_secret)
                providers.append(make_provider(r["provider"], key, r["model"], r["base_url"]))
            except Exception:  # noqa: BLE001 — bad key / unknown provider -> skip
                continue
        if settings.groq_api_key:
            providers.append(make_provider("groq", settings.groq_api_key, settings.groq_model))

        seen: set[str] = set()
        uniq: list[LLMProvider] = []
        for p in providers:
            k = cls._key(p)
            if k not in seen:
                seen.add(k)
                uniq.append(p)
        return cls(uniq)

    def chat(self, messages, tools=None, role: str = "chat", **kw) -> LLMResponse:
        """Try providers in order, skipping any in cooldown; fail over on error.
        Trips the circuit-breaker on failure and clears it on success."""
        if not self.providers:
            raise RuntimeError("no LLM providers configured")
        now = time.time()
        # prefer providers not cooling down; if all are cooling, try them all anyway
        order = [p for p in self.providers if _breaker.get(self._key(p), 0.0) <= now] \
            or list(self.providers)
        last_exc: Exception | None = None
        for p in order:
            try:
                resp = p.chat(messages, tools=tools, **kw)
                _breaker.pop(self._key(p), None)  # success clears the breaker
                resp.raw = {**(resp.raw or {}),
                            "_router": {"role": role, "provider": p.name, "model": p.model}}
                return resp
            except Exception as exc:  # noqa: BLE001 — provider HTTP/parse/timeout
                last_exc = exc
                _breaker[self._key(p)] = time.time() + _COOLDOWN_SECONDS
        raise last_exc or RuntimeError("all providers failed")

    @staticmethod
    def _key(p: LLMProvider) -> str:
        return f"{p.name}:{p.model}"
