"""Precompute predictive-MPC what-if replay into cache tables/artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.config import get_settings  # noqa: E402
from greenflow.control.replay import run_predictive_replay  # noqa: E402
from greenflow.control.whatif_cache import (  # noqa: E402
    begin_run,
    build_cache_identity,
    delete_run,
    ensure_schema,
    existing_run,
    expected_step_count,
    iter_chunks,
    load_zone_model_metadata,
    parse_local_date,
    telemetry_step_count,
    validate_cache_range,
    write_artifacts,
    write_replay_result,
    mark_run_failed,
)
from greenflow.datasets import active_dataset  # noqa: E402
from greenflow.db import db_conn  # noqa: E402


def _parse_write(value: str) -> set[str]:
    modes = {v.strip().lower() for v in value.split(",") if v.strip()}
    allowed = {"postgres", "parquet"}
    unknown = modes - allowed
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown write target(s): {', '.join(sorted(unknown))}")
    return modes or {"postgres"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--building-id", default=get_settings().default_building_id)
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--scenario-id", default=None)
    ap.add_argument("--horizon-steps", type=int, default=get_settings().greenflow_control_horizon_steps)
    ap.add_argument("--top-k", type=int, default=get_settings().greenflow_control_top_k)
    ap.add_argument("--chunk-days", type=int, default=1)
    ap.add_argument("--write", type=_parse_write, default={"postgres", "parquet"})
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true")
    ap.add_argument("--allow-local-fallback", action="store_true")
    args = ap.parse_args()

    ds = active_dataset()
    scenario_id = args.scenario_id or ds.scenario_id
    start = parse_local_date(args.date_from)
    end = parse_local_date(args.date_to)
    if start is None or end is None or start >= end:
        raise SystemExit("date-from/date-to are required and date-from must be before date-to")

    model_meta = load_zone_model_metadata(allow_local_fallback=args.allow_local_fallback)
    identity = build_cache_identity(
        ds=ds,
        scenario_id=scenario_id,
        horizon_steps=args.horizon_steps,
        top_k=args.top_k,
        model_metadata=model_meta,
    )
    cache_key = identity["cache_key"]
    chunks = iter_chunks(start, end, chunk_days=args.chunk_days)
    summary = {
        "dataset": ds.to_metadata(),
        "scenario_id": scenario_id,
        "cache_key": cache_key,
        "horizon_steps": args.horizon_steps,
        "top_k": args.top_k,
        "write": sorted(args.write),
        "dry_run": args.dry_run,
        "chunks_total": len(chunks),
        "chunks": [],
    }

    if args.dry_run:
        summary["chunks"] = [
            {
                "date_from": c0.isoformat(),
                "date_to": c1.isoformat(),
                "expected_steps": expected_step_count(c0, c1, timestep_minutes=ds.timestep_minutes),
                "status": "dry_run",
            }
            for c0, c1 in chunks
        ]
        print(json.dumps(summary, indent=2, default=str))
        return 0

    with db_conn() as conn:
        ensure_schema(conn)

    exit_code = 0
    for c0, c1 in chunks:
        run_id = None
        nominal_steps = expected_step_count(c0, c1, timestep_minutes=ds.timestep_minutes)
        expected_steps = telemetry_step_count(
            scenario_id=scenario_id,
            start=c0,
            end=c1,
            building_id=args.building_id,
        ) or nominal_steps
        chunk_log = {
            "date_from": c0.isoformat(),
            "date_to": c1.isoformat(),
            "expected_steps": expected_steps,
            "nominal_steps": nominal_steps,
        }
        try:
            with db_conn() as conn:
                ensure_schema(conn)
                old = existing_run(conn, cache_key=cache_key, start=c0, end=c1)
                if old and args.force:
                    delete_run(conn, str(old["id"]))
                    old = None
                if old and args.resume and old.get("status") == "complete":
                    chunk_log.update({"status": "skipped", "reason": "already complete",
                                      "run_id": str(old["id"])})
                    summary["chunks"].append(chunk_log)
                    continue
                if old and not args.force:
                    raise RuntimeError(
                        f"cache chunk already exists with status={old.get('status')}; "
                        "use --resume or --force"
                    )
                run_id = begin_run(
                    conn,
                    ds=ds,
                    scenario_id=scenario_id,
                    cache_key=cache_key,
                    identity=identity["identity"],
                    model_metadata=model_meta,
                    start=c0,
                    end=c1,
                    horizon_steps=args.horizon_steps,
                    top_k=args.top_k,
                )
            replay = run_predictive_replay(
                args.building_id,
                date_from=c0.isoformat(),
                date_to=c1.isoformat(),
                max_steps=expected_steps,
                horizon_steps=args.horizon_steps,
                top_k=args.top_k,
                scenario_id=scenario_id,
            )
            errors = replay.get("errors") or []
            actual_steps = len(replay.get("series") or [])
            if actual_steps != expected_steps:
                raise RuntimeError(f"expected {expected_steps} replay steps, got {actual_steps}")
            if errors and not args.continue_on_error:
                raise RuntimeError(f"predictive replay returned {len(errors)} errors")

            with db_conn() as conn:
                result_meta = write_replay_result(
                    conn,
                    run_id=run_id,
                    result=replay,
                    continue_on_error=args.continue_on_error,
                )
            artifacts = {}
            if "parquet" in args.write:
                artifacts = write_artifacts(
                    cache_key=cache_key,
                    result=replay,
                    daily_rows=result_meta["daily"],
                    chunk_start=c0,
                    chunk_end=c1,
                )
            chunk_log.update({
                "status": "complete_with_errors" if errors else "complete",
                "run_id": run_id,
                "steps": actual_steps,
                "daily_rows": len(result_meta["daily"]),
                "actions": result_meta["actions"],
                "errors": len(errors),
                "artifacts": artifacts,
            })
        except Exception as exc:  # noqa: BLE001
            exit_code = 1
            chunk_log.update({"status": "failed", "error": repr(exc)[:500]})
            if run_id is not None:
                try:
                    with db_conn() as conn:
                        mark_run_failed(conn, run_id, repr(exc), metadata=chunk_log)
                except Exception:
                    pass
            if not args.continue_on_error:
                summary["chunks"].append(chunk_log)
                print(json.dumps(summary, indent=2, default=str))
                return 1
        summary["chunks"].append(chunk_log)

    try:
        summary["validation"] = validate_cache_range(
            date_from=start.isoformat(),
            date_to=end.isoformat(),
            scenario_id=scenario_id,
            horizon_steps=args.horizon_steps,
            top_k=args.top_k,
            building_id=args.building_id,
        )
        if not summary["validation"].get("ok"):
            exit_code = 1
    except Exception as exc:  # noqa: BLE001
        summary["validation_error"] = repr(exc)[:500]
        exit_code = 1

    print(json.dumps(summary, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
