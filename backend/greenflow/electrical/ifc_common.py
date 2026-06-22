"""Shared IFC reading helpers (placement centroid, Finnish pset mapping, and
storey→canonical-floor reconciliation by elevation).

The enriched discipline models (ELE/HVAC) name storeys differently from the ARCH
spatial master (e.g. ELE ``01_Kerros`` ↔ ARCH ``Level_01``) but their elevations
match, so floors are reconciled by elevation against the ARCH storey list.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.element as ie
import ifcopenshell.util.placement as ip
import ifcopenshell.util.unit as iu

from . import canonical as C
from . import config as cfg


def open_ifc(path: str | Path):
    return ifcopenshell.open(str(path))


def by_type(f, cls: str) -> list:
    """f.by_type that tolerates classes absent from the file's IFC schema."""
    try:
        return f.by_type(cls)
    except RuntimeError:
        return []


def unit_scale(f) -> float:
    try:
        return float(iu.calculate_unit_scale(f))
    except Exception:
        return 1.0


def placement_xyz(elem, scale: float) -> tuple[float | None, float | None, float | None]:
    pl = getattr(elem, "ObjectPlacement", None)
    if pl is None:
        return (None, None, None)
    try:
        m = ip.get_local_placement(pl)
        return (round(float(m[0][3]) * scale, 3),
                round(float(m[1][3]) * scale, 3),
                round(float(m[2][3]) * scale, 3))
    except Exception:
        return (None, None, None)


def storey_of(elem):
    """Walk the spatial containment up to the IfcBuildingStorey."""
    try:
        cont = ie.get_container(elem)
    except Exception:
        cont = None
    guard = 0
    while cont is not None and not cont.is_a("IfcBuildingStorey") and guard < 5:
        nxt = None
        try:
            nxt = ie.get_container(cont) or (ie.get_aggregate(cont) if hasattr(ie, "get_aggregate") else None)
        except Exception:
            nxt = None
        cont = nxt
        guard += 1
    return cont if (cont is not None and cont.is_a("IfcBuildingStorey")) else None


def canonical_props(elem) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (canonical typed props, raw psets) for an IFC element."""
    raw = ie.get_psets(elem)
    typed: dict[str, Any] = {}
    for pset_name, vals in raw.items():
        for k, v in vals.items():
            if k == "id":
                continue
            mapped = cfg.FINNISH_PSET_MAP.get(k)
            if mapped:
                key, caster = mapped
                cv = caster(v)
                if cv is not None and key not in typed:
                    typed[key] = cv
    return typed, raw


class FloorIndex:
    """Canonical floors from the ARCH storey list; resolves any storey to a floor
    by exact name or nearest elevation."""

    def __init__(self, arch_storeys: list[dict]):
        self.floors: list[dict] = []
        for s in arch_storeys:
            name = s.get("name") or ""
            self.floors.append({
                "floor_id": C.floor_id(name),
                "name": name,
                "floor_index": s.get("floor_index"),
                "elevation_m": float(s.get("elevation_m") or 0.0),
            })
        self._by_name = {f["name"]: f for f in self.floors}

    def by_name(self, name: str) -> dict | None:
        return self._by_name.get(name)

    def by_elevation(self, elev_m: float, tol: float = 0.75) -> dict | None:
        if elev_m is None:
            return None
        best, bestd = None, 1e18
        for f in self.floors:
            d = abs(f["elevation_m"] - elev_m)
            if d < bestd:
                best, bestd = f, d
        return best if (best is not None and bestd <= tol) else (best if bestd <= 5.0 else None)

    def resolve(self, storey, scale: float) -> dict | None:
        """Resolve an IfcBuildingStorey (any discipline) to a canonical floor."""
        if storey is None:
            return None
        f = self.by_name(getattr(storey, "Name", "") or "")
        if f:
            return f
        elev = getattr(storey, "Elevation", None)
        if elev is not None:
            return self.by_elevation(float(elev) * scale)
        return None
