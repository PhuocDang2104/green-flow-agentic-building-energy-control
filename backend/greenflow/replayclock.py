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
    """Mốc 'now'. Ưu tiên replay_now cấu hình; else max(timestamp); else wall-clock."""
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
