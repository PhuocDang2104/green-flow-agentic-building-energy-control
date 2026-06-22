"""Load the graph-RAG cards into the vector store (turbovec) and answer questions.

Uses the repo's existing Embedder + VectorStore. Defaults to the dependency-free
HashingEmbedder so retrieval works without torch; swap to 'bge-m3' for production.
`search()` falls back to keyword overlap if the index/embedder is unavailable, so
the `/api/graph/rag/answer` endpoint always responds.
"""
from __future__ import annotations

import json
from pathlib import Path

from ...config import get_settings
from .. import config as cfg
from .. import graph_rag

EMBEDDER = "hashing"   # 'bge-m3' for production multilingual retrieval


def _vector_dir() -> Path:
    d = get_settings().storage_path / "processed" / "vector"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return _vector_dir() / "electrical_kg.tv"


def _cards_path() -> Path:
    return _vector_dir() / "electrical_kg_cards.json"


def _all_cards() -> list[dict]:
    cards = C_read(graph_rag.ENTITY_CARDS) + C_read(graph_rag.REL_CARDS)
    return cards


def C_read(path):
    from .. import canonical as C
    return C.read_jsonl(path)


def load() -> dict:
    import numpy as np
    from ...vector.embedder import get_embedder
    from ...vector.store import VectorStore

    cards = _all_cards()
    if not cards:
        return {"loaded": 0, "note": "no cards; run --phase rag first"}
    emb = get_embedder(EMBEDDER)
    vecs = emb.embed([c.get("text", c.get("title", "")) for c in cards], kind="passage")
    idx_path = _index_path()
    if idx_path.exists():
        idx_path.unlink()
    store = VectorStore(dim=emb.dim, path=idx_path)
    store.add(list(range(len(cards))), np.ascontiguousarray(vecs))
    store.save()
    _cards_path().write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    return {"loaded": len(cards), "dim": emb.dim, "index": str(idx_path)}


def _keyword_search(cards: list[dict], question: str, k: int) -> list[dict]:
    q = set(question.lower().split())
    scored = []
    for c in cards:
        blob = (c.get("text", "") + " " + c.get("title", "")).lower()
        scored.append((sum(1 for w in q if w in blob), c))
    scored.sort(key=lambda x: -x[0])
    return [c for s, c in scored[:k] if s > 0] or [c for _s, c in scored[:k]]


def search(question: str, k: int = 6) -> list[dict]:
    cards = []
    if _cards_path().exists():
        cards = json.loads(_cards_path().read_text(encoding="utf-8"))
    if not cards:
        cards = _all_cards()
    try:
        import numpy as np
        from ...vector.embedder import get_embedder
        from ...vector.store import VectorStore
        if not _index_path().exists():
            raise FileNotFoundError("index not built")
        emb = get_embedder(EMBEDDER)
        store = VectorStore(dim=emb.dim, path=_index_path())
        qv = emb.embed([question], kind="query")[0]
        hits = store.search(np.ascontiguousarray(qv), k=k)
        return [cards[i] for i, _s in hits if 0 <= i < len(cards)]
    except Exception:
        return _keyword_search(cards, question, k)


def answer(question: str) -> dict:
    cards = search(question, k=5)
    if not cards:
        return {"question": question, "answer": "No relevant electrical entities found.",
                "sources": [], "policy": _POLICY}
    top = cards[0]
    lines = [top.get("text", top.get("title", ""))]
    if top.get("caveats"):
        lines.append("Caveats: " + "; ".join(top["caveats"]) + ".")
    lines.append(f"Provenance: {top.get('provenance', 'see card')}; "
                 f"confidence: {top.get('confidence', 'n/a')}.")
    return {
        "question": question,
        "answer": " ".join(lines),
        "value_labels_required": ["measured", "energyplus_simulated", "ifc_derived",
                                  "spatially_inferred", "naming_inferred", "assumption_based",
                                  "manual_review"],
        "sources": [{"card_id": c.get("card_id"), "type": c.get("card_type"),
                     "title": c.get("title"), "view": c.get("recommended_dashboard_view")}
                    for c in cards],
        "policy": _POLICY,
    }


_POLICY = ("Board demand is EnergyPlus-simulated zone energy redistributed by inferred "
           "allocation (estimated, not measured). Overload is only asserted with a real rated "
           "current; otherwise rating_missing. Topology is estimated unless edge confidence=exact.")


if __name__ == "__main__":
    print(load())
