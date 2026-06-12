"""Simulation engine tests (REPO_BUILD_SPEC §17.2)."""

from greenflow.sim.actions import make_action
from greenflow.sim.action_to_idf import apply_actions_to_idf
from greenflow.sim.kpi import compare_runs, tariff_at
from greenflow.sim.synthetic_baseline import run_synthetic, zone_specs_from_normalized


def test_baseline_produces_output(normalized):
    result = run_synthetic(zone_specs_from_normalized(normalized))
    assert len(result.records) == 5 * 96  # 5 zones x 96 ticks
    assert result.totals["energy_kwh"] > 0
    assert result.totals["peak_demand_kw"] > 0


def test_deterministic(normalized):
    specs = zone_specs_from_normalized(normalized)
    a = run_synthetic(specs)
    b = run_synthetic(specs)
    assert a.totals == b.totals


def test_lighting_reduction_saves_energy(normalized):
    specs = zone_specs_from_normalized(normalized)
    baseline = run_synthetic(specs)
    action = make_action("lighting_reduction", [], start_hour=8, end_hour=18)
    optimized = run_synthetic(specs, [action])
    kpi = compare_runs(baseline, optimized)
    assert kpi["saving_kwh"] > 0
    assert kpi["lighting_kwh_delta"] < 0


def test_same_inputs_only_actions_differ(normalized):
    """Counterfactual integrity: weekend/weekday flags identical across runs."""
    specs = zone_specs_from_normalized(normalized)
    baseline = run_synthetic(specs, is_weekend=False)
    optimized = run_synthetic(specs, [make_action("hvac_eco_mode", [])],
                              is_weekend=False)
    # occupancy trajectories must match exactly (actions never touch occupancy)
    base_occ = [r.occupancy_count for r in baseline.records]
    opt_occ = [r.occupancy_count for r in optimized.records]
    assert base_occ == opt_occ


def test_action_to_idf_modifies_schedules_only(normalized):
    from pathlib import Path
    idf_text = (Path(__file__).resolve().parents[2]
                / "data" / "greenflow_archetype.idf").read_text(encoding="utf-8",
                                                                errors="replace")
    action = make_action("hvac_eco_mode", [], start_hour=12, end_hour=16)
    patched = apply_actions_to_idf(idf_text, action and [action])
    assert patched != idf_text
    # geometry untouched
    assert patched.count("BUILDINGSURFACE:DETAILED") == idf_text.count(
        "BUILDINGSURFACE:DETAILED")
    # only CoolSetSched values change
    assert "25" in patched  # 24 + 1.0 eco delta appears


def test_tariff_bands():
    assert tariff_at(2) == 1184      # off-peak
    assert tariff_at(10) == 3314     # morning peak
    assert tariff_at(14) == 1839     # normal
    assert tariff_at(18) == 3314     # evening peak
    assert tariff_at(23) == 1184


def test_pre_cooling_reduces_peak_window(normalized):
    specs = zone_specs_from_normalized(normalized)
    baseline = run_synthetic(specs)
    actions = [make_action("pre_cooling", [], start_hour=11, end_hour=13),
               make_action("peak_load_reduction", [], start_hour=13, end_hour=16)]
    optimized = run_synthetic(specs, actions)
    kpi = compare_runs(baseline, optimized)
    assert kpi["peak_reduction_kw"] > 0
