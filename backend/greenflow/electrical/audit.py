"""Phase 1 — repository audit & source inventory.

Inventories the IFC files, the gold Parquet/DuckDB tables, the final docs, and
which sources carry boards/lights/outlets/cable-trays/spaces — so the rest of the
pipeline (and a reviewer) knows exactly what evidence exists.
"""
from __future__ import annotations

from collections import Counter

from . import canonical as C
from . import config as cfg
from . import gold
from . import ifc_common as ic


def _ele_counts() -> dict:
    f = ic.open_ifc(cfg.ELE_IFC)
    cnt = Counter(p.is_a() for p in f.by_type("IfcProduct"))
    return dict(cnt)


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    ele = _ele_counts()
    parquet_grains = sorted(p.name for p in cfg.PARQUET_ROOT.iterdir() if p.is_dir())
    meters = gold.meter_names()
    zones = len(gold.zone_eplus_map())
    xeokit_map = (cfg.ROOT / "web" / "public" / "assets" / "buildings" / cfg.BUILDING_KEY
                  / "mapping" / "xeokit_object_map.json")

    inv = {
        "building": cfg.BUILDING_NAME,
        "ifc_files": {
            "ARCH": {"path": str(cfg.ARCH_IFC.relative_to(cfg.ROOT)),
                     "exists": cfg.ARCH_IFC.exists(), "role": "spatial master (storeys, spaces)"},
            "ELE": {"path": str(cfg.ELE_IFC.relative_to(cfg.ROOT)), "exists": cfg.ELE_IFC.exists(),
                    "schema": "IFC4", "product_counts": ele,
                    "has_boards": ele.get("IfcElectricDistributionBoard", 0) > 0,
                    "has_lights": ele.get("IfcLightFixture", 0) > 0,
                    "has_outlets": ele.get("IfcOutlet", 0) > 0,
                    "has_cable_trays": (ele.get("IfcCableCarrierSegment", 0)
                                        + ele.get("IfcCableCarrierFitting", 0)) > 0,
                    "property_language": "Finnish (Granlund/Simplebim FI_* property sets)"},
            "HVAC": {"path": str(cfg.HVAC_IFC.relative_to(cfg.ROOT)), "exists": cfg.HVAC_IFC.exists(),
                     "role": "HVAC device graph / serving relationships"},
            "STRUCT": {"path": str(cfg.STRUCT_IFC.relative_to(cfg.ROOT)),
                       "exists": cfg.STRUCT_IFC.exists(), "role": "structural context"},
        },
        "idf": {"path": str(cfg.IDF_FILE.relative_to(cfg.ROOT)), "exists": cfg.IDF_FILE.exists(),
                "note": "zone-level EnergyPlus analytical model (kept byte-stable)"},
        "gold_dataset": {
            "duckdb": {"path": str(cfg.DUCKDB_FILE.name), "exists": cfg.DUCKDB_FILE.exists()},
            "parquet_grains": parquet_grains,
            "zone_timeseries": "final_zone_device_power_timeseries (best for board allocation)",
            "zone_count": zones, "scenario_id": cfg.SCENARIO_ID, "timestep_hours": cfg.TIMESTEP_HOURS,
            "building_meters": meters, "eplusout_sql_present": False,
            "data_dictionary": str(cfg.DATA_DICTIONARY.name),
        },
        "mappings": {"xeokit_object_map_present": xeokit_map.exists(),
                     "graph_erd_exports_present": False},
    }
    C.write_json(cfg.OUT_AUDIT / "source_inventory.json", inv)

    el = inv["ifc_files"]["ELE"]
    md = f"""# Source Inventory Report

**Building:** {cfg.BUILDING_NAME}

## IFC files (enriched)
| discipline | exists | role / key content |
|---|---|---|
| ARCH | {cfg.ARCH_IFC.exists()} | spatial master — storeys + spaces |
| ELE  | {cfg.ELE_IFC.exists()} | boards={el['has_boards']}, lights={el['has_lights']}, outlets={el['has_outlets']}, cable-trays={el['has_cable_trays']}; **Finnish** property sets |
| HVAC | {cfg.HVAC_IFC.exists()} | HVAC device graph |
| STRUCT | {cfg.STRUCT_IFC.exists()} | structural context |

### ELE product counts
{chr(10).join(f'- `{k}`: {v}' for k, v in sorted(ele.items(), key=lambda x: -x[1]))}

## EnergyPlus / gold dataset (energy source of truth — not re-simulated)
- IDF: `{cfg.IDF_FILE.name}` (zone-level model, byte-stable)
- DuckDB: `{cfg.DUCKDB_FILE.name}` (present: {cfg.DUCKDB_FILE.exists()})
- Parquet grains: {', '.join(parquet_grains)}
- **Best table for board allocation:** `final_zone_device_power_timeseries`
  (per-zone lights/equipment/HVAC kW + kWh-interval), {zones} zones, scenario `{cfg.SCENARIO_ID}`
- Building meters (validation): {', '.join(meters)}
- `eplusout.sql`: **not present** → using the patched Parquet/DuckDB outputs
- Data dictionary: `{cfg.DATA_DICTIONARY.name}`

## Mappings
- xeokit object map present: {xeokit_map.exists()}
- graph/ERD exports present: False (this pipeline creates them)
"""
    C.write_text(cfg.OUT_AUDIT / "source_inventory_report.md", md)
    return {"ele_product_classes": len(ele), "parquet_grains": len(parquet_grains),
            "meters": len(meters), "zones": zones}


if __name__ == "__main__":
    print(run())
