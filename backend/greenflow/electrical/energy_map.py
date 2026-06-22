"""Phase 4 — parse the IDF (names only) and map zone load categories to the gold
EnergyPlus output columns. We never re-simulate: the patched
``final_zone_device_power_timeseries`` is the simulated source of truth, and the
IDF is read only to record object names and provenance.
"""
from __future__ import annotations

import re
from collections import Counter

from . import canonical as C
from . import config as cfg
from . import gold
from .provenance import SourceSystem, ValueClass

TARGET_CLASSES = [
    "Zone", "Lights", "ElectricEquipment", "People",
    "ZoneHVAC:PackagedTerminalAirConditioner", "ZoneHVAC:EquipmentList",
    "Fan:OnOff", "Fan:SystemModel", "Fan:ConstantVolume",
    "Coil:Cooling:DX:SingleSpeed", "Coil:Heating:Electric", "Coil:Heating:Fuel",
    "Schedule:Compact", "ThermostatSetpoint:DualSetpoint",
    "Timestep", "Output:Variable", "Output:Meter", "RunPeriod",
]


def _objects(text: str):
    """Yield (class_name, fields[]) for every IDF object (comments stripped)."""
    text = re.sub(r"!.*", "", text)            # strip line comments
    for chunk in text.split(";"):
        fields = [t.strip() for t in chunk.split(",")]
        fields = [f for f in fields if f != ""]
        if not fields:
            continue
        yield fields[0], fields


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    text = cfg.IDF_FILE.read_text(encoding="utf-8", errors="ignore")
    eplus_zones = set(gold.zone_eplus_map().values())

    class_counts: Counter = Counter()
    per_zone: dict[str, dict] = {z: {"eplus_zone_name": z} for z in eplus_zones}
    field_for = {
        "Lights": "lights_object_name",
        "ElectricEquipment": "electric_equipment_object_name",
        "ZoneHVAC:PackagedTerminalAirConditioner": "ptac_object_name",
        "Fan:OnOff": "fan_object_name", "Fan:SystemModel": "fan_object_name",
        "Fan:ConstantVolume": "fan_object_name",
        "Coil:Cooling:DX:SingleSpeed": "cooling_coil_object_name",
        "Coil:Heating:Electric": "heating_coil_object_name",
        "Coil:Heating:Fuel": "heating_coil_object_name",
    }
    timestep = None
    for cls, fields in _objects(text):
        class_counts[cls] += 1
        if cls == "Timestep" and len(fields) > 1:
            timestep = fields[1]
        col = field_for.get(cls)
        if col:
            name = fields[1] if len(fields) > 1 else ""
            blob = ",".join(fields)
            for z in eplus_zones:
                if z and z in blob:
                    per_zone.setdefault(z, {"eplus_zone_name": z})[col] = name
                    break

    idf_rows = sorted(per_zone.values(), key=lambda r: r["eplus_zone_name"])
    C.write_rows_csv(cfg.OUT_ENERGY / "idf_energy_mapping.csv", idf_rows,
                     fieldnames=["eplus_zone_name", "lights_object_name",
                                 "electric_equipment_object_name", "ptac_object_name",
                                 "fan_object_name", "cooling_coil_object_name",
                                 "heating_coil_object_name"])

    # ---- output column mapping (gold table is the energy source) ----
    col_rows = []
    cat_src_flag = {cfg.CAT_LIGHTS: "lights_electricity_source",
                    cfg.CAT_EQUIPMENT: "equipment_electricity_source",
                    cfg.CAT_HVAC: "hvac_electricity_source"}
    for cat, (kw, kwh) in cfg.ZONE_CAT_COLUMNS.items():
        col_rows.append({"target_metric": f"zone_{cat}_kw", "source_table": "final_zone_device_power_timeseries",
                         "source_column": kw, "unit": "kW", "value_class": ValueClass.ENERGYPLUS_SIMULATED,
                         "source_flag_column": cat_src_flag[cat], "key_columns": "zone_id,timestep_index",
                         "notes": f"per-zone {cat} electricity rate"})
        col_rows.append({"target_metric": f"zone_{cat}_kwh_interval", "source_table": "final_zone_device_power_timeseries",
                         "source_column": kwh, "unit": "kWh", "value_class": ValueClass.ENERGYPLUS_SIMULATED,
                         "source_flag_column": cat_src_flag[cat], "key_columns": "zone_id,timestep_index",
                         "notes": f"per-zone {cat} energy over 0.5 h interval"})
    col_rows += [
        {"target_metric": "final_total_zone_electricity_kw", "source_table": "final_zone_device_power_timeseries",
         "source_column": "final_total_zone_electricity_kw", "unit": "kW",
         "value_class": ValueClass.ENERGYPLUS_SIMULATED, "source_flag_column": "",
         "key_columns": "zone_id,timestep_index", "notes": "validation only; not allocated to boards"},
        {"target_metric": "building_meter_total_kwh", "source_table": "final_building_meter_timeseries",
         "source_column": "value_kwh_interval_if_energy", "unit": "kWh",
         "value_class": ValueClass.ENERGYPLUS_SIMULATED, "source_flag_column": "meter_name",
         "key_columns": "meter_name,timestep_index", "notes": f"meter {cfg.METER_TOTAL}"},
    ]
    for cat, meter in cfg.METER_FOR_CATEGORY.items():
        col_rows.append({"target_metric": f"building_meter_{cat}_kwh", "source_table": "final_building_meter_timeseries",
                         "source_column": "value_kwh_interval_if_energy", "unit": "kWh",
                         "value_class": ValueClass.ENERGYPLUS_SIMULATED, "source_flag_column": "meter_name",
                         "key_columns": "meter_name,timestep_index", "notes": f"meter {meter}"})
    C.write_rows_csv(cfg.OUT_ENERGY / "energy_output_column_mapping.csv", col_rows)

    # ---- audit ----
    meters = gold.meter_names()
    top = "\n".join(f"- `{c}`: {n}" for c, n in class_counts.most_common(20))
    audit = f"""# Energy Source Audit

**Energy source of truth:** the existing patched dataset under `data/final`
(`final_zone_device_power_timeseries`), scenario `{cfg.SCENARIO_ID}`,
30-minute timestep ({cfg.TIMESTEP_HOURS} h), full-year 2025. EnergyPlus is **not**
re-run; the IDF (`{cfg.IDF_FILE.name}`) is parsed for object names + provenance only
and is left byte-stable. No `eplusout.sql` is present.

## IDF object inventory (top classes)
- IDF Timestep: `{timestep}` per hour
{top}

## Per-category source columns (zone-level, EnergyPlus simulated)
- lights → `lights_electricity_kw` / `lights_electricity_kwh_interval`
- equipment (plug) → `equipment_electricity_kw` / `equipment_electricity_kwh_interval`
- hvac → `final_hvac_electricity_kw` / `final_hvac_electricity_kwh_interval`
  (composed from fan + cooling/heating coil + PTAC columns by the postprocess)
- total (validation only) → `final_total_zone_electricity_kw`

Zone↔EnergyPlus identity is already carried in the gold table
(`zone_id` ↔ `eplus_zone_name`); {len(eplus_zones)} zones.

## Building meters (validation)
{chr(10).join('- `' + m + '`' for m in meters)}
"""
    C.write_text(cfg.OUT_ENERGY / "energy_source_audit.md", audit)
    return {"idf_classes": len(class_counts), "idf_objects": sum(class_counts.values()),
            "zones_mapped": len(idf_rows), "column_mappings": len(col_rows)}


if __name__ == "__main__":
    print(run())
