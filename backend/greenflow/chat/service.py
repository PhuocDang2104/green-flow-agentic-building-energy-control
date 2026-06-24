"""Chat orchestrator: RAG (turbovec) + function-calling (data_tools) + lịch sử.

Luồng 1 lượt:
  user -> retrieve context (vector) -> LLM (có tools) -> [tool calls -> query DB
  -> feed lại]* -> câu trả lời -> lưu lịch sử.

Structured data (telemetry/KPI) đi qua TOOL (chính xác, an toàn); doc/policy/định
nghĩa/Q&A cũ đi qua VECTOR (ngữ nghĩa). LLM chỉ điều phối + diễn giải.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from greenflow.chat.data_tools import TOOL_SPECS, dispatch
from greenflow.db import fetch_all, fetch_one
from greenflow.llm.keystore import decrypt_key
from greenflow.llm.provider import LLMProvider, make_provider
from greenflow.vector.embedder import Embedder, get_embedder
from greenflow.vector.reranker import rerank
from greenflow.vector.store import VectorStore

SYSTEM_PROMPT = (
    "You are GreenFlow's building assistant. Answer questions about this office "
    "building's historical operational data (energy, cost, peak power, comfort, "
    "occupancy, alerts). ALWAYS call the provided tools to get real numbers — never "
    "invent figures. Keep answers concise and factual. If retrieved context is given, "
    "use it for definitions and policy. Always answer in English.\n\n"
    "You can also START a real agentic run with trigger_agent_action (run_optimization, "
    "peak_strategy, run_prediction) when the user explicitly asks to run/start/trigger one — "
    "not when they're just asking a question. The run executes in the background and its "
    "live progress is shown to the user separately, so just confirm briefly that you started "
    "it (e.g. which one and why); do not describe step-by-step results you don't have yet."
)
MAX_TOOL_ROUNDS = 4
PROVIDER_RETRIES = 2  # retries on provider error before degrading gracefully


@dataclass
class ChatRuntime:
    provider: LLMProvider
    embedder: Embedder
    store: VectorStore
    reranker_model: str = ""
    rag_candidates: int = 20

    @classmethod
    def build(cls, conn, settings) -> "ChatRuntime":
        # provider: lấy config active (key đã mã hoá) trong DB, else fallback env
        cfg = fetch_one(conn, "SELECT provider, model, base_url, api_key_enc "
                        "FROM provider_configs WHERE is_active ORDER BY created_at DESC LIMIT 1")
        if cfg and cfg["api_key_enc"]:
            key = decrypt_key(cfg["api_key_enc"], settings.llm_keystore_secret)
            provider = make_provider(cfg["provider"], key, cfg["model"], cfg["base_url"])
        else:
            provider = make_provider("groq", settings.groq_api_key, settings.groq_model)
        embedder = get_embedder(settings.llm_embedder)
        store = VectorStore(dim=embedder.dim, path=settings.vector_index_path)
        return cls(provider, embedder, store,
                   settings.llm_reranker, settings.rag_candidates)

    # ---- retrieval (hybrid: dense + lexical -> RRF -> cross-encoder rerank) ----
    def retrieve(self, conn, message: str, k: int = 4) -> list[dict]:
        candidates = self._gather_candidates(conn, message, n=self.rag_candidates)
        if not candidates:
            return []
        # cross-encoder chấm lại; thiếu model -> giữ thứ tự RRF (rerank() tự fallback)
        return rerank(message, candidates, top_k=k, model_name=self.reranker_model)

    def _gather_candidates(self, conn, message: str, n: int) -> list[dict]:
        """2 nhánh song song rồi fuse bằng Reciprocal Rank Fusion (RRF)."""
        # nhánh DENSE: bi-encoder bge-m3 -> turbovec
        dense_ids: list[int] = []
        try:
            qv = self.embedder.embed([message], kind="query")[0]
            dense_ids = [i for i, _ in self.store.search(qv, k=n)]
        except Exception:  # noqa: BLE001 — embedder/index hỏng -> chỉ còn lexical
            pass
        # nhánh LEXICAL: Postgres full-text, config 'simple' (không stem -> hợp đa ngôn ngữ)
        sparse_ids: list[int] = []
        try:
            rows = fetch_all(conn, """
                SELECT id FROM kb_chunks
                WHERE to_tsvector('simple', coalesce(title,'') || ' ' || content)
                      @@ websearch_to_tsquery('simple', :q)
                ORDER BY ts_rank(
                    to_tsvector('simple', coalesce(title,'') || ' ' || content),
                    websearch_to_tsquery('simple', :q)) DESC
                LIMIT :n""", q=message, n=n)
            sparse_ids = [r["id"] for r in rows]
        except Exception:  # noqa: BLE001
            pass
        fused = _rrf_fuse(dense_ids, sparse_ids)[:n]
        if not fused:
            return []
        rows = {r["id"]: r for r in fetch_all(
            conn, "SELECT id, title, content FROM kb_chunks WHERE id = ANY(:ids)", ids=fused)}
        return [{"id": i, "title": rows[i]["title"], "content": rows[i]["content"]}
                for i in fused if i in rows]

    # ---- resilient provider call ----
    def _chat_resilient(self, messages, tools):
        """Call the provider with a small retry, then a tools-free fallback.

        Mitigates the case where the model emits malformed tool-call syntax
        (Groq returns HTTP 400 tool_use_failed) or a transient rate-limit/5xx:
        instead of letting that 500 the whole chat request, retry (the model is
        stochastic) and finally re-ask WITHOUT tools so it answers in prose.
        Returns None only if every attempt fails."""
        for attempt in range(PROVIDER_RETRIES):
            try:
                return self.provider.chat(messages, tools=tools)
            except Exception:  # noqa: BLE001 — provider HTTP error / timeout
                time.sleep(0.5 * (attempt + 1))
        try:  # last resort: no tools -> the model cannot malform a tool call
            return self.provider.chat(messages, tools=None)
        except Exception:  # noqa: BLE001
            return None

    # ---- main ----
    def answer(self, conn, session_id: str | None, message: str, building_id: str) -> dict:
        session_id = _ensure_session(conn, session_id, building_id)
        history = _load_history(conn, session_id, limit=8)
        snippets = self.retrieve(conn, message)

        system = SYSTEM_PROMPT
        if snippets:
            ctx = "\n".join(f"- {s['title']}: {s['content']}" for s in snippets)
            system += f"\n\nRetrieved context:\n{ctx}"
        messages = [{"role": "system", "content": system}, *history,
                    {"role": "user", "content": message}]

        tools_used, answer_text, resp = [], "", None
        for _ in range(MAX_TOOL_ROUNDS):
            resp = self._chat_resilient(messages, TOOL_SPECS)
            if resp is None:  # provider kept failing -> degrade, never 500
                answer_text = ("I couldn't reach the language model just now. "
                               "Please try again in a moment.")
                break
            if not resp.tool_calls:
                answer_text = resp.content or ""
                break
            messages.append({
                "role": "assistant", "content": resp.content,
                "tool_calls": [{"id": tc["id"], "type": "function",
                                "function": {"name": tc["name"],
                                             "arguments": json.dumps(tc["arguments"])}}
                               for tc in resp.tool_calls]})
            for tc in resp.tool_calls:
                try:  # savepoint: tool lỗi không phá transaction lưu lịch sử
                    with conn.begin_nested():
                        result = dispatch(tc["name"], tc["arguments"], conn, building_id)
                except Exception as e:  # noqa: BLE001
                    result = {"error": str(e)}
                tools_used.append({"name": tc["name"], "args": tc["arguments"], "result": result})
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": json.dumps(result, default=str)})
        else:
            answer_text = (resp.content if resp else "") or "Sorry, I couldn't complete that."

        _save_message(conn, session_id, "user", message)
        _save_message(conn, session_id, "assistant", answer_text, tools_used)
        return {"session_id": session_id, "answer": answer_text,
                "tools_used": tools_used, "sources": [s["title"] for s in snippets]}


# ------------------------------------------------------------------- retrieval
def _rrf_fuse(*ranked_lists: list[int], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion: gộp nhiều danh sách xếp hạng thành một.

    Mỗi id góp 1/(k+rank) từ mỗi danh sách -> id xuất hiện ở cả 2 nhánh (dense +
    lexical) được cộng dồn, nổi lên trên. k=60 là hằng chuẩn (Cormack 2009),
    giảm ảnh hưởng của các vị trí xếp hạng thấp.
    """
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, doc_id in enumerate(lst):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


# --------------------------------------------------------------------------- DB
def _ensure_session(conn, session_id, building_id) -> str:
    if session_id:
        row = fetch_one(conn, "SELECT id FROM chat_sessions WHERE id = :s", s=session_id)
        if row:
            return str(row["id"])
    row = fetch_one(conn, "INSERT INTO chat_sessions (building_id) VALUES (:b) RETURNING id",
                    b=building_id)
    return str(row["id"])


def _load_history(conn, session_id, limit: int) -> list[dict]:
    rows = fetch_all(conn, """
        SELECT role, content FROM chat_messages WHERE session_id = :s AND role IN ('user','assistant')
        ORDER BY created_at DESC LIMIT :lim""", s=session_id, lim=limit)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _save_message(conn, session_id, role, content, tools_used=None) -> None:
    fetch_one(conn, """
        INSERT INTO chat_messages (session_id, role, content, tool_calls)
        VALUES (:s, :r, :c, cast(:t as jsonb)) RETURNING id""",
        s=session_id, r=role, c=content,
        # default=str: tool results carry Decimal/datetime from Postgres; without
        # it the whole chat request 500s when saving the transcript.
        t=json.dumps(tools_used or [], default=str))


def reindex_kb(conn, runtime: "ChatRuntime") -> int:
    """Embed lại toàn bộ kb_chunks vào turbovec (admin)."""
    rows = fetch_all(conn, "SELECT id, content FROM kb_chunks ORDER BY id")
    if not rows:
        return 0
    import numpy as np
    vecs = runtime.embedder.embed([r["content"] for r in rows], kind="passage")
    ids = [int(r["id"]) for r in rows]
    for cid in ids:                      # upsert: xoá trước nếu đã có
        try:
            runtime.store.remove(cid)
        except Exception:  # noqa: BLE001
            pass
    runtime.store.add(ids, np.asarray(vecs))
    runtime.store.save()
    return len(ids)
