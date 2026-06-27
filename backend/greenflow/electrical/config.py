"""Paths, constants, and the Finnish→canonical property map for the electrical
knowledge-graph / board-allocation layer.

The enriched ELE IFC (Granlund/Simplebim) carries Finnish MEP property sets
(``FI_Tekninen``, ``FI_Komponentti``, ``FI_Sijainti``, ``FI_Geometria``,
``FI_Asennus``, ``FI_Tuote``). This module maps the engineering-relevant keys to
stable canonical names; everything unmapped is preserved verbatim in
``raw_properties_json`` so nothing is silently dropped.
"""
from __future__ import annotations

import math
from pathlib import Path

from ..datasets import active_dataset

# repo root: backend/greenflow/electrical/config.py -> parents[3]
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
ACTIVE_DATASET = active_dataset()
DATASET_KEY = ACTIVE_DATASET.key

# ----- inputs -----
ENRICHED = DATA / "enriched_IFC"
ELE_IFC = ENRICHED / "ELE_enriched.ifc"
ARCH_IFC = ENRICHED / "ARCH_AsBuilt_enriched.ifc"
HVAC_IFC = ENRICHED / "HVAC_enriched.ifc"
STRUCT_IFC = ENRICHED / "STRUCTURAL_enriched.ifc"
IDF_FILE = DATA / "IDF_FILE.idf"

FINAL = ACTIVE_DATASET.parquet_root.parent
PARQUET_ROOT = ACTIVE_DATASET.parquet_root


def _parquet_entry(name: str) -> Path:
    folder = PARQUET_ROOT / name
    if folder.exists():
        return folder
    file = PARQUET_ROOT / f"{name}.parquet"
    return file if file.exists() else folder


def parquet_scan(path: Path) -> str:
    return (path / "**" / "*.parquet").as_posix() if path.is_dir() else path.as_posix()


ZONE_TS = _parquet_entry("final_zone_device_power_timeseries")
METER_TS = _parquet_entry("final_building_meter_timeseries")
if DATASET_KEY == "elnino_2024_mar_apr":
    DATA_DICTIONARY = next(iter((DATA / "final_elnino" / "docs").glob("final_data_dictionary*.csv")),
                           FINAL / "04. docs" / "final_data_dictionary_patched.csv")
else:
    DATA_DICTIONARY = FINAL / "04. docs" / "final_data_dictionary_patched.csv"
DUCKDB_FILE = ACTIVE_DATASET.duckdb_path

# ----- outputs -----
OUT_ELEC = ACTIVE_DATASET.electrical_out
OUT_KG = DATA / "knowledge_graph_build"
OUT_AUDIT = OUT_KG / "audit"
OUT_MAPPING = OUT_KG / "mapping"
OUT_ENERGY = OUT_KG / "energy"

BUILDING_KEY = "greenflow_archetype"
BUILDING_NAME = "Nordic LCA Office"
SCENARIO_ID = ACTIVE_DATASET.scenario_id
TIMESTEP_HOURS = 0.5                             # 30-minute intervals

# ----- electrical engineering constants -----
DEFAULT_POWER_FACTOR = 0.9          # used only for estimated current; marked assumed_default
DEFAULT_VOLTAGE_1P = 230.0          # V, line-to-neutral
DEFAULT_VOLTAGE_3P = 400.0          # V, line-to-line
SQRT3 = math.sqrt(3.0)
LOADING_WARN_PCT = 80.0
LOADING_OVERLOAD_PCT = 100.0

# ----- IFC class buckets -----
BOARD_CLASSES = {"IfcElectricDistributionBoard", "IfcDistributionBoard"}
LIGHT_CLASSES = {"IfcLightFixture", "IfcLamp"}
OUTLET_CLASSES = {"IfcOutlet"}
ALARM_CLASSES = {"IfcAlarm", "IfcSensor"}
CABLE_CLASSES = {"IfcCableCarrierSegment", "IfcCableCarrierFitting",
                 "IfcCableSegment", "IfcCableFitting"}
LOAD_POINT_CLASSES = LIGHT_CLASSES | OUTLET_CLASSES | ALARM_CLASSES

# Finnish property name -> (canonical_key, caster).  Casters keep typing explicit.
def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _s(v):
    if v is None:
        return None
    s = str(v).strip().strip('"')
    return s or None


FINNISH_PSET_MAP: dict[str, tuple[str, object]] = {
    "Jännite": ("voltage_v", _f),
    "Teho": ("design_power_w", _f),
    "Tehokerroin": ("power_factor", _f),
    "Vaiheiden lukumäärä": ("phase_count", _f),
    "Valovirta": ("luminous_flux_lm", _f),
    "Nimellisvirta": ("rated_current_a", _f),
    "Sulake": ("fuse_rating_a", _f),
    "Etukoje": ("upstream_protection", _s),
    "Oikosulkukestoisuusarvo Icw": ("short_circuit_icw_ka", _f),
    "Oikosulkukestoisuusarvo Ipk": ("short_circuit_ipk_ka", _f),
    "Laitetunnus": ("device_tag", _s),
    "Järjestelmien tunnukset": ("system_code", _s),
    "Järjestelmien nimet": ("system_name", _s),
    "01 Komponentin pääryhmä": ("component_main_group", _s),
    "02 Komponentin alaryhmä": ("component_sub_group", _s),
    "03 Komponentin koodi": ("component_code", _s),
    "04 Komponentin yleisnimi": ("component_general_name", _s),
    "05 Komponentin yleistunnus": ("component_general_tag", _s),
    "Leveys": ("width_mm", _f),
    "Korkeus": ("height_mm", _f),
    "Syvyys": ("depth_mm", _f),
    "Pituus": ("length_mm", _f),
    "Koko": ("size_label", _s),
    "03 Asennuskorko, abs.": ("install_elev_abs_mm", _f),
    "Tuotetyypin nimi": ("product_type_name", _s),
    "Tuotetyypin valmistaja": ("manufacturer", _s),
    "Tuotetyypin kuvaus": ("product_description", _s),
}

# load category labels
CAT_LIGHTS = "lights"
CAT_EQUIPMENT = "equipment"
CAT_HVAC = "hvac"
LOAD_CATEGORIES = (CAT_LIGHTS, CAT_EQUIPMENT, CAT_HVAC)

# zone gold columns per category (kW + kWh-interval)
ZONE_CAT_COLUMNS = {
    CAT_LIGHTS: ("lights_electricity_kw", "lights_electricity_kwh_interval"),
    CAT_EQUIPMENT: ("equipment_electricity_kw", "equipment_electricity_kwh_interval"),
    CAT_HVAC: ("final_hvac_electricity_kw", "final_hvac_electricity_kwh_interval"),
}
# building meters used to reconcile each category (Phase 11)
METER_FOR_CATEGORY = {
    CAT_LIGHTS: "InteriorLights:Electricity",
    CAT_EQUIPMENT: "InteriorEquipment:Electricity",
    CAT_HVAC: "Electricity:HVAC",
}
METER_TOTAL = "Electricity:Facility"

UNMAPPED_BOARD_ID = "board_UNMAPPED"


def ensure_dirs() -> None:
    for d in (OUT_ELEC, OUT_KG, OUT_AUDIT, OUT_MAPPING, OUT_ENERGY):
        d.mkdir(parents=True, exist_ok=True)
