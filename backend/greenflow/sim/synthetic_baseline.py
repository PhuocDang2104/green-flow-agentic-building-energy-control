"""Deterministic physics-lite zone simulation (EnergyPlus fallback).

Computes 15-minute zone trajectories driven by the schedules parsed from the
IDF: lighting/plug loads from W/m2 x schedule, occupancy from people-density x
schedule, an outdoor-temperature sine profile for Hanoi, an envelope UA model
and window solar gains for cooling load, plus a simple thermal-mass "coolth
storage" term so pre-cooling has a realistic peak-shaving effect.

It never replaces EnergyPlus for real studies (see REPO_BUILD_SPEC §1.1); it
exists so the repo demos end-to-end without the EnergyPlus binary, producing
the same simulation_results record shape as the E+ parser.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .actions import Action, zone_modifiers_at

# Tunable physical constants (plausible office defaults, not measured data)
ENVELOPE_U_W_M2K = 1.9       # average envelope U-value
SOLAR_PEAK_KW_M2 = 0.16      # peak solar gain through glazing per m2 window
PERSON_SENSIBLE_KW = 0.12    # sensible heat per person
COP = 3.2                    # cooling system COP
COMFORT_LIMIT_C = 26.5       # comfort violation threshold while occupied
COOLTH_DECAY = 0.85          # thermal-mass storage retention per step
COOLTH_GAIN = 0.30           # fraction of extra pre-cooling stored
HANOI_TEMP_MEAN = 30.0       # June design day mean
HANOI_TEMP_AMPL = 4.5


def outdoor_temp_c(hour: float) -> float:
    """Sine diurnal profile: min ~05:30, max ~15:30."""
    return HANOI_TEMP_MEAN + HANOI_TEMP_AMPL * math.sin(2 * math.pi * (hour - 9.5) / 24.0)


def solar_fraction(hour: float) -> float:
    """0 at night, peaks ~13:00."""
    if hour < 6 or hour > 18.5:
        return 0.0
    return max(0.0, math.sin(math.pi * (hour - 6) / 12.5))


@dataclass
class ZoneSpec:
    """Static zone inputs for the synthetic engine (from normalized JSON)."""
    zone_key: str
    name: str
    area_m2: float
    height_m: float
    lights_w_m2: float
    equip_w_m2: float
    people_per_m2: float
    window_area_m2: float
    envelope_area_m2: float
    occupancy_weekday: list[float]
    occupancy_weekend: list[float]
    lights_weekday: list[float]
    lights_weekend: list[float]
    cooling_setpoint: list[float]   # 24 hourly values


@dataclass
class SimRecord:
    minutes: int                    # minutes since 00:00 of sim day
    zone_key: str
    temperature_c: float
    setpoint_c: float
    occupancy_count: float
    lighting_kw: float
    plug_kw: float
    hvac_kw: float
    total_kw: float
    comfort_violated: bool


@dataclass
class SimResult:
    engine: str
    step_minutes: int
    records: list[SimRecord] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)


def zone_specs_from_normalized(normalized: dict) -> list[ZoneSpec]:
    schedules = normalized["schedules"]
    cooling_sched_name = normalized["setpoints"]["cooling_schedule"]
    cooling = schedules.get(cooling_sched_name, {}).get("weekday", [24.0] * 24)

    win_area: dict[str, float] = {}
    for f in normalized["fenestrations"]:
        pts = f["vertices"]
        if len(pts) >= 3:
            # area via cross products around first vertex
            area = 0.0
            for i in range(1, len(pts) - 1):
                ux = [pts[i][k] - pts[0][k] for k in range(3)]
                vx = [pts[i + 1][k] - pts[0][k] for k in range(3)]
                cx = (ux[1] * vx[2] - ux[2] * vx[1],
                      ux[2] * vx[0] - ux[0] * vx[2],
                      ux[0] * vx[1] - ux[1] * vx[0])
                area += 0.5 * (cx[0] ** 2 + cx[1] ** 2 + cx[2] ** 2) ** 0.5
            win_area[f["zone_key"]] = win_area.get(f["zone_key"], 0.0) + area

    env_area: dict[str, float] = {}
    for s in normalized["surfaces"]:
        if s["boundary"] == "outdoors":
            pts = s["vertices"]
            area = 0.0
            for i in range(1, len(pts) - 1):
                ux = [pts[i][k] - pts[0][k] for k in range(3)]
                vx = [pts[i + 1][k] - pts[0][k] for k in range(3)]
                cx = (ux[1] * vx[2] - ux[2] * vx[1],
                      ux[2] * vx[0] - ux[0] * vx[2],
                      ux[0] * vx[1] - ux[1] * vx[0])
                area += 0.5 * (cx[0] ** 2 + cx[1] ** 2 + cx[2] ** 2) ** 0.5
            env_area[s["zone_key"]] = env_area.get(s["zone_key"], 0.0) + area

    specs = []
    for z in normalized["zones"]:
        occ = schedules.get(z["occupancy_schedule"], {"weekday": [0.0] * 24, "weekend": [0.0] * 24})
        lights = schedules.get(z["lights_schedule"], {"weekday": [0.0] * 24, "weekend": [0.0] * 24})
        specs.append(ZoneSpec(
            zone_key=z["entity_key"],
            name=z["name"],
            area_m2=z["area_m2"],
            height_m=z["height_m"],
            lights_w_m2=z["lights_w_m2"],
            equip_w_m2=z["equip_w_m2"],
            people_per_m2=z["people_per_m2"],
            window_area_m2=round(win_area.get(z["entity_key"], 0.0), 2),
            envelope_area_m2=round(env_area.get(z["entity_key"], 0.0), 2),
            occupancy_weekday=occ["weekday"],
            occupancy_weekend=occ["weekend"],
            lights_weekday=lights["weekday"],
            lights_weekend=lights["weekend"],
            cooling_setpoint=cooling,
        ))
    return specs


def _sched_at(values: list[float], hour: float) -> float:
    """Linear interpolation between hourly schedule values."""
    h0 = int(hour) % 24
    h1 = (h0 + 1) % 24
    frac = hour - int(hour)
    return values[h0] * (1 - frac) + values[h1] * frac


def run_synthetic(
    specs: list[ZoneSpec],
    actions: list[Action] | None = None,
    *,
    is_weekend: bool = False,
    step_minutes: int = 15,
    days: int = 1,
) -> SimResult:
    """Run the synthetic engine. Deterministic: same inputs -> same outputs."""
    actions = actions or []
    result = SimResult(engine="synthetic", step_minutes=step_minutes)
    coolth: dict[str, float] = {s.zone_key: 0.0 for s in specs}

    steps_per_day = 24 * 60 // step_minutes
    for day in range(days):
        for step in range(steps_per_day):
            minutes = day * 1440 + step * step_minutes
            hour = (step * step_minutes) / 60.0
            t_out = outdoor_temp_c(hour)
            sol = solar_fraction(hour)

            for spec in specs:
                mods = zone_modifiers_at(actions, spec.zone_key, hour)
                occ_sched = spec.occupancy_weekend if is_weekend else spec.occupancy_weekday
                lights_sched = spec.lights_weekend if is_weekend else spec.lights_weekday

                occupancy = spec.area_m2 * spec.people_per_m2 * _sched_at(occ_sched, hour)
                lighting_kw = (spec.area_m2 * spec.lights_w_m2 / 1000.0
                               * _sched_at(lights_sched, hour) * mods["lighting_factor"])
                plug_kw = (spec.area_m2 * spec.equip_w_m2 / 1000.0
                           * _sched_at(lights_sched, hour))

                setpoint = _sched_at(spec.cooling_setpoint, hour) + mods["setpoint_delta_c"]
                hvac_on = (not mods["hvac_off"]) and setpoint < 27.5 and not (
                    is_weekend and occupancy < 0.5)

                internal_kw = lighting_kw + plug_kw + occupancy * PERSON_SENSIBLE_KW
                solar_kw = spec.window_area_m2 * SOLAR_PEAK_KW_M2 * sol
                envelope_kw = max(
                    0.0, ENVELOPE_U_W_M2K * spec.envelope_area_m2 * (t_out - setpoint) / 1000.0)

                if hvac_on:
                    cooling_need_kw = internal_kw + solar_kw + envelope_kw
                    # thermal mass: discharge stored coolth against the need
                    discharge = min(coolth[spec.zone_key], cooling_need_kw * 0.5)
                    cooling_need_kw -= discharge
                    coolth[spec.zone_key] = (coolth[spec.zone_key] - discharge) * COOLTH_DECAY
                    if mods["setpoint_delta_c"] < 0:  # pre-cooling charges the mass
                        extra = abs(mods["setpoint_delta_c"]) * 0.4 * spec.area_m2 / 100.0
                        cooling_need_kw += extra
                        coolth[spec.zone_key] += extra * COOLTH_GAIN / COOLTH_DECAY
                    hvac_kw = max(0.0, cooling_need_kw) / COP
                    temperature = setpoint + min(1.2, max(0.0, (t_out - setpoint) * 0.04))
                else:
                    hvac_kw = 0.0
                    coolth[spec.zone_key] *= COOLTH_DECAY
                    drift = 0.55 + 0.05 * min(4.0, internal_kw)
                    temperature = t_out - (t_out - 25.5) * (1 - drift)

                total_kw = lighting_kw + plug_kw + hvac_kw
                violated = bool(occupancy >= 0.5 and temperature > COMFORT_LIMIT_C)

                result.records.append(SimRecord(
                    minutes=minutes,
                    zone_key=spec.zone_key,
                    temperature_c=round(temperature, 2),
                    setpoint_c=round(setpoint, 2),
                    occupancy_count=round(occupancy, 1),
                    lighting_kw=round(lighting_kw, 3),
                    plug_kw=round(plug_kw, 3),
                    hvac_kw=round(hvac_kw, 3),
                    total_kw=round(total_kw, 3),
                    comfort_violated=violated,
                ))

    _fill_totals(result)
    return result


def _fill_totals(result: SimResult) -> None:
    step_h = result.step_minutes / 60.0
    energy_kwh = sum(r.total_kw for r in result.records) * step_h
    hvac_kwh = sum(r.hvac_kw for r in result.records) * step_h
    lighting_kwh = sum(r.lighting_kw for r in result.records) * step_h
    plug_kwh = sum(r.plug_kw for r in result.records) * step_h

    by_step: dict[int, float] = {}
    for r in result.records:
        by_step[r.minutes] = by_step.get(r.minutes, 0.0) + r.total_kw
    peak_minutes, peak_kw = max(by_step.items(), key=lambda kv: kv[1]) if by_step else (0, 0.0)

    violation_minutes = sum(result.step_minutes for r in result.records if r.comfort_violated)

    result.totals = {
        "energy_kwh": round(energy_kwh, 2),
        "hvac_kwh": round(hvac_kwh, 2),
        "lighting_kwh": round(lighting_kwh, 2),
        "plug_kwh": round(plug_kwh, 2),
        "peak_demand_kw": round(peak_kw, 2),
        "peak_minutes": peak_minutes,
        "comfort_violation_minutes": violation_minutes,
    }
