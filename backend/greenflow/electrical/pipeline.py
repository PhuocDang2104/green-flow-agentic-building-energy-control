"""Orchestrates the 12-phase electrical knowledge-graph build. Each phase is
independently rerunnable; the full run regenerates validation + docs every time.
"""
from __future__ import annotations

import importlib
import time

# phase key -> module under greenflow.electrical (each exposes run())
PHASES: list[tuple[str, str]] = [
    ("audit", "audit"),
    ("ele", "ele_extract"),
    ("spatial", "spatial_map"),
    ("energy", "energy_map"),
    ("alloc", "board_alloc"),
    ("hvac", "hvac_energy"),
    ("graph", "graph_build"),
    ("timeseries", "board_timeseries"),
    ("validate", "validate"),
    ("rag", "graph_rag"),
    ("dashboard", "dashboard"),
    ("docs", "docs"),
]
PHASE_KEYS = [k for k, _ in PHASES]


def _run_one(key: str, module: str) -> dict:
    mod = importlib.import_module(f"greenflow.electrical.{module}")
    t0 = time.time()
    res = mod.run()
    return {"phase": key, "seconds": round(time.time() - t0, 1), "result": res}


def run(phases: list[str] | None = None, load_db: bool = False) -> list[dict]:
    todo = phases or PHASE_KEYS
    order = {k: i for i, k in enumerate(PHASE_KEYS)}
    todo = sorted(set(todo), key=lambda k: order.get(k, 99))
    by_key = dict(PHASES)
    out = []
    for key in todo:
        if key not in by_key:
            print(f"  ! unknown phase '{key}' (valid: {', '.join(PHASE_KEYS)})")
            continue
        r = _run_one(key, by_key[key])
        out.append(r)
        print(f"  ✓ {key:<11} {r['seconds']:>6}s  {r['result']}")
    if load_db:
        for loader in ("postgres", "pgvector"):
            try:
                mod = importlib.import_module(f"greenflow.electrical.loaders.{loader}")
                print(f"  ✓ load:{loader:<6} {mod.load()}")
            except Exception as ex:  # noqa: BLE001
                print(f"  ! load:{loader} skipped: {type(ex).__name__}: {ex}")
    return out


if __name__ == "__main__":
    run()
