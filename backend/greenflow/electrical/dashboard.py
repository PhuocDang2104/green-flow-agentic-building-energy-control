"""Phase 10 — 3D dashboard manifest + view payload builders.

`run()` writes `dashboard_electrical_manifest.json` (layers, metrics, colour
scales, entity types, click actions, API endpoints, badges). The `build_*`
functions assemble the per-view payloads and are reused by the FastAPI router.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from . import canonical as C
from . import config as cfg
from ..energy_scope import dedup_enabled

MANIFEST = cfg.OUT_ELEC / "dashboard_electrical_manifest.json"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _boards():
    return {b["board_id"]: b for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")}


@lru_cache(maxsize=1)
def _annual():
    return {a["board_id"]: a for a in C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")}


@lru_cache(maxsize=1)
def _alloc():
    return C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv")


@lru_cache(maxsize=1)
def _zones():
    return {z["zone_id"]: z for z in C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")}


def build_building_overview() -> dict:
    ann = _annual()
    recon = C.read_rows_csv(cfg.OUT_ELEC / "energy_reconciliation_by_board_category.csv")
    ranking = sorted(({"board_id": a["board_id"], "device_tag": a.get("device_tag"),
                       "floor_id": a.get("floor_id"), "peak_total_kw": _f(a.get("peak_total_kw")),
                       "total_kwh": _f(a.get("total_kwh")), "overload_status": a.get("overload_status")}
                      for a in ann.values() if a["board_id"] != cfg.UNMAPPED_BOARD_ID),
                     key=lambda r: -(r["peak_total_kw"] or 0))
    split = {r["category"]: _f(r["zone_allocated_kwh"]) for r in recon}
    raw_total = sum(_f(r.get("raw_zone_kwh")) or 0 for r in recon)
    deduped_total = sum(
        _f(r.get("deduped_zone_kwh", r.get("zone_allocated_kwh"))) or 0 for r in recon
    )
    try:
        report = __import__("json").loads((cfg.OUT_ELEC / "electrical_validation_report.json").read_text("utf-8"))
        vsummary = report.get("summary", {})
    except Exception:
        vsummary = {}
    return {"building": cfg.BUILDING_NAME, "dataset_key": cfg.DATASET_KEY,
            "scenario_id": cfg.SCENARIO_ID, "energy_split_kwh": split,
            "raw_total_kwh": round(raw_total, 1), "deduped_total_kwh": round(deduped_total, 1),
            "excluded_aggregate_kwh": round(raw_total - deduped_total, 1),
            "energy_scope_mode": "dedup" if dedup_enabled() else "audit",
            "board_demand_ranking": ranking, "validation_summary": vsummary,
            "boards": len(_boards()), "zones": len(_zones())}


def build_floor_view(floor_id: str) -> dict:
    boards = [b for b in _boards().values() if b.get("floor_id") == floor_id]
    ann = _annual()
    zone_set = {z["zone_id"] for z in _zones().values() if z.get("floor_id") == floor_id}
    floor_kwh = 0.0
    for a in _alloc():
        if a["zone_id"] in zone_set:
            pass  # floor demand summed from board side below
    bview = [{"board_id": b["board_id"], "device_tag": b.get("device_tag"), "system_code": b.get("system_code"),
              "peak_total_kw": _f((ann.get(b["board_id"]) or {}).get("peak_total_kw")),
              "total_kwh": _f((ann.get(b["board_id"]) or {}).get("total_kwh")),
              "overload_status": (ann.get(b["board_id"]) or {}).get("overload_status"),
              "coordinates": [_f(b.get("x")), _f(b.get("y")), _f(b.get("z"))]} for b in boards]
    floor_kwh = sum((v["total_kwh"] or 0) for v in bview)
    return {"floor_id": floor_id, "boards": bview, "zone_count": len(zone_set),
            "estimated_floor_kwh": round(floor_kwh, 1)}


def build_zone_view(zone_id: str) -> dict:
    z = _zones().get(zone_id, {})
    served = [{"board_id": a["board_id"], "category": a["load_category"], "weight": _f(a["weight"]),
               "confidence": a["mapping_confidence"], "method": a["mapping_method"]}
              for a in _alloc() if a["zone_id"] == zone_id]
    return {"zone_id": zone_id, "eplus_zone_name": z.get("eplus_zone_name"),
            "room_type": z.get("room_type"), "floor_id": z.get("floor_id"), "area_m2": z.get("area_m2"),
            "energy_scope": z.get("energy_scope"),
            "counts_toward_energy": z.get("counts_toward_energy"),
            "scope_reason": z.get("scope_reason"),
            "assigned_boards": served, "energy_value_class": "energyplus_simulated",
            "note": "lights/equipment/HVAC kW available in the gold zone timeseries"}


def build_board_view(board_id: str) -> dict:
    b = _boards().get(board_id, {})
    a = _annual().get(board_id, {})
    served = defaultdict(list)
    for al in _alloc():
        if al["board_id"] == board_id:
            served[al["load_category"]].append({"zone_id": al["zone_id"], "weight": _f(al["weight"]),
                                                 "confidence": al["mapping_confidence"]})
    return {"board_id": board_id, "device_tag": b.get("device_tag"), "floor_id": b.get("floor_id"),
            "voltage_v": _f(b.get("voltage_v")), "phase_count": _f(b.get("phase_count")),
            "rated_current_a": _f(b.get("rated_current_a")), "system_code": b.get("system_code"),
            "system_name": b.get("system_name"),
            "estimated": {k: a.get(k) for k in ("total_kwh", "lights_kwh", "equipment_kwh", "hvac_kwh",
                          "peak_total_kw", "peak_timestamp", "estimated_peak_current_a",
                          "loading_pct", "overload_status", "pf_source")},
            "served_zones": served, "value_class": "spatially_inferred",
            "caveats": ["board demand = EnergyPlus-simulated zone energy × inferred allocation",
                        "overload reported only with a real rated current"]}


def build_graph_neighbors(entity_id: str) -> dict:
    edges = C.read_rows_csv(cfg.OUT_KG / "graph_edges.csv")
    out = [e for e in edges if e["source_node_id"] == entity_id or e["target_node_id"] == entity_id]
    return {"entity_id": entity_id, "neighbors": out[:200], "count": len(out)}


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    manifest = {
        "building": cfg.BUILDING_NAME, "version": 2,
        "dataset_key": cfg.DATASET_KEY, "scenario_id": cfg.SCENARIO_ID,
        "layers": [
            {"id": "boards", "label": "Electrical boards", "entity_type": "ElectricalBoard",
             "geometry": "point", "default_visible": True},
            {"id": "load_points", "label": "Lights & outlets", "entity_type": "LoadPoint", "geometry": "point"},
            {"id": "cable_trays", "label": "Cable trays", "entity_type": "CableTray", "geometry": "line"},
            {"id": "zones", "label": "Zones (energy)", "entity_type": "ThermalZone", "geometry": "volume"},
            {"id": "hvac", "label": "HVAC devices", "entity_type": "HVACDevice", "geometry": "point"},
        ],
        "metrics": [
            {"id": "board_peak_kw", "label": "Board peak demand", "unit": "kW", "source": "board_annual_summary"},
            {"id": "board_total_kwh", "label": "Board annual energy", "unit": "kWh"},
            {"id": "loading_pct", "label": "Loading", "unit": "%", "requires": "rated_current_a"},
            {"id": "zone_total_kw", "label": "Zone electricity", "unit": "kW", "source": "gold_zone_timeseries"},
        ],
        "color_scales": {
            "loading_pct": [{"stop": 0, "color": "#2ecc71"}, {"stop": 80, "color": "#f1c40f"},
                            {"stop": 100, "color": "#e74c3c"}],
            "overload_status": {"normal": "#2ecc71", "warning": "#f1c40f", "overload": "#e74c3c",
                                "rating_missing": "#95a5a6", "unmapped": "#7f8c8d"},
        },
        "entity_types": ["Building", "Floor", "ThermalZone", "EnergyPlusZone", "ElectricalBoard",
                         "Circuit", "LightFixture", "Outlet", "Alarm", "CableTray", "HVACDevice", "Meter"],
        "click_actions": {
            "ElectricalBoard": "GET /api/electrical/boards/{id}",
            "ThermalZone": "GET /api/electrical/zones/{id}/electrical",
            "Floor": "GET /api/electrical/floors/{id}",
            "any": "GET /api/graph/entities/{id}/neighbors",
        },
        "api_endpoints": [
            "GET /api/electrical/boards", "GET /api/electrical/boards/{board_id}",
            "GET /api/electrical/boards/{board_id}/timeseries",
            "GET /api/electrical/boards/{board_id}/served-zones",
            "GET /api/electrical/zones/{zone_id}/electrical",
            "GET /api/electrical/load-points/{load_point_id}",
            "GET /api/electrical/floors/{floor_id}", "GET /api/electrical/overview",
            "GET /api/graph/entities/{entity_id}/neighbors",
            "GET /api/graph/entities/{entity_id}/evidence", "GET /api/graph/rag/answer",
        ],
        "badges": {
            "warning": {"field": "overload_status", "values": ["warning", "overload"]},
            "confidence": {"field": "mapping_confidence", "values": ["low", "manual_review"]},
            "manual_review": {"source": "manual_review_items.csv"},
            "rating_missing": {"field": "overload_status", "values": ["rating_missing"]},
        },
        "views": ["building_overview", "floor_electrical_view", "zone_energy_view", "board_view",
                  "circuit_view", "graph_rag_view"],
    }
    C.write_json(MANIFEST, manifest)
    return {"layers": len(manifest["layers"]), "endpoints": len(manifest["api_endpoints"])}


if __name__ == "__main__":
    print(run())
