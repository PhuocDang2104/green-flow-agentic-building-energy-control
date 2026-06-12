"""Simulation runner: EnergyPlus when available, synthetic engine otherwise."""

from __future__ import annotations

import csv
import subprocess
import tempfile
from pathlib import Path

from ..config import get_settings
from .actions import Action
from .action_to_idf import write_variant_idf
from .synthetic_baseline import (SimRecord, SimResult, run_synthetic,
                                 zone_specs_from_normalized)


def energyplus_available() -> bool:
    s = get_settings()
    return bool(s.energyplus_bin) and Path(s.energyplus_bin).exists() \
        and Path(s.weather_epw).exists()


def run_simulation(normalized: dict, actions: list[Action] | None = None,
                   *, engine: str = "auto", days: int = 1,
                   is_weekend: bool = False) -> SimResult:
    """Run a building simulation and return a SimResult.

    engine: "auto" | "synthetic" | "energyplus"
    """
    actions = actions or []
    if engine == "energyplus" or (engine == "auto" and energyplus_available()):
        try:
            return _run_energyplus(normalized, actions)
        except Exception as exc:  # fall back rather than fail the demo
            print(f"EnergyPlus run failed ({exc}); falling back to synthetic engine")
    specs = zone_specs_from_normalized(normalized)
    return run_synthetic(specs, actions, days=days, is_weekend=is_weekend)


def _run_energyplus(normalized: dict, actions: list[Action]) -> SimResult:
    s = get_settings()
    workdir = Path(tempfile.mkdtemp(prefix="greenflow_ep_",
                                    dir=s.storage_path / "processed" / "energyplus"))
    idf = write_variant_idf(s.idf_file, workdir / "model.idf", actions)
    cmd = [s.energyplus_bin, "-w", str(Path(s.weather_epw).resolve()),
           "-d", str(workdir), "-r", str(idf)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"energyplus exited {proc.returncode}: {proc.stderr[-400:]}")
    return _parse_eplus_csv(workdir / "eplusout.csv", normalized)


def _parse_eplus_csv(csv_path: Path, normalized: dict) -> SimResult:
    """Map eplusout.csv columns back to zones; emit SimRecords.

    Columns look like 'BLOCK OPEN_OFFICE STOREY 0:Zone Mean Air Temperature [C](TimeStep)'.
    """
    zone_names = {z["name"].upper(): z["entity_key"] for z in normalized["zones"]}
    result = SimResult(engine="energyplus", step_minutes=15)
    with csv_path.open(encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        minutes = 0
        for row in reader:
            per_zone: dict[str, dict] = {k: {} for k in zone_names.values()}
            for col, val in row.items():
                up = col.upper()
                for zname, zkey in zone_names.items():
                    if not up.startswith(zname + ":"):
                        continue
                    try:
                        v = float(val)
                    except (TypeError, ValueError):
                        continue
                    if "MEAN AIR TEMPERATURE" in up:
                        per_zone[zkey]["temperature_c"] = v
                    elif "TOTAL COOLING ENERGY" in up:        # J per timestep
                        per_zone[zkey]["hvac_kw"] = v / 3600.0 / 1000.0 * 4
                    elif "LIGHTS ELECTRICITY ENERGY" in up:
                        per_zone[zkey]["lighting_kw"] = v / 3600.0 / 1000.0 * 4
                    elif "ELECTRIC EQUIPMENT ELECTRICITY ENERGY" in up:
                        per_zone[zkey]["plug_kw"] = v / 3600.0 / 1000.0 * 4
            for zkey, vals in per_zone.items():
                if not vals:
                    continue
                lighting = vals.get("lighting_kw", 0.0)
                plug = vals.get("plug_kw", 0.0)
                hvac = vals.get("hvac_kw", 0.0) / 3.2  # electricity at COP 3.2
                temp = vals.get("temperature_c", 25.0)
                result.records.append(SimRecord(
                    minutes=minutes, zone_key=zkey,
                    temperature_c=round(temp, 2), setpoint_c=24.0,
                    occupancy_count=0.0,
                    lighting_kw=round(lighting, 3), plug_kw=round(plug, 3),
                    hvac_kw=round(hvac, 3),
                    total_kw=round(lighting + plug + hvac, 3),
                    comfort_violated=temp > 26.5,
                ))
            minutes += 15
    from .synthetic_baseline import _fill_totals
    _fill_totals(result)
    return result
