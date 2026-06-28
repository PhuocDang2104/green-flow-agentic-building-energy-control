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
OBJECTIVE_VERSION = "v2_policy_aware"
CONTROLLER_VERSION = "predictive_mpc_v8"
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
    conn.execute(text("ALTER TABLE whatif_cache_daily ADD COLUMN IF NOT EXISTS baseline_comfort_violation_min numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_daily ADD COLUMN IF NOT EXISTS ai_added_comfort_violation_min numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_daily ADD COLUMN IF NOT EXISTS lighting_saving_kwh numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_daily ADD COLUMN IF NOT EXISTS hvac_saving_kwh numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_daily ADD COLUMN IF NOT EXISTS policy_violation_count int"))
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
    conn.execute(text("ALTER TABLE whatif_cache_timestep ADD COLUMN IF NOT EXISTS baseline_comfort_violation_min numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_timestep ADD COLUMN IF NOT EXISTS ai_added_comfort_violation_min numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_timestep ADD COLUMN IF NOT EXISTS lighting_saving_kwh numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_timestep ADD COLUMN IF NOT EXISTS hvac_saving_kwh numeric"))
    conn.execute(text("ALTER TABLE whatif_cache_timestep ADD COLUMN IF NOT EXISTS policy_violation_count int"))
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
    from ..ml.model_registry import REGISTERED_MODELS, model_contract

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
    run_id = None
    selector = version
    if configured_source == "mlflow" and registered and version:
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        client = mlflow.MlflowClient()
        if "@" in model_uri:
            resolved = client.get_model_version_by_alias(registered, version)
        elif version.isdigit():
            resolved = client.get_model_version(registered, version)
        else:
            resolved = None
        if resolved is not None:
            version = str(resolved.version)
            run_id = resolved.run_id
    contract = model_contract("zone")
    return {
        "key": "zone",
        "source": configured_source,
        "registered_model": registered,
        "model_uri": model_uri,
        "version": version,
        "selector": selector,
        "run_id": run_id,
        "dataset": contract,
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
            "run_id": model_metadata.get("run_id"),
            "dataset_sha256": (model_metadata.get("dataset") or {}).get("source_sha256"),
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
        "baseline_comfort_violation_min": 0.0,
        "comfort_violation_min": 0.0,
        "ai_added_comfort_violation_min": 0.0,
        "lighting_saving_kwh": 0.0,
        "hvac_saving_kwh": 0.0,
        "policy_violation_count": 0,
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
        rec["baseline_comfort_violation_min"] += _f(row.get("baseline_comfort_violation_min"))
        rec["comfort_violation_min"] += _f(row.get("comfort_violation_min"))
        rec["ai_added_comfort_violation_min"] += _f(row.get("ai_added_comfort_violation_min"))
        rec["lighting_saving_kwh"] += _f(row.get("lighting_saving_kwh"))
        rec["hvac_saving_kwh"] += _f(row.get("hvac_saving_kwh"))
        rec["policy_violation_count"] += int(_f(row.get("policy_violation_count")))
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
            "baseline_comfort_violation_min": round(rec["baseline_comfort_violation_min"], 6),
            "comfort_violation_min": round(rec["comfort_violation_min"], 6),
            "ai_added_comfort_violation_min": round(rec["ai_added_comfort_violation_min"], 6),
            "lighting_saving_kwh": round(rec["lighting_saving_kwh"], 6),
            "hvac_saving_kwh": round(rec["hvac_saving_kwh"], 6),
            "policy_violation_count": int(rec["policy_violation_count"]),
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
              baseline_peak_kw, ai_peak_kw, baseline_comfort_violation_min,
              comfort_violation_min, ai_added_comfort_violation_min,
              lighting_saving_kwh, hvac_saving_kwh, policy_violation_count,
              action_count
            )
            VALUES (:run_id, :date, :baseline_kwh, :ai_kwh, :saving_kwh, :saving_percent,
                    :baseline_peak_kw, :ai_peak_kw, :baseline_comfort_violation_min,
                    :comfort_violation_min, :ai_added_comfort_violation_min,
                    :lighting_saving_kwh, :hvac_saving_kwh, :policy_violation_count,
                    :action_count)
            ON CONFLICT (run_id, date) DO UPDATE SET
              baseline_kwh = EXCLUDED.baseline_kwh,
              ai_kwh = EXCLUDED.ai_kwh,
              saving_kwh = EXCLUDED.saving_kwh,
              saving_percent = EXCLUDED.saving_percent,
              baseline_peak_kw = EXCLUDED.baseline_peak_kw,
              ai_peak_kw = EXCLUDED.ai_peak_kw,
              baseline_comfort_violation_min = EXCLUDED.baseline_comfort_violation_min,
              comfort_violation_min = EXCLUDED.comfort_violation_min,
              ai_added_comfort_violation_min = EXCLUDED.ai_added_comfort_violation_min,
              lighting_saving_kwh = EXCLUDED.lighting_saving_kwh,
              hvac_saving_kwh = EXCLUDED.hvac_saving_kwh,
              policy_violation_count = EXCLUDED.policy_violation_count,
              action_count = EXCLUDED.action_count
        """), {"run_id": run_id, **day})

    for row in series:
        ts = str(row["timestamp"])
        conn.execute(text("""
            INSERT INTO whatif_cache_timestep (
              run_id, timestamp, baseline_kw, ai_kw, baseline_kwh, ai_kwh,
              saving_kwh, baseline_comfort_violation_min, comfort_violation_min,
              ai_added_comfort_violation_min, lighting_saving_kwh, hvac_saving_kwh,
              policy_violation_count, selected_trajectory, objective_score, action_json
            )
            VALUES (
              :run_id, CAST(:timestamp AS timestamptz), :baseline_kw, :ai_kw,
              :baseline_kwh, :ai_kwh, :saving_kwh, :baseline_comfort_violation_min,
              :comfort_violation_min, :ai_added_comfort_violation_min,
              :lighting_saving_kwh, :hvac_saving_kwh, :policy_violation_count,
              :selected_trajectory, :objective_score, CAST(:action_json AS jsonb)
            )
            ON CONFLICT (run_id, timestamp) DO UPDATE SET
              baseline_kw = EXCLUDED.baseline_kw,
              ai_kw = EXCLUDED.ai_kw,
              baseline_kwh = EXCLUDED.baseline_kwh,
              ai_kwh = EXCLUDED.ai_kwh,
              saving_kwh = EXCLUDED.saving_kwh,
              baseline_comfort_violation_min = EXCLUDED.baseline_comfort_violation_min,
              comfort_violation_min = EXCLUDED.comfort_violation_min,
              ai_added_comfort_violation_min = EXCLUDED.ai_added_comfort_violation_min,
              lighting_saving_kwh = EXCLUDED.lighting_saving_kwh,
              hvac_saving_kwh = EXCLUDED.hvac_saving_kwh,
              policy_violation_count = EXCLUDED.policy_violation_count,
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
            "baseline_comfort_violation_min": row.get("baseline_comfort_violation_min"),
            "comfort_violation_min": row.get("comfort_violation_min"),
            "ai_added_comfort_violation_min": row.get("ai_added_comfort_violation_min"),
            "lighting_saving_kwh": row.get("lighting_saving_kwh"),
            "hvac_saving_kwh": row.get("hvac_saving_kwh"),
            "policy_violation_count": row.get("policy_violation_count"),
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


def _local_iso(value: Any) -> str:
    if hasattr(value, "astimezone"):
        return value.astimezone(TZ).isoformat()
    return str(value)


def _action_setpoint_delta(value: Any, zone_count: int) -> float:
    if zone_count <= 0:
        return 0.0
    actions = value or []
    if isinstance(actions, str):
        try:
            actions = json.loads(actions)
        except json.JSONDecodeError:
            actions = []
    if not isinstance(actions, list):
        return 0.0
    by_zone: dict[str, float] = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        delta = _f(action.get("setpoint_delta_c"))
        if not delta:
            continue
        for key in action.get("target_zone_keys") or []:
            by_zone[str(key)] = by_zone.get(str(key), 0.0) + delta
    return sum(by_zone.values()) / float(zone_count)


def _local_date_key(value: Any) -> str:
    if hasattr(value, "astimezone"):
        return value.astimezone(TZ).date().isoformat()
    return str(value)[:10]


def read_cache_response(*, mode: str = CONTROL_MODE, date_from: str | None = None,
                        date_to: str | None = None, scenario_id: str | None = None,
                        horizon_steps: int | None = None, top_k: int | None = None,
                        resolution: str = "auto") -> dict:
    ds = active_dataset()
    if mode != CONTROL_MODE:
        raise ValueError(f"unsupported what-if cache mode: {mode}")
    scenario = scenario_id or ds.scenario_id
    horizon = int(horizon_steps or get_settings().greenflow_control_horizon_steps)
    top = int(top_k or get_settings().greenflow_control_top_k)
    start = parse_local_date(date_from)
    end = parse_local_date(date_to)
    resolution = (resolution or "auto").lower()
    if resolution not in {"auto", "daily", "timestep"}:
        raise ValueError("resolution must be one of: auto, daily, timestep")

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
                   d.baseline_comfort_violation_min, d.ai_added_comfort_violation_min,
                   d.lighting_saving_kwh, d.hvac_saving_kwh, d.policy_violation_count,
                   d.action_count
            FROM whatif_cache_daily d
            JOIN whatif_cache_runs r ON r.id = d.run_id
            WHERE r.cache_key = :cache_key
              AND r.status = 'complete'
              AND d.date >= :date_from
              AND d.date < :date_to
            ORDER BY d.date
        """, cache_key=cache_key, date_from=start, date_to=end)
        span_days = max(0, (end - start).days) if start and end else 0
        effective_resolution = (
            "timestep" if resolution == "timestep"
            else "timestep" if resolution == "auto" and 0 < span_days <= 2
            else "daily"
        )
        step_rows = []
        if effective_resolution == "timestep":
            step_rows = fetch_all(conn, """
                SELECT t.timestamp, t.baseline_kw, t.ai_kw, t.baseline_kwh,
                       t.ai_kwh, t.saving_kwh, t.comfort_violation_min,
                       t.baseline_comfort_violation_min, t.ai_added_comfort_violation_min,
                       t.lighting_saving_kwh, t.hvac_saving_kwh, t.policy_violation_count,
                       t.selected_trajectory, t.action_json
                FROM whatif_cache_timestep t
                JOIN whatif_cache_runs r ON r.id = t.run_id
                WHERE r.cache_key = :cache_key
                  AND r.status = 'complete'
                  AND t.timestamp >= CAST(:date_from AS timestamptz)
                  AND t.timestamp < CAST(:date_to AS timestamptz)
                ORDER BY t.timestamp
            """, cache_key=cache_key, date_from=local_midnight(start),
                date_to=local_midnight(end))
        else:
            step_rows = fetch_all(conn, """
                SELECT t.timestamp, t.baseline_kw, t.ai_kw, t.baseline_kwh,
                       t.ai_kwh, t.saving_kwh, t.comfort_violation_min,
                       t.baseline_comfort_violation_min, t.ai_added_comfort_violation_min,
                       t.lighting_saving_kwh, t.hvac_saving_kwh, t.policy_violation_count,
                       t.selected_trajectory, t.action_json
                FROM whatif_cache_timestep t
                JOIN whatif_cache_runs r ON r.id = t.run_id
                WHERE r.cache_key = :cache_key
                  AND r.status = 'complete'
                  AND t.timestamp >= CAST(:date_from AS timestamptz)
                  AND t.timestamp < CAST(:date_to AS timestamptz)
                ORDER BY t.timestamp
            """, cache_key=cache_key, date_from=local_midnight(start),
                date_to=local_midnight(end))
        telemetry_rows = fetch_all(conn, """
            SELECT timestamp,
                   avg(temperature_c) AS baseline_temperature_c,
                   avg(COALESCE(setpoint_c, 24)) AS baseline_setpoint_c,
                   count(*) AS zone_count
            FROM telemetry_zone_15m
            WHERE timestamp >= CAST(:date_from AS timestamptz)
              AND timestamp < CAST(:date_to AS timestamptz)
              AND (CAST(:scenario_id AS text) IS NULL
                   OR scenario_id = CAST(:scenario_id AS text)
                   OR scenario_id IS NULL)
            GROUP BY timestamp
            ORDER BY timestamp
        """, date_from=local_midnight(start), date_to=local_midnight(end),
            scenario_id=scenario)

    if not rows:
        raise LookupError(f"precomputed what-if cache has no daily rows for {cache_key}")

    telemetry_by_ts = {_local_iso(r["timestamp"]): r for r in telemetry_rows}
    baseline_peak_for_loading = max((_f(r.get("baseline_kw")) for r in step_rows), default=0.0)
    timestep_series = []
    for r in step_rows:
        ts_iso = _local_iso(r["timestamp"])
        tele = telemetry_by_ts.get(ts_iso) or {}
        zone_count = int(_f(tele.get("zone_count"), ds.expected_zones) or ds.expected_zones)
        avg_delta = _action_setpoint_delta(r.get("action_json"), zone_count)
        base_temp = _f(tele.get("baseline_temperature_c"), 25.0)
        base_setpoint = _f(tele.get("baseline_setpoint_c"), 24.0)
        base_kw = _f(r.get("baseline_kw"))
        ai_kw = _f(r.get("ai_kw"))
        denom = baseline_peak_for_loading or max(base_kw, ai_kw, 1.0)
        timestep_series.append({
            "timestamp": ts_iso,
            "date": _local_date_key(r["timestamp"]),
            "baseline_kwh": round(_f(r["baseline_kwh"]), 4),
            "optimized_kwh": round(_f(r["ai_kwh"]), 4),
            "peak_baseline_kw": round(base_kw, 3),
            "peak_optimized_kw": round(ai_kw, 3),
            "baseline_temperature_c": round(base_temp, 3),
            "optimized_temperature_c": round(base_temp + 0.4 * avg_delta, 3),
            "baseline_setpoint_c": round(base_setpoint, 3),
            "optimized_setpoint_c": round(base_setpoint + avg_delta, 3),
            "baseline_loading_pct": round(base_kw / denom * 100.0, 3) if denom else 0.0,
            "optimized_loading_pct": round(ai_kw / denom * 100.0, 3) if denom else 0.0,
            "saving_kwh": round(_f(r["saving_kwh"]), 4),
            "baseline_comfort_violation_min": round(_f(r.get("baseline_comfort_violation_min")), 2),
            "comfort_violation_min": round(_f(r["comfort_violation_min"]), 2),
            "ai_added_comfort_violation_min": round(_f(r.get("ai_added_comfort_violation_min")), 2),
            "lighting_saving_kwh": round(_f(r.get("lighting_saving_kwh")), 4),
            "hvac_saving_kwh": round(_f(r.get("hvac_saving_kwh")), 4),
            "policy_violation_count": int(_f(r.get("policy_violation_count"))),
            "selected_trajectory": r.get("selected_trajectory"),
        })

    by_day_extra: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "n": 0,
        "baseline_temperature_c": 0.0,
        "optimized_temperature_c": 0.0,
        "baseline_setpoint_c": 0.0,
        "optimized_setpoint_c": 0.0,
        "baseline_loading_pct": 0.0,
        "optimized_loading_pct": 0.0,
        "baseline_comfort_violation_min": 0.0,
        "ai_added_comfort_violation_min": 0.0,
        "lighting_saving_kwh": 0.0,
        "hvac_saving_kwh": 0.0,
        "policy_violation_count": 0,
    })
    for point in timestep_series:
        rec = by_day_extra[point["date"]]
        rec["n"] += 1
        for key in ("baseline_temperature_c", "optimized_temperature_c",
                    "baseline_setpoint_c", "optimized_setpoint_c"):
            rec[key] += _f(point[key])
        rec["baseline_loading_pct"] = max(rec["baseline_loading_pct"], _f(point["baseline_loading_pct"]))
        rec["optimized_loading_pct"] = max(rec["optimized_loading_pct"], _f(point["optimized_loading_pct"]))
        for key in ("baseline_comfort_violation_min", "ai_added_comfort_violation_min",
                    "lighting_saving_kwh", "hvac_saving_kwh", "policy_violation_count"):
            rec[key] += _f(point.get(key))

    daily = []
    for r in rows:
        extras = by_day_extra.get(str(r["date"])) or {}
        n = int(extras.get("n") or 0)
        daily.append({
            "date": str(r["date"]),
            "baseline_kwh": round(_f(r["baseline_kwh"]), 1),
            "optimized_kwh": round(_f(r["ai_kwh"]), 1),
            "peak_baseline_kw": round(_f(r["baseline_peak_kw"]), 2),
            "peak_optimized_kw": round(_f(r["ai_peak_kw"]), 2),
            "baseline_temperature_c": round(_f(extras.get("baseline_temperature_c")) / n, 2) if n else None,
            "optimized_temperature_c": round(_f(extras.get("optimized_temperature_c")) / n, 2) if n else None,
            "baseline_setpoint_c": round(_f(extras.get("baseline_setpoint_c")) / n, 2) if n else None,
            "optimized_setpoint_c": round(_f(extras.get("optimized_setpoint_c")) / n, 2) if n else None,
            "baseline_loading_pct": round(_f(extras.get("baseline_loading_pct")), 1) if n else None,
            "optimized_loading_pct": round(_f(extras.get("optimized_loading_pct")), 1) if n else None,
            "baseline_comfort_violation_min": round(_f(extras.get("baseline_comfort_violation_min")), 2),
            "ai_added_comfort_violation_min": round(_f(extras.get("ai_added_comfort_violation_min")), 2),
            "lighting_saving_kwh": round(_f(extras.get("lighting_saving_kwh")), 2),
            "hvac_saving_kwh": round(_f(extras.get("hvac_saving_kwh")), 2),
            "policy_violation_count": int(_f(extras.get("policy_violation_count"))),
        })
    baseline = sum(_f(r["baseline_kwh"]) for r in rows)
    optimized = sum(_f(r["ai_kwh"]) for r in rows)
    saving = baseline - optimized
    peak_reduction_values = [
        _f(r["baseline_peak_kw"]) - _f(r["ai_peak_kw"]) for r in rows
    ]
    comfort = sum(_f(r["comfort_violation_min"]) for r in rows)
    baseline_comfort = sum(_f(r.get("baseline_comfort_violation_min")) for r in rows)
    ai_added_comfort = sum(_f(r.get("ai_added_comfort_violation_min")) for r in rows)
    lighting_saving = sum(_f(r.get("lighting_saving_kwh")) for r in rows)
    hvac_saving = sum(_f(r.get("hvac_saving_kwh")) for r in rows)
    policy_violations = sum(int(_f(r.get("policy_violation_count"))) for r in rows)
    series = []
    if effective_resolution == "timestep":
        series = timestep_series
    return {
        "metadata": {
            "source": "precomputed_cache",
            "status": "complete",
            "control_mode": CONTROL_MODE,
            "resolution": effective_resolution,
            "point_count": len(series) if effective_resolution == "timestep" else len(daily),
            "metric_thresholds": {
                "comfort_temperature_c": {"min": 23.0, "max": 26.0},
                "electrical_loading_pct": [80.0, 90.0, 100.0],
                "loading_basis": "normalized_to_selected_range_baseline_peak",
            },
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
            "baseline_comfort_violation_min": round(baseline_comfort, 1),
            "comfort_violation_delta_min": round(comfort, 1),
            "ai_added_comfort_violation_min": round(ai_added_comfort, 1),
            "lighting_saving_kwh": round(lighting_saving, 1),
            "hvac_saving_kwh": round(hvac_saving, 1),
            "policy_violation_count": int(policy_violations),
            "co2_avoided_kg": round(saving * GRID_CO2_KG_PER_KWH, 1),
            "days": len(daily),
        },
        "daily": daily,
        "series": series,
    }


def validate_cache_range(*, date_from: str, date_to: str, scenario_id: str | None = None,
                         horizon_steps: int | None = None, top_k: int | None = None,
                         building_id: str | None = None,
                         min_saving_percent: float = 0.0) -> dict:
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
            total_row = fetch_one(conn, """
                SELECT COALESCE(sum(d.baseline_kwh), 0) AS baseline_kwh,
                       COALESCE(sum(d.ai_kwh), 0) AS ai_kwh,
                       COALESCE(sum(d.saving_kwh), 0) AS saving_kwh,
                       COALESCE(sum(d.lighting_saving_kwh), 0) AS lighting_saving_kwh,
                       COALESCE(sum(d.hvac_saving_kwh), 0) AS hvac_saving_kwh,
                       COALESCE(sum(d.baseline_comfort_violation_min), 0) AS baseline_comfort_violation_min,
                       COALESCE(sum(d.comfort_violation_min), 0) AS ai_comfort_violation_min,
                       COALESCE(sum(d.ai_added_comfort_violation_min), 0) AS ai_added_comfort_violation_min,
                       COALESCE(sum(d.policy_violation_count), 0) AS policy_violation_count
                FROM whatif_cache_daily d
                JOIN whatif_cache_runs r ON r.id = d.run_id
                WHERE r.cache_key = :cache_key
                  AND r.status = 'complete'
                  AND d.date >= :date_from
                  AND d.date < :date_to
            """, cache_key=cache_key, date_from=start, date_to=end)
            error_rows = fetch_all(conn, """
                SELECT id, error FROM whatif_cache_runs
                WHERE cache_key = :cache_key
                  AND date_from >= CAST(:date_from AS timestamptz)
                  AND date_to <= CAST(:date_to AS timestamptz)
                  AND COALESCE(error, '') <> ''
            """, cache_key=cache_key, date_from=local_midnight(start),
                date_to=local_midnight(end))
        else:
            daily_rows, step_row, total_row, error_rows = [], {"n": 0}, {}, []

    found_dates = {parse_local_date(r["date"]) for r in daily_rows}
    missing = sorted(d for d in expected_dates if d not in found_dates)
    baseline_kwh = _f((total_row or {}).get("baseline_kwh"))
    ai_kwh = _f((total_row or {}).get("ai_kwh"))
    saving_kwh = _f((total_row or {}).get("saving_kwh"))
    lighting_saving_kwh = _f((total_row or {}).get("lighting_saving_kwh"))
    hvac_saving_kwh = _f((total_row or {}).get("hvac_saving_kwh"))
    baseline_comfort_min = _f((total_row or {}).get("baseline_comfort_violation_min"))
    ai_comfort_min = _f((total_row or {}).get("ai_comfort_violation_min"))
    ai_added_comfort_min = _f((total_row or {}).get("ai_added_comfort_violation_min"))
    policy_violation_count = int(_f((total_row or {}).get("policy_violation_count")))
    saving_percent = saving_kwh / baseline_kwh * 100.0 if baseline_kwh else 0.0
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
        "baseline_kwh": round(baseline_kwh, 3),
        "ai_kwh": round(ai_kwh, 3),
        "saving_kwh": round(saving_kwh, 3),
        "saving_percent": round(saving_percent, 3),
        "lighting_saving_kwh": round(lighting_saving_kwh, 3),
        "hvac_saving_kwh": round(hvac_saving_kwh, 3),
        "baseline_comfort_violation_min": round(baseline_comfort_min, 3),
        "ai_comfort_violation_min": round(ai_comfort_min, 3),
        "ai_added_comfort_violation_min": round(ai_added_comfort_min, 3),
        "policy_violation_count": policy_violation_count,
        "min_saving_percent": float(min_saving_percent),
        "source": "precomputed_cache" if cache_key else "missing",
    }
    summary["checks"] = {
        "cache_key": cache_key is not None,
        "days_complete": len(found_dates) == expected_days,
        "missing_days": not missing,
        "total_steps": summary["total_steps"] == expected_steps,
        "errors": len(error_rows) == 0,
        "saving_positive": saving_kwh > 0,
        "saving_threshold": saving_percent >= float(min_saving_percent),
        "policy_ok": policy_violation_count == 0,
        "comfort_tradeoff_ok": ai_added_comfort_min <= 1e-6,
    }
    summary["ok"] = all(summary["checks"].values())
    return summary
