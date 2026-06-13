"""Vector store bằng turbovec (IdMapIndex) — RAG cho chatbot.

turbovec: index nhị phân lượng tử hoá, nhanh, có ID ổn định (uint64) + xoá O(1) +
allowlist (hybrid). Ta dùng id = id dòng trong bảng kb_chunks -> search trả id ->
tra text từ DB. Embedding do Embedder ngoài sinh (vector/embedder.py).

Persist: .write()/.load() ra file trong storage/processed/vector/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from turbovec import IdMapIndex


class VectorStore:
    def __init__(self, dim: int, path: Path, bit_width: int = 4):
        self.dim = dim
        self.path = Path(path)
        self.index = IdMapIndex.load(str(self.path)) if self.path.exists() \
            else IdMapIndex(dim=dim, bit_width=bit_width)

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        if vectors.shape[1] != self.dim:
            raise ValueError(f"dim vector {vectors.shape[1]} != index {self.dim} "
                             "(embedder và store phải cùng dim)")
        self.index.add_with_ids(np.ascontiguousarray(vectors, dtype=np.float32),
                                np.asarray(ids, dtype=np.uint64))

    def search(self, query_vec: np.ndarray, k: int = 5,
               allowlist: list[int] | None = None) -> list[tuple[int, float]]:
        q = np.ascontiguousarray(query_vec.reshape(1, -1), dtype=np.float32)  # batch (1, dim)
        kw = {"allowlist": np.asarray(allowlist, dtype=np.uint64)} if allowlist else {}
        scores, ids = self.index.search(q, k=k, **kw)
        return [(int(i), float(s)) for i, s in zip(np.ravel(ids), np.ravel(scores))]

    def remove(self, chunk_id: int) -> None:
        self.index.remove(np.uint64(chunk_id))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.index.write(str(self.path))
