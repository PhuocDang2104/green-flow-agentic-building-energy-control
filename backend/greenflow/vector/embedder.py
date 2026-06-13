"""Embedder — turbovec KHÔNG tự sinh vector, nên cần model embedding ngoài.

Sản phẩm tiếng Anh -> mặc định **BAAI/bge-small-en-v1.5** (384 chiều, chạy local
qua sentence-transformers, top MTEB retrieval, nhẹ). Nâng cấp chất lượng:
bge-base-en-v1.5 (768) / mxbai-embed-large-v1 (1024). Nếu có key OpenAI ->
text-embedding-3-small (1536) qua API.

bge/e5 là model BẤT ĐỐI XỨNG: query cần prefix chỉ dẫn, passage thì không.
Embedder xử lý việc đó qua tham số kind ∈ {query, passage}.

⚠ dim của embedder PHẢI khớp dim của turbovec index (VectorStore).
"""
from __future__ import annotations

import hashlib

import numpy as np

# Catalog gợi ý (English). dim phải khớp khi tạo VectorStore.
EMBEDDER_CATALOG = {
    "bge-small":  {"st_model": "BAAI/bge-small-en-v1.5", "dim": 384},
    "bge-base":   {"st_model": "BAAI/bge-base-en-v1.5",  "dim": 768},
    "mxbai-large": {"st_model": "mixedbread-ai/mxbai-embed-large-v1", "dim": 1024},
}
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Embedder:
    dim: int

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    """Production (English): bge-small-en-v1.5 mặc định. Lazy import torch."""

    def __init__(self, preset: str = "bge-small"):
        spec = EMBEDDER_CATALOG[preset]
        from sentence_transformers import SentenceTransformer  # lazy (torch nặng)
        self._model = SentenceTransformer(spec["st_model"])
        self.dim = spec["dim"]
        self._is_bge = "bge" in spec["st_model"].lower()

    def embed(self, texts, kind="passage") -> np.ndarray:
        if self._is_bge and kind == "query":
            texts = [BGE_QUERY_INSTRUCTION + t for t in texts]
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


def get_embedder(name: str = "bge-small") -> Embedder:
    """Factory: 'bge-small'|'bge-base'|'mxbai-large' (production) | 'hashing' (dev)."""
    if name == "hashing":
        return HashingEmbedder()
    try:
        return SentenceTransformerEmbedder(name)
    except Exception as e:  # noqa: BLE001 — fallback rõ ràng khi thiếu torch/model
        import warnings
        warnings.warn(f"sentence-transformers không nạp được ({e}); "
                      "dùng HashingEmbedder (DEV ONLY).")
        return HashingEmbedder()
