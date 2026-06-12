"""Report Agent: build markdown reports from live DB data, render to PDF."""

from __future__ import annotations

from datetime import datetime

from ..llm import llm_text
from ..state import GreenFlowState
from ..tools import simulation_tool, timeseries_tool
from ..tools.report_tool import save_report

TITLES = {
    "building_semantic_report": "Building Semantic Report",
    "hvac_elec_report": "HVAC & Electrical Report",
    "peak_strategy_report": "Peak-Hour Strategy Report",
    "baseline_vs_optimized_report": "Baseline vs Optimized Report",
    "optimization_summary_report": "Optimization Summary Report",
}


def run(state: GreenFlowState) -> dict:
    report_type = state.get("report_type") or "building_semantic_report"
    builder = {
        "building_semantic_report": _building_semantic_md,
        "hvac_elec_report": _hvac_elec_md,
        "peak_strategy_report": _optimization_md,
        "baseline_vs_optimized_report": _baseline_vs_optimized_md,
        "optimization_summary_report": _optimization_md,
    }.get(report_type, _building_semantic_md)

    markdown = builder(state)
    title = TITLES.get(report_type, "GreenFlow Report")
    saved = save_report(state["building_id"], report_type, title, markdown,
                        agent_run_id=state.get("run_id"),
                        summary={"sections": markdown.count("\n## ")})
    return {
        "report_type": report_type,
        "report_markdown": markdown,
        "pdf_path": saved["pdf_path"],
        "report_id": saved["report_id"],
    }


def _header(title: str, state: GreenFlowState) -> str:
    b = state.get("building_summary", {})
    return (f"# {title}\n\n"
            f"Building: **{b.get('name', 'n/a')}** | Location: "
            f"{b.get('location_name', 'n/a')} | Generated: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")


def _building_semantic_md(state: GreenFlowState) -> str:
    b = state.get("building_summary", {})
    zones = state.get("zones", [])
    zone_state = state.get("latest_zone_state", {})
    findings = state.get("abnormal_findings", [])
    missing = state.get("missing_metadata", [])
    equipment_map = state.get("zone_equipment_map", {})

    md = _header("Building Semantic Report", state)
    md += ("## Building overview\n\n"
           f"| Metric | Value |\n|---|---|\n"
           f"| Floors | {b.get('floor_count', 0)} |\n"
           f"| Thermal zones | {b.get('zone_count', 0)} |\n"
           f"| Devices | {b.get('device_count', 0)} |\n"
           f"| Total area | {b.get('total_area_m2', 0):.0f} m2 |\n"
           f"| Source dataset | {b.get('source_dataset', 'n/a')} |\n\n")

    md += "## Zone hierarchy and state\n\n"
    md += "| Zone | Type | Area m2 | Occupancy | Temp C | Load kW | Comfort |\n"
    md += "|---|---|---|---|---|---|---|\n"
    for z in zones:
        st = zone_state.get(z["entity_key"], {})
        md += (f"| {z['name']} | {z['room_type']} | {z.get('area_m2', 0):.0f} "
               f"| {st.get('occupancy_count', '-')} | {st.get('temperature_c', '-')} "
               f"| {st.get('total_power_kw', '-')} | {st.get('comfort_risk', '-')} |\n")

    md += "\n## Zone-equipment mapping\n\n| Zone | Devices |\n|---|---|\n"
    for zk, devices in equipment_map.items():
        names = ", ".join(sorted({d["name"] for d in devices}))
        md += f"| {zk} | {names} |\n"

    md += "\n## Abnormal state summary\n\n"
    if findings:
        for f in findings:
            md += f"- **[{f['severity']}] {f['finding_type']}** - {f['detail']}\n"
    else:
        md += "- No abnormal findings.\n"

    md += "\n## Missing metadata / mapping quality\n\n"
    if missing:
        for m in missing:
            md += f"- {m['type']}: {m['detail']}\n"
    else:
        md += "- All zones and devices are fully mapped.\n"

    md += ("\n## EnergyPlus readiness\n\n"
           "- Geometry, constructions, schedules and internal loads parsed from IDF.\n"
           "- IdealLoadsAirSystem zone HVAC; baseline runs available.\n"
           "- Synthetic fallback engine active when the EnergyPlus binary is absent.\n")

    summary_fallback = (f"The building has {b.get('zone_count', 0)} zones with "
                        f"{len(findings)} abnormal findings and "
                        f"{len(missing)} metadata gaps.")
    md += "\n## Assessment\n\n" + llm_text(
        "Summarize this building operations report in 3 sentences:\n" + md,
        summary_fallback) + "\n"
    return md


def _hvac_elec_md(state: GreenFlowState) -> str:
    device_state = state.get("latest_device_state", {})
    findings = [f for f in state.get("abnormal_findings", [])
                if "hvac" in f["finding_type"] or "lighting" in f["finding_type"]]

    md = _header("HVAC & Electrical Report", state)
    md += "## Device inventory and state\n\n"
    md += "| Device | Type | Zone | Status | Power kW | Controllable |\n"
    md += "|---|---|---|---|---|---|\n"
    for key, d in sorted(device_state.items()):
        md += (f"| {d['name']} | {d.get('device_subtype', '-')} "
               f"| {d.get('zone_key') or 'building'} | {d.get('status', '-')} "
               f"| {d.get('power_kw', 0)} | {'yes' if d.get('controllable') else 'no'} |\n")

    controllable = [d for d in device_state.values() if d.get("controllable")]
    md += (f"\n## Controllable devices\n\n{len(controllable)} of "
           f"{len(device_state)} devices accept agent actions "
           f"(air terminals, lighting circuits, AHU).\n")

    md += "\n## Abnormal HVAC/electrical behavior\n\n"
    if findings:
        for f in findings:
            md += f"- **[{f['severity']}]** {f['detail']}\n"
    else:
        md += "- None detected at the latest tick.\n"

    md += ("\n## EnergyPlus usage\n\n"
           "- Lighting/equipment W/m2 densities map to Lights/ElectricEquipment.\n"
           "- Air terminals are action targets through schedule overrides only.\n")
    return md


def _baseline_vs_optimized_md(state: GreenFlowState) -> str:
    kpi = state.get("baseline_vs_optimized") or \
        simulation_tool.get_latest_comparison(state["building_id"]).get("details_json", {})
    md = _header("Baseline vs Optimized Report", state)
    if not kpi:
        return md + "No comparison runs available yet. Run an optimization first.\n"
    md += ("## Counterfactual KPI comparison\n\n"
           "Same weather and occupancy; only agent actions differ.\n\n"
           "| KPI | Baseline | Optimized | Delta |\n|---|---|---|---|\n"
           f"| Energy (kWh/day) | {kpi.get('baseline_kwh')} | {kpi.get('optimized_kwh')} "
           f"| -{kpi.get('saving_kwh')} ({kpi.get('saving_percent')}%) |\n"
           f"| Cost (VND/day) | {kpi.get('baseline_cost_vnd', '-')} "
           f"| {kpi.get('optimized_cost_vnd', '-')} | -{kpi.get('cost_saving_vnd')} |\n"
           f"| Peak window demand (kW) | {kpi.get('peak_window_baseline_kw', '-')} "
           f"| {kpi.get('peak_window_optimized_kw', '-')} "
           f"| -{kpi.get('peak_reduction_kw')} |\n"
           f"| Comfort violation (min) | {kpi.get('comfort_violation_baseline_min', '-')} "
           f"| {kpi.get('comfort_violation_optimized_min', '-')} "
           f"| {kpi.get('comfort_violation_delta_min')} |\n"
           f"| CO2 avoided (kg) | - | - | {kpi.get('co2_avoided_kg')} |\n\n")
    md += ("## Honest framing\n\n"
           "This is a what-if counterfactual simulation, not direct real-time "
           "control of the building.\n")
    return md


def _optimization_md(state: GreenFlowState) -> str:
    md = _header("Optimization Summary Report", state)
    sim = state.get("simulation_result", {})
    md += ("## Expected impact\n\n"
           f"- Saving: **{sim.get('expected_saving_kwh', 0)} kWh/day** "
           f"({sim.get('expected_cost_saving_vnd', 0):,.0f} VND)\n"
           f"- Peak reduction: **{sim.get('expected_peak_reduction_kw', 0)} kW**\n"
           f"- Comfort impact: {sim.get('comfort_violation_delta_min', 0)} min violation delta\n"
           f"- Engine: {sim.get('engine', 'synthetic')}\n\n")
    md += "## Final action plan\n\n"
    md += "| Action | Targets | Window | Saving kWh | Policy |\n|---|---|---|---|---|\n"
    for a in state.get("final_action_plan", []):
        targets = ", ".join(a.get("target_zone_keys", [])) or "all zones"
        md += (f"| {a['action_type']} | {targets} "
               f"| {a.get('start_hour', 0):.0f}:00-{a.get('end_hour', 24):.0f}:00 "
               f"| {a.get('expected_saving_kwh', '-')} | {a['policy_decision']} |\n")
    md += "\n## Policy reasoning\n\n"
    for d in state.get("policy_decisions", []):
        md += f"- **{d['action']['action_type']}** -> {d['decision']}: " \
              f"{'; '.join(d['reasons'])}\n"
    md += _baseline_vs_optimized_md(state).split("# Baseline vs Optimized Report")[-1]
    return md
