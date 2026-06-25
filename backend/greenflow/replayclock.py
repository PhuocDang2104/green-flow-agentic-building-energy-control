"""Replay clock — "bây giờ" của digital twin.

Telemetry là một NĂM ĐÃ GHI (EnergyPlus 2025), app phát lại (replay). Vì vậy
"now" KHÔNG phải wall-clock — nếu dùng now() thật (2026) trên data 2025 thì mọi
truy vấn "gần đây" rỗng. Tất cả chỗ cần "hiện tại" trên telemetry phải dùng
anchor này.

settings.replay_now (ISO, vd "2025-07-30T14:00:00") ghim "now" vào một ngày hè
tải cao để demo đẹp. Rỗng -> max(timestamp) trong telemetry.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import get_settings
from .db import db_conn, fetch_one

TZ = timezone(timedelta(hours=7))

# Streaming mode: when set, "now" advances with wall-clock so dashboards move.
# Process-global (set via the /api/replay/stream toggle); single-ref read/write
# is atomic under the GIL, no lock needed. None = static (pinned) behaviour.
_stream: dict | None = None  # {"started", "speed", "lo", "hi", "base"}


def _configured() -> datetime | None:
    s = (get_settings().replay_now or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def anchor(conn=None, building_id=None) -> datetime:
    """Mốc 'now'. Streaming mode (advancing) > replay_now ghim > max(timestamp) > wall-clock."""
    s = _stream
    if s is not None:
        # virtual now = base + elapsed_wall * speed, looped within the data range
        elapsed = (datetime.now(timezone.utc) - s["started"]).total_seconds() * s["speed"]
        span = (s["hi"] - s["lo"]).total_seconds()
        if span <= 0:
            return s["base"]
        pos = (s["base"] - s["lo"]).total_seconds() + elapsed
        off = pos % span
        step = s.get("step", 1800)
        off = (int(off) // step) * step  # snap down to the telemetry grid
        return s["lo"] + timedelta(seconds=off)
    cfg = _configured()
    if cfg is not None:
        return cfg
    sql = "SELECT max(timestamp) AS ts FROM telemetry_zone_15m"
    params = {}
    if building_id is not None:
        sql += " WHERE building_id = :b"
        params["b"] = building_id
    if conn is not None:
        row = fetch_one(conn, sql, **params)
    else:
        with db_conn() as c:
            row = fetch_one(c, sql, **params)
    return row["ts"] if row and row.get("ts") else datetime.now(TZ)


def start_stream(conn, building_id, speed: float = 360.0) -> dict:
    """Start advancing the clock: 1 real second -> `speed` virtual seconds,
    starting from the pinned demo time (or latest) and looping over the recorded
    range. Default 360x -> a ~30-min data step every ~5 real seconds."""
    global _stream
    row = fetch_one(conn, "SELECT min(timestamp) AS lo, max(timestamp) AS hi "
                    "FROM telemetry_zone_15m WHERE building_id = :b", b=building_id)
    lo, hi = (row or {}).get("lo"), (row or {}).get("hi")
    if not lo or not hi:
        raise ValueError("no telemetry to stream")
    base = _configured() or hi  # start at the pinned demo time if set, else latest
    if base < lo or base > hi:
        base = lo
    # telemetry grid step (gap between the first two distinct ticks) — the virtual
    # clock snaps to this so exact-match snapshot queries land on a real row.
    gap = fetch_one(conn, "SELECT EXTRACT(EPOCH FROM (max(ts)-min(ts)))::int AS step "
                    "FROM (SELECT DISTINCT timestamp AS ts FROM telemetry_zone_15m "
                    "WHERE building_id = :b ORDER BY timestamp LIMIT 2) q", b=building_id)
    step = int((gap or {}).get("step") or 1800) or 1800
    _stream = {"started": datetime.now(timezone.utc), "speed": max(1.0, float(speed)),
               "lo": lo, "hi": hi, "base": base, "step": step}
    return stream_status()


def stop_stream() -> dict:
    global _stream
    _stream = None
    return stream_status()


def stream_status() -> dict:
    if _stream is None:
        return {"streaming": False, "speed": None, "now": anchor().isoformat()}
    s = _stream
    return {"streaming": True, "speed": s["speed"], "now": anchor().isoformat(),
            "window": [s["lo"].isoformat(), s["hi"].isoformat()]}
