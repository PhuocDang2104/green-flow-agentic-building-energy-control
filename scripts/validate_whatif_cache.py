"""Validate precomputed predictive-MPC what-if cache coverage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.config import get_settings  # noqa: E402
from greenflow.control.whatif_cache import validate_cache_range  # noqa: E402
from greenflow.datasets import active_dataset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--scenario-id", default=None)
    ap.add_argument("--horizon-steps", type=int, default=get_settings().greenflow_control_horizon_steps)
    ap.add_argument("--top-k", type=int, default=get_settings().greenflow_control_top_k)
    args = ap.parse_args()

    ds = active_dataset()
    result = validate_cache_range(
        date_from=args.date_from,
        date_to=args.date_to,
        scenario_id=args.scenario_id or ds.scenario_id,
        horizon_steps=args.horizon_steps,
        top_k=args.top_k,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
