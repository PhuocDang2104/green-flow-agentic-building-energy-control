"""AI chat API: hỏi dữ liệu lịch sử tòa nhà + quản lý provider + lịch sử chat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...chat.service import ChatRuntime, reindex_kb
from ...config import get_settings
from ...db import db_conn, fetch_all, fetch_one
from ...llm.keystore import encrypt_key, mask
from ...llm.provider import OPENAI_COMPATIBLE
from ..deps import default_building_id

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    building_id: str | None = None


@router.post("/chat")
def chat(req: ChatRequest):
    b = req.building_id or default_building_id()
    with db_conn() as conn:
        runtime = ChatRuntime.build(conn, get_settings())
        return runtime.answer(conn, req.session_id, req.message, b)


@router.get("/chat/sessions")
def list_sessions(building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    with db_conn() as conn:
        return fetch_all(conn, """
            SELECT s.id, s.created_at,
                   (SELECT content FROM chat_messages m WHERE m.session_id = s.id
                    AND m.role = 'user' ORDER BY m.created_at LIMIT 1) AS first_message,
                   (SELECT count(*) FROM chat_messages m WHERE m.session_id = s.id) AS n_messages
            FROM chat_sessions s WHERE s.building_id = :b
            ORDER BY s.created_at DESC LIMIT 50""", b=b)


@router.get("/chat/sessions/{session_id}/messages")
def session_messages(session_id: str):
    with db_conn() as conn:
        return fetch_all(conn, """
            SELECT role, content, tool_calls, created_at FROM chat_messages
            WHERE session_id = :s ORDER BY created_at""", s=session_id)


# ---- provider management (select provider + nhập key + lưu, đã mã hoá) ----
class ProviderConfig(BaseModel):
    provider: str                 # groq | openai | openrouter | together | ollama | <custom>
    api_key: str
    model: str | None = None
    base_url: str | None = None


@router.get("/llm/providers")
def list_providers():
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT id, provider, model, base_url, is_active, created_at
            FROM provider_configs ORDER BY created_at DESC""")
    return {"configured": rows, "known": list(OPENAI_COMPATIBLE)}


@router.post("/llm/providers")
def add_provider(cfg: ProviderConfig):
    s = get_settings()
    spec = OPENAI_COMPATIBLE.get(cfg.provider, {})
    if not (cfg.base_url or spec):
        raise HTTPException(400, f"unknown provider '{cfg.provider}'; cấp base_url")
    enc = encrypt_key(cfg.api_key, s.llm_keystore_secret)
    with db_conn() as conn:
        fetch_one(conn, "UPDATE provider_configs SET is_active = false WHERE is_active RETURNING id")
        row = fetch_one(conn, """
            INSERT INTO provider_configs (provider, model, base_url, api_key_enc, is_active)
            VALUES (:p, :m, :u, :k, true) RETURNING id""",
            p=cfg.provider, m=cfg.model or spec.get("default_model"),
            u=cfg.base_url or spec.get("base_url"), k=enc)
    return {"id": str(row["id"]), "provider": cfg.provider, "key": mask(cfg.api_key),
            "active": True}


@router.post("/llm/providers/{config_id}/activate")
def activate_provider(config_id: str):
    with db_conn() as conn:
        fetch_one(conn, "UPDATE provider_configs SET is_active = false WHERE is_active RETURNING id")
        row = fetch_one(conn, "UPDATE provider_configs SET is_active = true WHERE id = :i RETURNING id",
                        i=config_id)
    if not row:
        raise HTTPException(404, "provider config not found")
    return {"id": config_id, "active": True}


@router.post("/chat/kb/reindex")
def kb_reindex():
    with db_conn() as conn:
        runtime = ChatRuntime.build(conn, get_settings())
        n = reindex_kb(conn, runtime)
    return {"indexed_chunks": n}
