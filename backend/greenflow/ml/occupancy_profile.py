"""Hồ sơ occupancy — học từ telemetry cũ (DB) + override sự kiện. KHÔNG phải ML forecaster.

Occupancy văn phòng tất định theo lịch -> chỉ cần BẢNG HỒ SƠ (trung vị theo
zone × loại ngày × slot 15') học từ telemetry_zone_15m. Real-time = YOLO (riêng).
occupancy_intensity (cho surrogate) = count / sức chứa thiết kế (area / m²/người).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import median

from ..db import fetch_all
from .forecast_service import archetype_of

M2_PER_PERSON = {"open_office": 10, "office": 12, "meeting": 3, "amenity": 8, "circulation": 40}
VN_TZ = timezone(timedelta(hours=7))


def _vn(ts):
    """timestamptz (có thể UTC) -> giờ địa phương VN; naive giữ nguyên."""
    return ts.astimezone(VN_TZ) if ts.tzinfo else ts


def _daytype(ts) -> str:
    return "weekend" if _vn(ts).weekday() >= 5 else "weekday"


def _slot(ts) -> int:
    t = _vn(ts)
    return t.hour * 4 + t.minute // 15


def _capacity(room_type, area_m2) -> float:
    return max(1.0, float(area_m2 or 50.0) / M2_PER_PERSON.get(archetype_of(room_type), 12))


@dataclass
class Event:
    entity_keys: set
    start: datetime
    end: datetime
    mult: float = 1.0


@dataclass
class OccupancyProfile:
    # (entity_key, daytype, slot) -> {frac, count, iqr}
    table: dict
    meta: dict                       # entity_key -> {room_type, area_m2, capacity}
    events: list = field(default_factory=list)

    @classmethod
    def learn(cls, conn, building_id) -> "OccupancyProfile":
        rows = fetch_all(conn, """
            SELECT z.entity_key, z.room_type, z.area_m2, t.timestamp, t.occupancy_count
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b""", b=building_id)
        meta, buckets = {}, {}
        for r in rows:
            ek = r["entity_key"]
            if ek not in meta:
                meta[ek] = {"room_type": r["room_type"], "area_m2": r["area_m2"],
                            "capacity": _capacity(r["room_type"], r["area_m2"])}
            frac = (r["occupancy_count"] or 0) / meta[ek]["capacity"]
            buckets.setdefault((ek, _daytype(r["timestamp"]), _slot(r["timestamp"])), []).append(frac)
        table = {}
        for key, fracs in buckets.items():
            fracs.sort()
            q1 = fracs[len(fracs) // 4]
            q3 = fracs[3 * len(fracs) // 4]
            table[key] = {"frac": median(fracs), "iqr": q3 - q1,
                          "count": median(fracs) * meta[key[0]]["capacity"]}
        return cls(table, meta)

    def add_event(self, entity_keys, start, end, mult=1.0) -> None:
        self.events.append(Event(set(entity_keys), start, end, mult))

    def expected(self, entity_key, ts) -> dict:
        rec = self.table.get((entity_key, _daytype(ts), _slot(ts)), {"frac": 0.0, "iqr": 0.5, "count": 0})
        frac, iqr = rec["frac"], rec["iqr"]
        for e in self.events:
            if entity_key in e.entity_keys and e.start <= ts < e.end:
                frac *= e.mult
        cap = self.meta.get(entity_key, {}).get("capacity", 1)
        conf = max(0.0, min(1.0, 1 - iqr / (frac + 0.1)))
        return {"frac": round(frac, 3), "count": int(round(frac * cap)), "confidence": round(conf, 3)}
