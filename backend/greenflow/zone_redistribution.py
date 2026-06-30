"""Aggregate-zone child mapping and redistribution helpers.

The redistribution layer is deliberately conservative:

- only explicit ``aggregate_context`` zones are redistributed;
- child candidates must be non-aggregate occupied/usable spaces on the same
  storey/floor;
- weights are area-based and sum to 1 per aggregate;
- the original raw aggregate rows can be kept for audit, or excluded/materialised
  through a caller-controlled feature flag.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable

from .energy_scope import AGGREGATE, classify_energy_scope
from .zone_naming import zone_display_name_from_mapping


SCOPE_CHILD_WEIGHTS_CSV = "zone_scope_child_weights.csv"
SCOPE_REDISTRIBUTION_REPORT_JSON = "zone_scope_redistribution_report.json"

_EXCLUDED_CHILD_ROOM_TYPES = {
    "gross_area_placeholder",
    "technical_core",
    "unknown",
}
_OCCUPIED_CHILD_ROOM_TYPES = {
    "office",
    "open_office",
    "meeting_room",
    "business_space",
    "workspace",
    "amenity",
    "lobby",
    "circulation",
}
_CONTEXT_PATTERN = re.compile(
    r"(?:CHASE|SHAFT|TURNING\s+FREE\s+SPACE|VENT|GFA|NETAREA|GROSS|VOLUME\s*/)",
    re.IGNORECASE,
)


def _f(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean(value: object) -> str:
    return str(value or "").strip()


def _zone_id(row: dict) -> str:
    return _clean(row.get("zone_id") or row.get("entity_key") or row.get("id"))


def _scope(row: dict) -> str:
    explicit = _clean(row.get("energy_scope"))
    if explicit:
        return explicit
    label = " ".join(
        _clean(row.get(k)) for k in ("long_name", "number", "name", "room_name")
    )
    return classify_energy_scope(
        label,
        area_m2=_f(row.get("area_m2")),
        volume_m3=_f(row.get("volume_m3")),
    ).scope


def _scope_reason(row: dict) -> str:
    explicit = _clean(row.get("scope_reason"))
    if explicit:
        return explicit
    label = " ".join(
        _clean(row.get(k)) for k in ("long_name", "number", "name", "room_name")
    )
    return classify_energy_scope(
        label,
        area_m2=_f(row.get("area_m2")),
        volume_m3=_f(row.get("volume_m3")),
    ).reason


def _storey_key(row: dict) -> str:
    return (_clean(row.get("storey")) or _clean(row.get("floor_name")) or _clean(row.get("floor_id"))).lower()


def _floor_key(row: dict) -> str:
    return (_clean(row.get("floor_id")) or _clean(row.get("floor_name")) or _clean(row.get("storey"))).lower()


def _label(row: dict) -> str:
    return " ".join(
        _clean(row.get(k)) for k in ("long_name", "number", "name", "room_name")
    )


def _is_building_wide_office_aggregate(row: dict) -> bool:
    label = _label(row).upper()
    storey = _storey_key(row)
    return "VOLUME / OFFICE" in label or (
        "OFFICE" in label and storey in {"foundation", "sea level", "floor_foundation"}
    )


def _building_wide_children(candidates: list[dict]) -> list[dict]:
    out = []
    for child in candidates:
        storey = _storey_key(child)
        if storey in {"basement", "foundation", "sea level"}:
            continue
        room_type = _clean(child.get("room_type")).lower()
        if room_type in _OCCUPIED_CHILD_ROOM_TYPES:
            out.append(child)
    return out


def is_child_candidate(row: dict) -> bool:
    if _scope(row) == AGGREGATE:
        return False
    if _f(row.get("area_m2")) <= 0:
        return False
    room_type = _clean(row.get("room_type")).lower()
    if room_type in _EXCLUDED_CHILD_ROOM_TYPES:
        return False
    reason = _scope_reason(row).lower()
    if "context_space_name" in reason or "unusual_height" in reason:
        return False
    return not _CONTEXT_PATTERN.search(_label(row))


@dataclass(frozen=True)
class RedistributionSummary:
    aggregate_count: int
    mapped_aggregate_count: int
    child_count: int
    weight_rows: int
    unmapped_aggregate_ids: list[str]

    def to_dict(self) -> dict:
        return {
            "aggregate_count": self.aggregate_count,
            "mapped_aggregate_count": self.mapped_aggregate_count,
            "child_count": self.child_count,
            "weight_rows": self.weight_rows,
            "unmapped_aggregate_ids": self.unmapped_aggregate_ids,
        }


def build_child_weights(zone_rows: Iterable[dict]) -> tuple[list[dict], RedistributionSummary]:
    zones = [dict(r) for r in zone_rows]
    aggregates = [z for z in zones if _scope(z) == AGGREGATE]
    candidates = [z for z in zones if is_child_candidate(z)]

    by_storey: dict[str, list[dict]] = defaultdict(list)
    by_floor: dict[str, list[dict]] = defaultdict(list)
    for child in candidates:
        by_storey[_storey_key(child)].append(child)
        by_floor[_floor_key(child)].append(child)

    rows: list[dict] = []
    unmapped: list[str] = []
    for agg in aggregates:
        children = by_storey.get(_storey_key(agg)) or by_floor.get(_floor_key(agg)) or []
        method = "same_storey_area_weight" if by_storey.get(_storey_key(agg)) else "same_floor_area_weight"
        confidence = "medium" if method == "same_storey_area_weight" else "low"
        if not children and _is_building_wide_office_aggregate(agg):
            children = _building_wide_children(candidates)
            method = "building_wide_occupied_area_weight"
            confidence = "low"
        # Never map an aggregate to itself even if source data is malformed.
        children = [c for c in children if _zone_id(c) != _zone_id(agg)]
        total_area = sum(_f(c.get("area_m2")) for c in children)
        if not children or total_area <= 0:
            unmapped.append(_zone_id(agg))
            continue
        norm: list[tuple[dict, float]] = [
            (child, round(_f(child.get("area_m2")) / total_area, 8))
            for child in children
        ]
        residual = round(1.0 - sum(w for _, w in norm), 8)
        if norm:
            idx = max(range(len(norm)), key=lambda i: norm[i][1])
            child, weight = norm[idx]
            norm[idx] = (child, round(weight + residual, 8))
        for child, weight in norm:
            rows.append({
                "aggregate_zone_id": _zone_id(agg),
                "aggregate_name": zone_display_name_from_mapping(agg),
                "aggregate_floor_id": agg.get("floor_id") or "",
                "aggregate_storey": agg.get("storey") or agg.get("floor_name") or "",
                "aggregate_area_m2": round(_f(agg.get("area_m2")), 3),
                "aggregate_scope_reason": _scope_reason(agg),
                "child_zone_id": _zone_id(child),
                "child_name": zone_display_name_from_mapping(child),
                "child_floor_id": child.get("floor_id") or "",
                "child_storey": child.get("storey") or child.get("floor_name") or "",
                "child_room_type": child.get("room_type") or "",
                "child_area_m2": round(_f(child.get("area_m2")), 3),
                "weight": weight,
                "method": method,
                "confidence": confidence,
                "reason": "area share among non-aggregate occupied child candidates on same location",
            })

    summary = RedistributionSummary(
        aggregate_count=len(aggregates),
        mapped_aggregate_count=len({_clean(r["aggregate_zone_id"]) for r in rows}),
        child_count=len({_clean(r["child_zone_id"]) for r in rows}),
        weight_rows=len(rows),
        unmapped_aggregate_ids=unmapped,
    )
    return rows, summary


def weights_by_aggregate(rows: Iterable[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        out[_clean(row.get("aggregate_zone_id"))].append(row)
    return dict(out)
