"""Run predictive-control validation replay and write a JSON artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.control.replay import run_predictive_replay  # noqa: E402
from greenflow.datasets import active_dataset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--building-id", default="b0000000-0000-0000-0000-000000000001")
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--max-steps", type=int, default=96)
    ap.add_argument("--horizon-steps", type=int, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--scenario-id", default=None)
    ap.add_argument("--out", default="data/validation/predictive_control_replay/replay_summary.json")
    args = ap.parse_args()

    ds = active_dataset()
    result = run_predictive_replay(
        args.building_id,
        date_from=args.date_from,
        date_to=args.date_to,
        max_steps=args.max_steps,
        horizon_steps=args.horizon_steps,
        top_k=args.top_k,
        scenario_id=args.scenario_id or ds.scenario_id,
    )
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"path": str(out), "summary": result.get("summary")}, indent=2))
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
