"""Cross-encoder reranker (giai đoạn 2 của hybrid RAG).

Bi-encoder (bge-m3) nhúng query & passage RIÊNG -> nhanh nhưng thô. Cross-encoder
(bge-reranker-v2-m3) đọc CẶP (query, passage) cùng lúc -> điểm liên quan chính xác
hơn nhiều, nhưng chậm -> chỉ chấm lại top-N ứng viên đã lọc, không quét cả kho.

Đa ngôn ngữ (xlm-roberta) nên chấm tốt query tiếng Việt vs passage tiếng Anh.
Apache-2.0. Lazy-load + cache; thiếu model/torch -> trả nguyên thứ tự cũ (degrade,
không vỡ chat).
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=2)
def _load(model_name: str):
    """Load 1 lần; None nếu thiếu sentence-transformers/torch/model."""
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(model_name, max_length=512)
    except Exception:  # noqa: BLE001 — thiếu lib/model -> caller giữ thứ tự cũ
        return None


def rerank(query: str, candidates: list[dict], top_k: int,
           model_name: str = "BAAI/bge-reranker-v2-m3") -> list[dict]:
    """Chấm lại ứng viên bằng cross-encoder, trả top_k theo điểm giảm dần.

    candidates: list dict có 'title' + 'content'. Mỗi dict được gắn 'rerank_score'.
    Thiếu model -> trả candidates[:top_k] nguyên thứ tự đầu vào (fallback an toàn).
    """
    if not candidates:
        return []
    if not model_name:
        return candidates[:top_k]
    model = _load(model_name)
    if model is None:
        return candidates[:top_k]
    pairs = [(query, f"{c.get('title', '')}\n{c.get('content', '')}") for c in candidates]
    scores = model.predict(pairs)
    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]
