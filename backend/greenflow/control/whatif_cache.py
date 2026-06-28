"""Precomputed what-if cache for predictive MPC replay.

The web UI must not run multi-month predictive replay in a request. This module
materializes replay chunks into Postgres and optional storage artifacts, then
serves campaign-shaped responses from the cache.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..config import get_settings
from ..datasets import DatasetConfig, active_dataset
from ..db import db_conn, fetch_all, fetch_one

TZ = timezone(timedelta(hours=7))
CONTROL_MODE = "predictive_replay"
OBJECTIVE_VERSION = "v1"
CONTROLLER_VERSION = "predictive_mpc_v1"
GRID_CO2_KG_PER_KWH = 0.6766
DEFAULT_AVG_TARIFF_VND_PER_KWH = 1839


def parse_local_date(value: str | date | datetime | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(TZ).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()


def local_midnight(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=TZ)


def expected_step_count(start: date, end: date, *, timestep_minutes: int) -> int:
    days = max(0, (end - start).days)
    return int(days * 24 * 60 / timestep_minutes)


def telemetry_step_count(*, scenario_id: str | None, start: date, end: date,
                         building_id: str | None = None) -> int:
    """Count actual recorded timestamps in the requested local-date window.

    El Nino starts at 2024-03-01 00:30 and has a terminal 2024-05-01 00:00
    timestamp, so calendar-day chunks are not always exactly 48 steps.
    """
    with db_conn() as conn:
        row = fetch_one(conn, """
            SELECT count(DISTINCT timestamp) AS n
            FROM telemetry_zone_15m
            WHERE timestamp >= CAST(:df AS timestamptz)
              AND timestamp < CAST(:dt AS timestamptz)
              AND (CAST(:building_id AS uuid) IS NULL OR building_id = CAST(:building_id AS uuid))
              AND (CAST(:scenario_id AS text) IS NULL
                   OR scenario_id = CAST(:scenario_id AS text)
                   OR scenario_id IS NULL)
        """, df=local_midnight(start), dt=local_midnight(end),
            building_id=building_id, scenario_id=scenario_id)
    return int((row or {}).get("n") or 0)


def iter_chunks(start: date, end: date, *, chunk_days: int) -> list[tuple[date, date]]:
    chunks = []
    cur = start
    step = timedelta(days=max(1, int(chunk_days)))
    while cur < end:
        nxt = min(end, cur + step)
        chunks.append((cur, nxt))
        cur = nxt
    return chunks


def ensure_schema(conn: Connection) -> None:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS whatif_cache_runs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          dataset_key text NOT NULL,
          scenario_id text NOT NULL,
          control_mode text NOT NULL,
          policy_key text NOT NULL,
          date_from timestamptz NOT NULL,
          date_to timestamptz NOT NULL,
          horizon_steps int,
          top_k int,
          objective_version text,
          controller_version text,
          model_metadata jsonb,
          cache_key text NOT NULL,
          status text NOT NULL,
          started_at timestamptz DEFAULT now(),
          completed_at timestamptz,
          error text,
          metadata jsonb DEFAULT '{}'::jsonb,
          UNIQUE (cache_key, date_from, date_to)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS whatif_cache_daily (
          run_id uuid REFERENCES whatif_cache_runs(id) ON DELETE CASCADE,
          date date NOT NULL,
          baseline_kwh numeric,
          ai_kwh numeric,
          saving_kwh numeric,
          saving_percent numeric,
          baseline_peak_kw numeric,
          ai_peak_kw numeric,
          comfort_violation_min numeric,
          action_count int,
          PRIMARY KEY (run_id, date)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS whatif_cache_timestep (
          run_id uuid REFERENCES whatif_cache_runs(id) ON DELETE CASCADE,
          timestamp timestamptz NOT NULL,
          baseline_kw numeric,
          ai_kw numeric,
          baseline_kwh numeric,
          ai_kwh numeric,
          saving_kwh numeric,
          comfort_violation_min numeric,
          selected_trajectory text,
          objective_score numeric,
          action_json jsonb,
          PRIMARY KEY (run_id, timestamp)
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS whatif_cache_runs_lookup_idx
          ON whatif_cache_runs(dataset_key, scenario_id, control_mode,
                               horizon_steps, top_k, status, date_from, date_to)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS whatif_cache_daily_date_idx
          ON whatif_cache_daily(date)
    """))


def load_zone_model_metadata(*, allow_local_fallback: bool = False) -> dict[str, Any]:
    """Return lightweight model metadata for cache provenance.

    This intentionally avoids downloading MLflow artifacts. The actual replay
    will load the model; cache identity only needs the configured selector.
    """
    from ..ml.model_registry import REGISTERED_MODELS

    settings = get_settings()
    configured_source = (settings.greenflow_model_source or "mlflow").lower()
    model_uri = settings.greenflow_model_zone
    version = None
    registered = REGISTERED_MODELS["zone"]
    if model_uri.startswith("models:/"):
        tail = model_uri[len("models:/"):]
        if "@" in tail:
            registered, version = tail.split("@", 1)
        elif "/" in tail:
            registered, version = tail.rsplit("/", 1)
        elif tail:
            registered = tail
    if configured_source != "mlflow" and not allow_local_fallback:
        raise RuntimeError(
            f"zone model source is {configured_source!r}; rerun with --allow-local-fallback "
            "if this is intentional"
        )
    return {
        "key": "zone",
        "source": configured_source,
        "registered_model": registered,
        "model_uri": model_uri,
        "version": version,
        "run_id": None,
        "n_features": None,
        "error": None,
    }


def build_cache_identity(*, ds: DatasetConfig, scenario_id: str, horizon_steps: int,
                         top_k: int, model_metadata: dict[str, Any],
                         policy_key: str = "default") -> dict[str, Any]:
    seed = {
        "dataset_key": ds.key,
        "scenario_id": scenario_id,
        "control_mode": CONTROL_MODE,
        "policy_key": policy_key,
        "horizon_steps": int(horizon_steps),
        "top_k": int(top_k),
        "objective_version": OBJECTIVE_VERSION,
        "controller_version": CONTROLLER_VERSION,
        "model": {
            "source": model_metadata.get("source"),
            "registered_model": model_metadata.get("registered_model"),
            "model_uri": model_metadata.get("model_uri"),
            "version": model_metadata.get("version"),
        },
        "timestep_minutes": ds.timestep_minutes,
    }
    digest = hashlib.sha256(json.dumps(seed, sort_keys=True, default=str).encode()).hexdigest()[:12]
    cache_key = (
        f"{CONTROL_MODE}_{ds.key}_h{int(horizon_steps)}_top{int(top_k)}_"
        f"{OBJECTIVE_VERSION}_{digest}"
    )
    return {"cache_key": cache_key, "identity": seed}


def artifact_root(cache_key: str) -> Path:
    return get_settings().storage_path / "whatif_cache" / cache_key


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _daily_from_series(series: list[dict], actions: list[dict]) -> list[dict]:
    by_day: dict[date, dict[str, Any]] = defaultdict(lambda: {
        "baseline_kwh": 0.0,
        "ai_kwh": 0.0,
        "saving_kwh": 0.0,
        "baseline_peak_kw": 0.0,
        "ai_peak_kw": 0.0,
        "comfort_violation_min": 0.0,
        "action_count": 0,
    })
    for row in series:
        ts = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
        day = ts.astimezone(TZ).date() if ts.tzinfo else ts.date()
        rec = by_day[day]
        rec["baseline_kwh"] += _f(row.get("baseline_kwh"))
        rec["ai_kwh"] += _f(row.get("ai_kwh"))
        rec["saving_kwh"] += _f(row.get("saving_kwh"))
        rec["baseline_peak_kw"] = max(rec["baseline_peak_kw"], _f(row.get("baseline_kw")))
        rec["ai_peak_kw"] = max(rec["ai_peak_kw"], _f(row.get("ai_kw")))
        rec["comfort_violation_min"] += _f(row.get("comfort_violation_min"))
    for action in actions:
        ts_value = action.get("timestamp")
        if not ts_value:
            continue
        ts = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
        day = ts.astimezone(TZ).date() if ts.tzinfo else ts.date()
        by_day[day]["action_count"] += 1
    out = []
    for day, rec in sorted(by_day.items()):
        base = rec["baseline_kwh"]
        saving = rec["saving_kwh"]
        out.append({
            "date": day,
            "baseline_kwh": round(base, 6),
            "ai_kwh": round(rec["ai_kwh"], 6),
            "saving_kwh": round(saving, 6),
            "saving_percent": round(saving / base * 100.0, 6) if base else 0.0,
            "baseline_peak_kw": round(rec["baseline_peak_kw"], 6),
            "ai_peak_kw": round(rec["ai_peak_kw"], 6),
            "comfort_violation_min": round(rec["comfort_violation_min"], 6),
            "action_count": int(rec["action_count"]),
        })
    return out


def existing_run(conn: Connection, *, cache_key: str, start: date, end: date) -> dict | None:
    return fetch_one(conn, """
        SELECT * FROM whatif_cache_runs
        WHERE cache_key = :key
          AND date_from = CAST(:df AS timestamptz)
          AND date_to = CAST(:dt AS timestamptz)
        LIMIT 1
    """, key=cache_key, df=local_midnight(start), dt=local_midnight(end))


def delete_run(conn: Connection, run_id: str) -> None:
    conn.execute(text("DELETE FROM whatif_cache_runs WHERE id = :id"), {"id": run_id})


def begin_run(conn: Connection, *, ds: DatasetConfig, scenario_id: str, cache_key: str,
              identity: dict[str, Any], model_metadata: dict[str, Any],
              start: date, end: date, horizon_steps: int, top_k: int,
              policy_key: str = "default") -> str:
    ensure_schema(conn)
    row = fetch_one(conn, """
        INSERT INTO whatif_cache_runs (
          dataset_key, scenario_id, control_mode, policy_key, date_from, date_to,
          horizon_steps, top_k, objective_version, controller_version,
          model_metadata, cache_key, status, metadata
        )
        VALUES (
          :dataset_key, :scenario_id, :control_mode, :policy_key,
          CAST(:date_from AS timestamptz), CAST(:date_to AS timestamptz),
          :horizon_steps, :top_k, :objective_version, :controller_version,
          CAST(:model_metadata AS jsonb), :cache_key, 'running',
          CAST(:metadata AS jsonb)
        )
        RETURNING id
    """, dataset_key=ds.key, scenario_id=scenario_id, control_mode=CONTROL_MODE,
        policy_key=policy_key, date_from=local_midnight(start), date_to=local_midnight(end),
        horizon_steps=int(horizon_steps), top_k=int(top_k),
        objective_version=OBJECTIVE_VERSION, controller_version=CONTROLLER_VERSION,
        model_metadata=_json(model_metadata), cache_key=cache_key,
        metadata=_json({"identity": identity, "dataset": ds.to_metadata()}))
    return str(row["id"])


def mark_run_failed(conn: Connection, run_id: str, error: str, *,
                    metadata: dict[str, Any] | None = None) -> None:
    conn.execute(text("""
        UPDATE whatif_cache_runs
        SET status = 'failed', completed_at = now(), error = :error,
            metadata = metadata || CAST(:metadata AS jsonb)
        WHERE id = :id
    """), {"id": run_id, "error": error[:1000], "metadata": _json(metadata or {})})


def write_replay_result(conn: Connection, *, run_id: str, result: dict,
                        continue_on_error: bool = False) -> dict[str, Any]:
    series = result.get("series") or []
    actions = result.get("actions") or []
    errors = result.get("errors") or []
    daily = _daily_from_series(series, actions)
    actions_by_ts: dict[str, list[dict]] = defaultdict(list)
    for action in actions:
        if action.get("timestamp"):
            actions_by_ts[str(action["timestamp"])].append(action)

    for day in daily:
        conn.execute(text("""
            INSERT INTO whatif_cache_daily (
              run_id, date, baseline_kwh, ai_kwh, saving_kwh, saving_percent,
              baseline_peak_kw, ai_peak_kw, comfort_violation_min, action_count
            )
            VALUES (:run_id, :date, :baseline_kwh, :ai_kwh, :saving_kwh, :saving_percent,
                    :baseline_peak_kw, :ai_peak_kw, :comfort_violation_min, :action_count)
            ON CONFLICT (run_id, date) DO UPDATE SET
              baseline_kwh = EXCLUDED.baseline_kwh,
              ai_kwh = EXCLUDED.ai_kwh,
              saving_kwh = EXCLUDED.saving_kwh,
              saving_percent = EXCLUDED.saving_percent,
              baseline_peak_kw = EXCLUDED.baseline_peak_kw,
              ai_peak_kw = EXCLUDED.ai_peak_kw,
              comfort_violation_min = EXCLUDED.comfort_violation_min,
              action_count = EXCLUDED.action_count
        """), {"run_id": run_id, **day})

    for row in series:
        ts = str(row["timestamp"])
        conn.execute(text("""
            INSERT INTO whatif_cache_timestep (
              run_id, timestamp, baseline_kw, ai_kw, baseline_kwh, ai_kwh,
              saving_kwh, comfort_violation_min, selected_trajectory,
              objective_score, action_json
            )
            VALUES (
              :run_id, CAST(:timestamp AS timestamptz), :baseline_kw, :ai_kw,
              :baseline_kwh, :ai_kwh, :saving_kwh, :comfort_violation_min,
              :selected_trajectory, :objective_score, CAST(:action_json AS jsonb)
            )
            ON CONFLICT (run_id, timestamp) DO UPDATE SET
              baseline_kw = EXCLUDED.baseline_kw,
              ai_kw = EXCLUDED.ai_kw,
              baseline_kwh = EXCLUDED.baseline_kwh,
              ai_kwh = EXCLUDED.ai_kwh,
              saving_kwh = EXCLUDED.saving_kwh,
              comfort_violation_min = EXCLUDED.comfort_violation_min,
              selected_trajectory = EXCLUDED.selected_trajectory,
              objective_score = EXCLUDED.objective_score,
              action_json = EXCLUDED.action_json
        """), {
            "run_id": run_id,
            "timestamp": ts,
            "baseline_kw": row.get("baseline_kw"),
            "ai_kw": row.get("ai_kw"),
            "baseline_kwh": row.get("baseline_kwh"),
            "ai_kwh": row.get("ai_kwh"),
            "saving_kwh": row.get("saving_kwh"),
            "comfort_violation_min": row.get("comfort_violation_min"),
            "selected_trajectory": row.get("selected_trajectory"),
            "objective_score": row.get("objective_score"),
            "action_json": _json(actions_by_ts.get(ts, [])),
        })

    status = "complete_with_errors" if errors and continue_on_error else "complete"
    conn.execute(text("""
        UPDATE whatif_cache_runs
        SET status = :status, completed_at = now(), error = :error,
            metadata = metadata || CAST(:metadata AS jsonb)
        WHERE id = :id
    """), {
        "id": run_id,
        "status": status,
        "error": None if not errors else _json(errors)[:1000],
        "metadata": _json({
            "summary": result.get("summary", {}),
            "errors": errors,
            "series_rows": len(series),
            "daily_rows": len(daily),
            "action_rows": len(actions),
        }),
    })
    return {"daily": daily, "series_rows": len(series), "actions": len(actions), "errors": errors}


def write_artifacts(*, cache_key: str, result: dict, daily_rows: list[dict],
                    chunk_start: date, chunk_end: date) -> dict[str, Any]:
    root = artifact_root(cache_key)
    root.mkdir(parents=True, exist_ok=True)
    date_label = chunk_start.isoformat()
    written: dict[str, Any] = {"root": str(root)}

    manifest_path = root / "manifest.json"
    manifest = {
        "cache_key": cache_key,
        "updated_at": datetime.now(TZ).isoformat(),
        "last_chunk": {"date_from": chunk_start.isoformat(), "date_to": chunk_end.isoformat()},
        "metadata": result.get("metadata", {}),
        "summary": result.get("summary", {}),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
                             encoding="utf-8")
    written["manifest"] = str(manifest_path)

    actions_dir = root / "actions" / f"date={date_label}"
    actions_dir.mkdir(parents=True, exist_ok=True)
    actions_path = actions_dir / "actions.jsonl"
    with actions_path.open("w", encoding="utf-8") as fh:
        for action in result.get("actions") or []:
            fh.write(json.dumps(action, ensure_ascii=False, default=str))
            fh.write("\n")
    written["actions"] = str(actions_path)

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        series_dir = root / "series" / f"date={date_label}"
        series_dir.mkdir(parents=True, exist_ok=True)
        series_path = series_dir / "part-000.parquet"
        pq.write_table(pa.Table.from_pylist(result.get("series") or []), str(series_path))
        written["series"] = str(series_path)

        daily_path = root / "daily.parquet"
        existing = []
        if daily_path.exists():
            existing = pq.read_table(str(daily_path)).to_pylist()
            existing = [r for r in existing if str(r.get("date")) not in {str(d["date"]) for d in daily_rows}]
        pq.write_table(pa.Table.from_pylist(existing + daily_rows), str(daily_path))
        written["daily"] = str(daily_path)
    except Exception as exc:  # noqa: BLE001
        fallback = root / f"series_{date_label}.json"
        fallback.write_text(json.dumps({
            "series": result.get("series") or [],
            "daily": daily_rows,
        }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        written["fallback_json"] = str(fallback)
        written["parquet_error"] = repr(exc)[:240]
    return written


def _completed_cache_key(conn: Connection, *, ds: DatasetConfig, scenario_id: str,
                         horizon_steps: int, top_k: int,
                         start: date | None, end: date | None) -> dict | None:
    if start is None or end is None:
        return fetch_one(conn, """
            SELECT cache_key, min(date_from) AS date_from, max(date_to) AS date_to,
                   max(completed_at) AS completed_at, count(*) AS chunks
            FROM whatif_cache_runs
            WHERE dataset_key = :dataset_key
              AND scenario_id = :scenario_id
              AND control_mode = :control_mode
              AND horizon_steps = :horizon_steps
              AND top_k = :top_k
              AND status = 'complete'
            GROUP BY cache_key
            ORDER BY max(completed_at) DESC NULLS LAST
            LIMIT 1
        """, dataset_key=ds.key, scenario_id=scenario_id, control_mode=CONTROL_MODE,
            horizon_steps=int(horizon_steps), top_k=int(top_k))
    expected_days = (end - start).days
    return fetch_one(conn, """
        SELECT r.cache_key, min(r.date_from) AS date_from, max(r.date_to) AS date_to,
               max(r.completed_at) AS completed_at, count(DISTINCT d.date) AS days
        FROM whatif_cache_runs r
        JOIN whatif_cache_daily d ON d.run_id = r.id
        WHERE r.dataset_key = :dataset_key
          AND r.scenario_id = :scenario_id
          AND r.control_mode = :control_mode
          AND r.horizon_steps = :horizon_steps
          AND r.top_k = :top_k
          AND r.status = 'complete'
          AND d.date >= :date_from
          AND d.date < :date_to
        GROUP BY r.cache_key
        HAVING count(DISTINCT d.date) = :expected_days
        ORDER BY max(r.completed_at) DESC NULLS LAST
        LIMIT 1
    """, dataset_key=ds.key, scenario_id=scenario_id, control_mode=CONTROL_MODE,
        horizon_steps=int(horizon_steps), top_k=int(top_k),
        date_from=start, date_to=end, expected_days=expected_days)


def read_cache_response(*, mode: str = CONTROL_MODE, date_from: str | None = None,
                        date_to: str | None = None, scenario_id: str | None = None,
                        horizon_steps: int | None = None, top_k: int | None = None) -> dict:
    ds = active_dataset()
    if mode != CONTROL_MODE:
        raise ValueError(f"unsupported what-if cache mode: {mode}")
    scenario = scenario_id or ds.scenario_id
    horizon = int(horizon_steps or get_settings().greenflow_control_horizon_steps)
    top = int(top_k or get_settings().greenflow_control_top_k)
    start = parse_local_date(date_from)
    end = parse_local_date(date_to)

    with db_conn() as conn:
        ensure_schema(conn)
        key_row = _completed_cache_key(
            conn, ds=ds, scenario_id=scenario, horizon_steps=horizon, top_k=top,
            start=start, end=end)
        if not key_row:
            raise LookupError(
                "precomputed what-if cache missing for "
                f"dataset={ds.key}, scenario={scenario}, mode={mode}, "
                f"date_from={date_from}, date_to={date_to}, "
                f"horizon_steps={horizon}, top_k={top}"
            )
        cache_key = key_row["cache_key"]
        if start is None:
            start = parse_local_date(key_row["date_from"])
        if end is None:
            end = parse_local_date(key_row["date_to"])
        rows = fetch_all(conn, """
            SELECT d.date, d.baseline_kwh, d.ai_kwh, d.saving_kwh, d.saving_percent,
                   d.baseline_peak_kw, d.ai_peak_kw, d.comfort_violation_min,
                   d.action_count
            FROM whatif_cache_daily d
            JOIN whatif_cache_runs r ON r.id = d.run_id
            WHERE r.cache_key = :cache_key
              AND r.status = 'complete'
              AND d.date >= :date_from
              AND d.date < :date_to
            ORDER BY d.date
        """, cache_key=cache_key, date_from=start, date_to=end)

    if not rows:
        raise LookupError(f"precomputed what-if cache has no daily rows for {cache_key}")

    daily = []
    for r in rows:
        daily.append({
            "date": str(r["date"]),
            "baseline_kwh": round(_f(r["baseline_kwh"]), 1),
            "optimized_kwh": round(_f(r["ai_kwh"]), 1),
            "peak_baseline_kw": round(_f(r["baseline_peak_kw"]), 2),
            "peak_optimized_kw": round(_f(r["ai_peak_kw"]), 2),
        })
    baseline = sum(_f(r["baseline_kwh"]) for r in rows)
    optimized = sum(_f(r["ai_kwh"]) for r in rows)
    saving = baseline - optimized
    peak_reduction_values = [
        _f(r["baseline_peak_kw"]) - _f(r["ai_peak_kw"]) for r in rows
    ]
    comfort = sum(_f(r["comfort_violation_min"]) for r in rows)
    return {
        "metadata": {
            "source": "precomputed_cache",
            "status": "complete",
            "control_mode": CONTROL_MODE,
            "cache_key": cache_key,
            "dataset": ds.to_metadata(),
            "scenario_id": scenario,
            "horizon_steps": horizon,
            "top_k": top,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
        "policy": {
            "engine": "predictive_mpc_replay",
            "peak_window": "receding-horizon",
            "setpoint_delta_c": None,
        },
        "kpi": {
            "baseline_kwh": round(baseline, 1),
            "optimized_kwh": round(optimized, 1),
            "saving_kwh": round(saving, 1),
            "saving_percent": round(saving / baseline * 100.0, 2) if baseline else 0.0,
            "cost_saving_vnd": round(saving * DEFAULT_AVG_TARIFF_VND_PER_KWH),
            "peak_reduction_kw": round(
                sum(peak_reduction_values) / len(peak_reduction_values), 2
            ) if peak_reduction_values else 0.0,
            "comfort_violation_delta_min": round(comfort, 1),
            "co2_avoided_kg": round(saving * GRID_CO2_KG_PER_KWH, 1),
            "days": len(daily),
        },
        "daily": daily,
    }


def validate_cache_range(*, date_from: str, date_to: str, scenario_id: str | None = None,
                         horizon_steps: int | None = None, top_k: int | None = None,
                         building_id: str | None = None) -> dict:
    ds = active_dataset()
    scenario = scenario_id or ds.scenario_id
    horizon = int(horizon_steps or get_settings().greenflow_control_horizon_steps)
    top = int(top_k or get_settings().greenflow_control_top_k)
    start = parse_local_date(date_from)
    end = parse_local_date(date_to)
    if start is None or end is None or start >= end:
        raise ValueError("date_from/date_to are required and date_from must be before date_to")
    expected_days = (end - start).days
    expected_steps = telemetry_step_count(
        scenario_id=scenario, start=start, end=end, building_id=building_id)
    if expected_steps <= 0:
        expected_steps = expected_step_count(start, end, timestep_minutes=ds.timestep_minutes)
    expected_dates = {start + timedelta(days=i) for i in range(expected_days)}

    with db_conn() as conn:
        ensure_schema(conn)
        key_row = _completed_cache_key(
            conn, ds=ds, scenario_id=scenario, horizon_steps=horizon, top_k=top,
            start=start, end=end)
        cache_key = key_row["cache_key"] if key_row else None
        if cache_key:
            daily_rows = fetch_all(conn, """
                SELECT d.date
                FROM whatif_cache_daily d
                JOIN whatif_cache_runs r ON r.id = d.run_id
                WHERE r.cache_key = :cache_key
                  AND r.status = 'complete'
                  AND d.date >= :date_from
                  AND d.date < :date_to
                ORDER BY d.date
            """, cache_key=cache_key, date_from=start, date_to=end)
            step_row = fetch_one(conn, """
                SELECT count(*) AS n
                FROM whatif_cache_timestep t
                JOIN whatif_cache_runs r ON r.id = t.run_id
                WHERE r.cache_key = :cache_key
                  AND r.status = 'complete'
                  AND t.timestamp >= CAST(:date_from AS timestamptz)
                  AND t.timestamp < CAST(:date_to AS timestamptz)
            """, cache_key=cache_key, date_from=local_midnight(start),
                date_to=local_midnight(end))
            error_rows = fetch_all(conn, """
                SELECT id, error FROM whatif_cache_runs
                WHERE cache_key = :cache_key
                  AND date_from >= CAST(:date_from AS timestamptz)
                  AND date_to <= CAST(:date_to AS timestamptz)
                  AND COALESCE(error, '') <> ''
            """, cache_key=cache_key, date_from=local_midnight(start),
                date_to=local_midnight(end))
        else:
            daily_rows, step_row, error_rows = [], {"n": 0}, []

    found_dates = {parse_local_date(r["date"]) for r in daily_rows}
    missing = sorted(d for d in expected_dates if d not in found_dates)
    summary = {
        "dataset_key": ds.key,
        "scenario_id": scenario,
        "control_mode": CONTROL_MODE,
        "cache_key": cache_key,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "expected_days": expected_days,
        "days_complete": len(found_dates),
        "missing_days": [d.isoformat() for d in missing],
        "expected_steps": expected_steps,
        "total_steps": int((step_row or {}).get("n") or 0),
        "errors": len(error_rows),
        "error_rows": error_rows,
        "source": "precomputed_cache" if cache_key else "missing",
    }
    summary["checks"] = {
        "cache_key": cache_key is not None,
        "days_complete": len(found_dates) == expected_days,
        "missing_days": not missing,
        "total_steps": summary["total_steps"] == expected_steps,
        "errors": len(error_rows) == 0,
    }
    summary["ok"] = all(summary["checks"].values())
    return summary
