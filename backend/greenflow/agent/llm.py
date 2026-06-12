"""LLM factory: openai | anthropic | none.

With LLM_PROVIDER=none (default) every call returns the deterministic
fallback, so the whole agent flow works offline and in tests. The LLM is only
used to polish natural-language text — intents, plans, policy and actions are
always rule-based and auditable.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings


@lru_cache
def get_chat_model():
    """Return a LangChain chat model or None when unavailable."""
    s = get_settings()
    try:
        if s.llm_provider == "openai" and s.openai_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key,
                              temperature=0.2, timeout=30)
        if s.llm_provider == "anthropic" and s.anthropic_api_key:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=s.anthropic_model, api_key=s.anthropic_api_key,
                                 temperature=0.2, timeout=30)
    except ImportError:
        pass
    return None


def llm_text(prompt: str, fallback: str) -> str:
    """Ask the LLM for text; return deterministic fallback when no provider."""
    model = get_chat_model()
    if model is None:
        return fallback
    try:
        response = model.invoke(prompt)
        content = response.content
        if isinstance(content, list):  # anthropic content blocks
            content = " ".join(c.get("text", "") if isinstance(c, dict) else str(c)
                               for c in content)
        return str(content).strip() or fallback
    except Exception:
        return fallback
