"""Replay streaming control — advance the digital-twin clock for a live demo.

When streaming is on, replayclock.anchor() advances with wall-clock, so every
endpoint that reads "now" (KPIs, energy, comfort, peak, faults, time-series)
returns moving data and the polling dashboards come alive.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ...db import db_conn
from ...replayclock import start_stream, stop_stream, stream_status
from ..deps import default_building_id

router = APIRouter(prefix="/replay")


class StreamRequest(BaseModel):
    on: bool
    speed: float = 360.0
    building_id: str | None = None


@router.post("/stream")
def stream(req: StreamRequest):
    if req.on:
        b = req.building_id or default_building_id()
        with db_conn() as conn:
            return start_stream(conn, b, speed=req.speed)
    return stop_stream()


@router.get("/status")
def status():
    return stream_status()
