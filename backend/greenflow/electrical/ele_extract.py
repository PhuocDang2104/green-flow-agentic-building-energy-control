"""Phase 2 — extract electrical assets from the enriched ELE IFC.

Boards (distribution assets, never loads), load points (light fixtures, outlets,
alarms), and cable-carrier assets, each with world-coordinate location, the
reconciled canonical floor, mapped Finnish engineering properties, and the raw
property sets preserved. Electrical rules are honoured: missing power stays
missing (never 0); an explicit 0 is kept but flagged for review in the property
audit; voltage-without-power is recorded as such.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from greenflow.bim.ifc_geometry import building_storeys

from . import canonical as C
from . import config as cfg
from . import ifc_common as ic
from .provenance import Confidence, SourceSystem, ValueClass

SRC = "ELE_enriched.ifc"


def _base(elem, scale: float, fidx: ic.FloorIndex) -> dict[str, Any]:
    typed, raw = ic.canonical_props(elem)
    storey = ic.storey_of(elem)
    floor = fidx.resolve(storey, scale)
    x, y, z = ic.placement_xyz(elem, scale)
    return {
        "ifc_global_id": elem.GlobalId,
        "name": elem.Name or "",
        "ifc_class": elem.is_a(),
        "predefined_type": getattr(elem, "PredefinedType", None) or "",
        "object_type": getattr(elem, "ObjectType", None) or "",
        "storey": getattr(storey, "Name", None) or "",
        "floor_id": floor["floor_id"] if floor else "",
        "floor_name": floor["name"] if floor else "",
        "x": x, "y": y, "z": z,
        "_typed": typed,
        "_raw": raw,
    }


def _g(typed: dict, key: str):
    return typed.get(key)


def _audit_rows(kind: str, gid: str, ifc_class: str, typed: dict) -> list[dict]:
    expect = {
        "board": ["voltage_v", "phase_count", "rated_current_a", "system_code"],
        "lighting": ["voltage_v", "design_power_w", "power_factor", "phase_count", "system_code"],
        "plug": ["voltage_v", "design_power_w", "phase_count", "system_code"],
        "alarm": ["voltage_v", "system_code"],
    }.get(kind, ["system_code"])
    rows = []
    for fld in expect:
        v = typed.get(fld)
        if v is None:
            status = "missing"
        elif fld in ("design_power_w", "rated_current_a") and float(v) == 0.0:
            status = "explicit_zero_placeholder"
        else:
            status = "present"
        rows.append({"ifc_global_id": gid, "ifc_class": ifc_class, "kind": kind,
                     "field": fld, "value": v, "status": status})
    return rows


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    f = ic.open_ifc(cfg.ELE_IFC)
    scale = ic.unit_scale(f)
    fidx = ic.FloorIndex(building_storeys(cfg.ARCH_IFC))

    boards: list[dict] = []
    load_points: list[dict] = []
    cables: list[dict] = []
    audit: list[dict] = []

    # ---- boards ----
    for cls in cfg.BOARD_CLASSES:
        for e in ic.by_type(f, cls):
            b = _base(e, scale, fidx)
            t = b["_typed"]
            audit += _audit_rows("board", b["ifc_global_id"], b["ifc_class"], t)
            boards.append({
                "board_id": C.board_id(e.GlobalId),
                "ifc_global_id": b["ifc_global_id"], "name": b["name"],
                "device_tag": _g(t, "device_tag"), "ifc_class": b["ifc_class"],
                "predefined_type": b["predefined_type"], "object_type": b["object_type"],
                "board_kind": _g(t, "component_general_name") or "DistributionBoard",
                "floor_id": b["floor_id"], "storey": b["storey"],
                "x": b["x"], "y": b["y"], "z": b["z"],
                "voltage_v": _g(t, "voltage_v"), "phase_count": _g(t, "phase_count"),
                "rated_current_a": _g(t, "rated_current_a"), "fuse_rating_a": _g(t, "fuse_rating_a"),
                "power_factor": _g(t, "power_factor"),
                "short_circuit_icw_ka": _g(t, "short_circuit_icw_ka"),
                "short_circuit_ipk_ka": _g(t, "short_circuit_ipk_ka"),
                "system_code": _g(t, "system_code"), "system_name": _g(t, "system_name"),
                "width_mm": _g(t, "width_mm"), "height_mm": _g(t, "height_mm"),
                "depth_mm": _g(t, "depth_mm"),
                "manufacturer": _g(t, "manufacturer"),
                "product_description": _g(t, "product_description"),
                "rating_present": _g(t, "rated_current_a") not in (None, 0.0),
                "source_file": SRC, "source_system": SourceSystem.IFC_ELE,
                "value_class": ValueClass.IFC_DERIVED, "extraction_confidence": Confidence.HIGH,
                "notes": "" if b["floor_id"] else "floor unresolved",
                "raw_properties_json": __import__("json").dumps(b["_raw"], ensure_ascii=False, default=str),
            })

    # ---- load points (lighting / plug / alarm) ----
    def _kind(ifc_class: str) -> str:
        if ifc_class in cfg.LIGHT_CLASSES:
            return "lighting"
        if ifc_class in cfg.OUTLET_CLASSES:
            return "plug"
        if ifc_class in cfg.ALARM_CLASSES:
            return "alarm"
        return "other"

    for cls in sorted(cfg.LOAD_POINT_CLASSES):
        for e in ic.by_type(f, cls):
            b = _base(e, scale, fidx)
            t = b["_typed"]
            kind = _kind(b["ifc_class"])
            power = _g(t, "design_power_w")
            audit += _audit_rows(kind, b["ifc_global_id"], b["ifc_class"], t)
            load_points.append({
                "load_point_id": C.load_point_id(e.GlobalId),
                "ifc_global_id": b["ifc_global_id"], "name": b["name"],
                "device_tag": _g(t, "device_tag"), "ifc_class": b["ifc_class"],
                "load_kind": kind, "category": {"lighting": cfg.CAT_LIGHTS,
                                                "plug": cfg.CAT_EQUIPMENT}.get(kind, "other"),
                "floor_id": b["floor_id"], "storey": b["storey"],
                "x": b["x"], "y": b["y"], "z": b["z"],
                "voltage_v": _g(t, "voltage_v"), "design_power_w": power,
                "design_power_present": power is not None,
                "design_power_is_zero": (power == 0.0),
                "power_factor": _g(t, "power_factor"), "phase_count": _g(t, "phase_count"),
                "luminous_flux_lm": _g(t, "luminous_flux_lm"),
                "system_code": _g(t, "system_code"), "system_name": _g(t, "system_name"),
                "component_main_group": _g(t, "component_main_group"),
                "component_sub_group": _g(t, "component_sub_group"),
                "manufacturer": _g(t, "manufacturer"),
                "product_type_name": _g(t, "product_type_name"),
                "source_file": SRC, "source_system": SourceSystem.IFC_ELE,
                "value_class": ValueClass.IFC_DERIVED, "extraction_confidence": Confidence.HIGH,
                "notes": "voltage present, design power missing"
                         if (_g(t, "voltage_v") is not None and power is None) else "",
                "raw_properties_json": __import__("json").dumps(b["_raw"], ensure_ascii=False, default=str),
            })

    # ---- cable assets ----
    for cls in sorted(cfg.CABLE_CLASSES):
        for e in ic.by_type(f, cls):
            b = _base(e, scale, fidx)
            t = b["_typed"]
            cables.append({
                "cable_id": C.cable_id(e.GlobalId),
                "ifc_global_id": b["ifc_global_id"], "name": b["name"],
                "ifc_class": b["ifc_class"], "floor_id": b["floor_id"], "storey": b["storey"],
                "x": b["x"], "y": b["y"], "z": b["z"],
                "size_label": _g(t, "size_label"), "width_mm": _g(t, "width_mm"),
                "height_mm": _g(t, "height_mm"), "length_mm": _g(t, "length_mm"),
                "system_code": _g(t, "system_code"), "system_name": _g(t, "system_name"),
                "source_file": SRC, "source_system": SourceSystem.IFC_ELE,
                "value_class": ValueClass.IFC_DERIVED, "extraction_confidence": Confidence.HIGH,
                "notes": "", "raw_properties_json":
                    __import__("json").dumps(b["_raw"], ensure_ascii=False, default=str),
            })

    C.write_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv", boards)
    C.write_rows_csv(cfg.OUT_ELEC / "electrical_load_points.csv", load_points)
    C.write_rows_csv(cfg.OUT_ELEC / "electrical_cable_assets.csv", cables)
    C.write_rows_csv(cfg.OUT_ELEC / "electrical_asset_property_audit.csv", audit)

    return {"boards": len(boards), "load_points": len(load_points),
            "cable_assets": len(cables), "property_audit_rows": len(audit)}


if __name__ == "__main__":
    print(run())
