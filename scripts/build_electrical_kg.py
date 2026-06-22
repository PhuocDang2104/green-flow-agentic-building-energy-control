"""CLI for the GreenFlow electrical knowledge-graph / board-allocation build.

  python scripts/build_electrical_kg.py --all
  python scripts/build_electrical_kg.py --phase ele --phase alloc --phase timeseries
  python scripts/build_electrical_kg.py --all --load-db     # + Postgres + pgvector

Outputs land in data/electrical_distribution/ and data/knowledge_graph_build/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from greenflow.electrical.pipeline import PHASE_KEYS, run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the GreenFlow electrical knowledge graph.")
    ap.add_argument("--all", action="store_true", help="run every phase in order")
    ap.add_argument("--phase", action="append", default=[], choices=PHASE_KEYS,
                    help="run a specific phase (repeatable)")
    ap.add_argument("--load-db", action="store_true", help="load graph into Postgres + cards into pgvector")
    args = ap.parse_args()
    if not args.all and not args.phase:
        ap.error("specify --all or one/more --phase")
    print("GreenFlow electrical KG build")
    run(phases=None if args.all else args.phase, load_db=args.load_db)
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
