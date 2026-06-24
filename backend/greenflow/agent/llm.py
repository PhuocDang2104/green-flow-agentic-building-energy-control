"""Agent text helper — unified onto the same ModelRouter as the chat brain.

The agent uses an LLM ONLY to polish natural-language text (action reasons,
report prose, the chatbot-style answer). Intents, plans, policy and actions stay
rule-based and auditable. Polishing is OFF by default (AGENT_LLM_POLISH=false) so
agent runs remain fast and fully deterministic; when enabled, llm_text() routes
through the SHARED provider pool (failover + circuit-breaker + audit) instead of
a separate LangChain stack. On no provider / any error it returns the
deterministic fallback, so callers always get usable text.

Anthropic, like the chat brain, needs an AnthropicProvider adapter in
llm/provider.py before it can join the pool (the pool is OpenAI-compatible).
"""

from __future__ import annotations

from ..config import get_settings


def llm_text(prompt: str, fallback: str) -> str:
    """Polish text via the shared model router; return the deterministic fallback
    when polishing is disabled, no provider is available, or the call fails."""
    if not get_settings().agent_llm_polish:
        return fallback
    try:
        from ..db import db_conn
        from ..llm.router import ModelRouter
        with db_conn() as conn:
            router = ModelRouter.build(conn, get_settings())
        resp = router.chat([{"role": "user", "content": prompt}],
                           tools=None, role="agent_text")
        return (resp.content or "").strip() or fallback
    except Exception:  # noqa: BLE001 — DB/provider/parse failure -> stay deterministic
        return fallback
