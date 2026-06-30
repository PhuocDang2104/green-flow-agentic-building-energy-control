"""Building Semantic Agent: graph + state + metadata quality + abnormal findings.

The foundation agent (blueprint §4.2). There is intentionally no separate
Anomaly Agent — all abnormalities are derived here from semantic graph +
current state + schedule context.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...replayclock import anchor
from ..state import GreenFlowState
from ..tools import db_tool, graph_tool

TZ = timezone(timedelta(hours=7))
WORK_START, WORK_END = 7, 19


def run(state: GreenFlowState) -> dict:
    building_id = state["building_id"]
    summary = db_tool.get_building_summary(building_id)
    floors = db_tool.get_floors(building_id)
    zones = db_tool.get_zones(building_id)
    zone_state = db_tool.get_latest_zone_state(building_id)
    device_state = db_tool.get_latest_device_state(building_id)
    equipment_map = graph_tool.get_zone_equipment_map(building_id)
    missing = graph_tool.get_missing_metadata(building_id)
    weather = db_tool.get_latest_weather()

    findings = _abnormal_findings(zones, zone_state, equipment_map)

    controllable = [d for d in db_tool.get_devices(building_id) if d["controllable"]]
    zone_types = {z["entity_key"]: z["room_type"] for z in zones}

    semantic_context = {
        "building_name": summary.get("name"),
        "floor_count": summary.get("floor_count"),
        "zone_count": len(zones),
        "physical_zone_count": summary.get("zone_count"),
        "energy_zone_count": summary.get("energy_zone_count"),
        "device_count": summary.get("device_count"),
        "total_area_m2": summary.get("total_area_m2"),
        "zone_types": zone_types,
        "controllable_device_keys": [d["entity_key"] for d in controllable],
        "data_quality_issues": len(missing),
        "abnormal_count": len(findings),
    }

    return {
        "building_summary": summary,
        "floors": floors,
        "zones": zones,
        "latest_zone_state": zone_state,
        "latest_device_state": device_state,
        "zone_equipment_map": equipment_map,
        "weather_state": weather,
        "semantic_context": semantic_context,
        "abnormal_findings": findings,
        "missing_metadata": missing,
    }


def _abnormal_findings(zones: list[dict], zone_state: dict[str, dict],
                       equipment_map: dict) -> list[dict]:
    findings: list[dict] = []
    now_hour = anchor().hour
    in_work_hours = WORK_START <= now_hour < WORK_END

    for z in zones:
        st = zone_state.get(z["entity_key"])
        if not st:
            findings.append({
                "finding_type": "missing_telemetry", "severity": "watch",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": f"No telemetry for {z['name']}",
            })
            continue
        occupied = (st.get("occupancy_count") or 0) > 0
        lighting = st.get("lighting_power_kw") or 0.0
        hvac = st.get("hvac_power_kw") or 0.0
        nominal_light = z.get("area_m2", 0) * 11 / 1000.0

        if st.get("anomaly_label"):
            findings.append({
                "finding_type": st["anomaly_label"], "severity": "high",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": _anomaly_text(st["anomaly_label"], z["name"], st),
                "metrics": {"lighting_kw": lighting, "hvac_kw": hvac,
                            "occupancy": st.get("occupancy_count")},
            })
        elif not occupied and lighting > max(0.15, nominal_light * 0.3):
            findings.append({
                "finding_type": "lighting_on_empty_zone", "severity": "watch",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": f"{z['name']} is empty but lighting draws {lighting:.2f} kW",
                "metrics": {"lighting_kw": lighting},
            })
        elif not occupied and hvac > 0.3 and not in_work_hours:
            findings.append({
                "finding_type": "hvac_on_empty_zone", "severity": "watch",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": f"HVAC running ({hvac:.2f} kW) in empty {z['name']} outside work hours",
                "metrics": {"hvac_kw": hvac},
            })
        if st.get("comfort_risk") == "high":
            findings.append({
                "finding_type": "comfort_risk_high", "severity": "high",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": f"{z['name']} at {st.get('temperature_c')}degC exceeds comfort "
                          f"threshold while occupied",
                "metrics": {"temperature_c": st.get("temperature_c")},
            })
        if not equipment_map.get(z["entity_key"]):
            findings.append({
                "finding_type": "zone_unmapped_devices", "severity": "info",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": f"{z['name']} has no device mapping in the semantic graph",
            })
        occ_conf = st.get("occupancy_confidence")
        if occ_conf is not None and occ_conf < 0.7:
            findings.append({
                "finding_type": "occupancy_confidence_low", "severity": "info",
                "zone_key": z["entity_key"], "zone_name": z["name"],
                "detail": f"Occupancy confidence {occ_conf:.2f} below 0.7 in {z['name']}",
            })
    return findings


def _anomaly_text(label: str, zone_name: str, st: dict) -> str:
    if label == "lighting_on_empty_zone":
        return (f"{zone_name} shows {st.get('lighting_power_kw', 0):.2f} kW lighting "
                f"with zero occupancy")
    if label == "hvac_on_empty_zone":
        return (f"{zone_name} shows {st.get('hvac_power_kw', 0):.2f} kW HVAC with "
                f"zero occupancy")
    return f"Anomaly '{label}' detected in {zone_name}"
