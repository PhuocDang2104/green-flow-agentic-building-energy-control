"""WebSocket state broadcasting + telemetry replay ticker.

The replay ticker walks the seeded 15-minute telemetry of the most recent day
on a wall-clock cadence (REPLAY_SPEED_SECONDS per tick) and broadcasts each
tick to /ws/building/{building_id}/state subscribers — the "mock realtime"
mode from REPO_BUILD_SPEC §2.2. Agent events are also pushed here.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket

from ..config import get_settings
from ..db import db_conn, fetch_all
from ..agent.tools.db_tool import _clean


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms[room].add(ws)

    def disconnect(self, room: str, ws: WebSocket) -> None:
        self.rooms[room].discard(ws)

    async def broadcast(self, room: str, payload: dict) -> None:
        message = json.dumps(payload, default=str)
        dead = []
        for ws in self.rooms[room]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)


manager = ConnectionManager()


async def replay_ticker() -> None:
    """Cycle through the latest day of telemetry, one 15-min tick per interval."""
    from ..replayclock import stream_status
    settings = get_settings()
    building_id = settings.default_building_id
    interval = max(2, settings.replay_speed_seconds)
    tick_index = 0

    while True:
        try:
            # psycopg connect/query is blocking; run it off the event loop so a
            # slow or unreachable Postgres never freezes HTTP request handling.
            status = await asyncio.to_thread(stream_status)
            if status["streaming"]:
                # Streaming: broadcast the virtual 'now' (grid-snapped) so the 3D
                # viewer tracks the same clock as the polled KPI cards.
                ts = status["now"]
            else:
                timestamps = await asyncio.to_thread(_distinct_timestamps, building_id)
                ts = timestamps[tick_index % len(timestamps)] if timestamps else None
                tick_index += 1
            if ts:
                zones = await asyncio.to_thread(_zone_states_at, building_id, ts)
                total_kw = sum(z.get("total_power_kw") or 0 for z in zones.values())
                occupancy = sum(z.get("occupancy_count") or 0 for z in zones.values())
                await manager.broadcast(f"building:{building_id}", {
                    "type": "state_tick",
                    "timestamp": ts,
                    "building": {"total_power_kw": round(total_kw, 2),
                                 "occupancy": occupancy},
                    "zones": zones,
                })
        except Exception:
            pass  # ticker must survive DB hiccups
        await asyncio.sleep(interval)


async def monitor_ticker() -> None:
    """Periodic agent monitor: once per virtual hour (throttled to ≥45s real, and
    only while streaming so the twin clock is moving), scan for faults and post a
    digest into the '🛰 Agent monitor' chat session."""
    import time
    from ..replayclock import anchor, stream_status
    from ..agent.reporting import run_monitor_cycle
    building_id = get_settings().default_building_id
    last_hour = None
    last_post = 0.0
    while True:
        try:
            st = await asyncio.to_thread(stream_status)
            if st.get("streaming"):
                now = await asyncio.to_thread(anchor, None, building_id)
                hour = now.replace(minute=0, second=0, microsecond=0)
                if hour != last_hour and (time.monotonic() - last_post) > 45:
                    last_hour = hour
                    posted = await asyncio.to_thread(run_monitor_cycle, building_id)
                    if posted:
                        last_post = time.monotonic()
        except Exception:
            pass  # the monitor must survive DB hiccups
        await asyncio.sleep(5)


async def broadcast_agent_event(building_id: str, event: dict) -> None:
    await manager.broadcast(f"building:{building_id}",
                            {"type": "agent_event", **event})


def _distinct_timestamps(building_id: str) -> list:
    from ..replayclock import anchor
    with db_conn() as conn:
        a = anchor(conn, building_id)
        rows = fetch_all(conn, """
            SELECT DISTINCT timestamp FROM telemetry_zone_15m
            WHERE building_id = :b AND timestamp > :a - interval '24 hours' AND timestamp <= :a
            ORDER BY timestamp
        """, b=building_id, a=a)
    return [r["timestamp"].isoformat() for r in rows]


def _zone_states_at(building_id: str, ts: str) -> dict[str, dict]:
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT z.entity_key, t.occupancy_count, t.temperature_c, t.hvac_power_kw,
                   t.lighting_power_kw, t.plug_power_kw, t.total_power_kw,
                   t.setpoint_c, t.comfort_risk, t.peak_risk, t.anomaly_label
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND t.timestamp = cast(:ts as timestamptz)
        """, b=building_id, ts=ts)
    return {r["entity_key"]: _clean(r) for r in rows}
