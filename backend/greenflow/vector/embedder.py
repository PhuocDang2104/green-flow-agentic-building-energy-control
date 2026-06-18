"""Embedder — turbovec KHÔNG tự sinh vector, nên cần model embedding ngoài.

Chatbot nhận câu hỏi **tiếng Việt** (và Anh) -> embedder PHẢI đa ngôn ngữ. Mặc
định **BAAI/bge-m3** (1024 chiều, MIT, 100+ ngôn ngữ, "workhorse" RAG 2026): cùng
một model nhúng tốt cho cả query VN lẫn passage EN -> cross-lingual retrieval.
Phương án nhẹ hơn: intfloat/multilingual-e5-base (768). Model chỉ-Anh
(bge-small/base-en) GIỮ trong catalog cho fallback nhưng KHÔNG nên dùng cho
sản phẩm tiếng Việt.

Tiền tố theo loại model (BẤT ĐỐI XỨNG):
  - bge-*-en-v1.5: query cần "Represent this sentence...", passage không.
  - e5: "query: " / "passage: ".
  - bge-m3: KHÔNG cần prefix (query & passage encode như nhau).
Embedder xử lý qua tham số kind ∈ {query, passage}.

⚠ dim của embedder PHẢI khớp dim của turbovec index (VectorStore). Đổi preset =>
phải reindex lại (xoá index cũ) vì dim đổi.
"""
from __future__ import annotations

import hashlib

import numpy as np

# Catalog. dim phải khớp khi tạo VectorStore. prefix: kiểu tiền tố query/passage.
EMBEDDER_CATALOG = {
    "bge-m3":      {"st_model": "BAAI/bge-m3", "dim": 1024, "prefix": "none"},
    "e5-base":     {"st_model": "intfloat/multilingual-e5-base", "dim": 768, "prefix": "e5"},
    "bge-small":   {"st_model": "BAAI/bge-small-en-v1.5", "dim": 384, "prefix": "bge-en"},
    "bge-base":    {"st_model": "BAAI/bge-base-en-v1.5",  "dim": 768, "prefix": "bge-en"},
    "mxbai-large": {"st_model": "mixedbread-ai/mxbai-embed-large-v1", "dim": 1024, "prefix": "bge-en"},
}
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Embedder:
    dim: int

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    """Production: bge-m3 đa ngôn ngữ mặc định. Lazy import torch."""

    def __init__(self, preset: str = "bge-m3"):
        spec = EMBEDDER_CATALOG[preset]
        from sentence_transformers import SentenceTransformer  # lazy (torch nặng)
        self._model = SentenceTransformer(spec["st_model"])
        self.dim = spec["dim"]
        self._prefix = spec.get("prefix", "none")

    def _apply_prefix(self, texts, kind):
        if self._prefix == "bge-en" and kind == "query":
            return [BGE_QUERY_INSTRUCTION + t for t in texts]
        if self._prefix == "e5":
            tag = "query: " if kind == "query" else "passage: "
            return [tag + t for t in texts]
        return texts  # bge-m3 và mọi model "none": không prefix

    def embed(self, texts, kind="passage") -> np.ndarray:
        texts = self._apply_prefix(texts, kind)
        v = self._model.encode(texts, normalize_embeddings=True,
                               convert_to_numpy=True)
        return v.astype(np.float32)


class HashingEmbedder(Embedder):
    """Fallback dev (KHÔNG cần torch): hashing trick + L2 norm. Cùng dim bge-small
    để thay thế trực tiếp khi test. KHÔNG dùng production (không có ngữ nghĩa thật)."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts, kind="passage") -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in t.lower().split():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


def get_embedder(name: str = "bge-m3") -> Embedder:
    """Factory: 'bge-m3'|'e5-base'|'bge-base'|... (production) | 'hashing' (dev).

    Fallback HashingEmbedder dùng ĐÚNG dim của preset đang chọn để không lệch dim
    với turbovec index (nếu thiếu torch/model thì retrieval kém nhưng không vỡ)."""
    if name == "hashing":
        return HashingEmbedder()
    try:
        return SentenceTransformerEmbedder(name)
    except Exception as e:  # noqa: BLE001 — fallback rõ ràng khi thiếu torch/model
        import warnings
        dim = EMBEDDER_CATALOG.get(name, {}).get("dim", 384)
        warnings.warn(f"sentence-transformers không nạp được ({e}); "
                      f"dùng HashingEmbedder dim={dim} (DEV ONLY).")
        return HashingEmbedder(dim=dim)
