"""Report Agent: build markdown reports from live DB data, render to PDF."""

from __future__ import annotations

from datetime import datetime

from ..llm import llm_text
from ..state import GreenFlowState
from ..tools import simulation_tool, timeseries_tool
from ..tools.report_tool import save_report

TITLES = {
    "building_semantic_report": "GreenFlow Building Performance & Semantic Report",
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


def _cell(value, max_len: int = 140) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("|", "/").split())
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value, suffix: str = "", digits: int = 1) -> str:
    if value in (None, ""):
        return "-"
    n = _num(value, None)
    if n is None:
        return _cell(value)
    if abs(n - round(n)) < 0.05:
        return f"{int(round(n)):,}{suffix}"
    return f"{n:,.{digits}f}{suffix}"


def _score_status(score) -> str:
    n = _num(score, 0)
    if n >= 80:
        return "Good"
    if n >= 60:
        return "Watch"
    return "Critical"


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "warning": 2, "medium": 2, "low": 3, "info": 4}
    return order.get((severity or "").lower(), 5)


def _recommendation_for_finding(finding: dict) -> str:
    ftype = (finding.get("finding_type") or "").lower()
    detail = (finding.get("detail") or "").lower()
    if "co2" in ftype or "co2" in detail or "air" in ftype:
        return "Inspect ventilation schedule, outside-air path, and CO2 sensor calibration."
    if "comfort" in ftype or "temperature" in detail:
        return "Check setpoint, zone load, and terminal-unit response for affected zones."
    if "peak" in ftype or "demand" in detail or "load" in detail:
        return "Move flexible load outside peak window and review demand-response sequence."
    if "metadata" in ftype or "mapping" in detail:
        return "Complete zone-device mapping before using this point for automated control."
    if "fault" in ftype or "sensor" in detail or "device" in detail:
        return "Triage BMS fault, verify device status, then resolve or suppress stale alerts."
    return "Assign facility engineer for verification and close-out evidence."


def _recommended_actions(health: dict, kpis: dict, findings: list[dict],
                         missing: list[dict]) -> list[tuple[str, str, str, str]]:
    dims = {d.get("key"): d for d in health.get("dimensions", [])}
    rows: list[tuple[str, str, str, str]] = []

    if _num(dims.get("energy", {}).get("score"), 100) < 85:
        rows.append(("Demand management",
                     "Run peak-demand mitigation for high-risk zones before the next peak window.",
                     "Facility energy lead", "Today"))
    if _num(dims.get("air", {}).get("score"), 100) < 80:
        rows.append(("Indoor air quality",
                     "Review CO2 excursions, ventilation schedule, and economizer/outside-air availability.",
                     "BMS operator", "24 hours"))
    if _num(dims.get("comfort", {}).get("score"), 100) < 82:
        rows.append(("Thermal comfort",
                     "Inspect zones in high or watch comfort risk and verify setpoint compliance.",
                     "Operations team", "24 hours"))
    if _num(dims.get("reliability", {}).get("score"), 100) < 85:
        rows.append(("Reliability",
                     "Separate device faults from sensor-watch alerts; close resolved alerts in BMS.",
                     "Maintenance lead", "48 hours"))
    if missing:
        rows.append(("Data quality",
                     "Close semantic mapping gaps so controls and reports use traceable source points.",
                     "Digital twin owner", "This week"))
    if not rows and not findings:
        rows.append(("Continuous monitoring",
                     "Maintain current control strategy; keep weekly BPI review and alert hygiene.",
                     "Operations team", "Weekly"))
    return rows[:6]


def _building_semantic_md(state: GreenFlowState) -> str:
    b = state.get("building_summary", {})
    zones = state.get("zones", [])
    zone_state = state.get("latest_zone_state", {})
    findings = state.get("abnormal_findings", [])
    missing = state.get("missing_metadata", [])
    equipment_map = state.get("zone_equipment_map", {})
    health = timeseries_tool.get_building_health(state["building_id"]) or {}
    kpis = timeseries_tool.get_building_kpis(state["building_id"]) or {}
    dims = {d.get("key"): d for d in health.get("dimensions", [])}
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    source_ts = health.get("timestamp") or kpis.get("timestamp") or "latest available"
    total_zones = int(b.get("zone_count") or health.get("zones") or len(zones) or 0)
    total_devices = int(b.get("device_count") or 0)
    score = health.get("score")
    grade = _score_status(score)

    md = _header("GreenFlow Building Performance & Semantic Report", state)
    md += ("## Executive summary\n\n"
           f"- Overall Building Performance Index is **{_fmt(score)}/100 ({grade})** "
           f"against the latest replay anchor: **{_cell(source_ts)}**.\n"
           f"- Current building load is **{_fmt(kpis.get('total_kw'), ' kW')}** with "
           f"**{_fmt(kpis.get('occupancy'), ' occupants')}** represented in telemetry.\n"
           f"- The report covers **{total_zones:,} thermal zones**, "
           f"**{total_devices:,} devices**, and semantic mappings from the current backend state.\n"
           f"- Priority exceptions: **{len(findings):,} abnormal findings** and "
           f"**{len(missing):,} semantic/data-quality gaps** require review.\n\n")

    md += ("## Report scope and asset profile\n\n"
           "| Item | Value |\n|---|---|\n"
           f"| Building | {_cell(b.get('name', 'n/a'))} |\n"
           f"| Location | {_cell(b.get('location_name', 'n/a'))} |\n"
           f"| Generated | {generated_at} |\n"
           f"| Floors | {_fmt(b.get('floor_count'))} |\n"
           f"| Thermal zones | {total_zones:,} |\n"
           f"| Devices | {total_devices:,} |\n"
           f"| Gross modeled area | {_fmt(b.get('total_area_m2'), ' m2', 0)} |\n"
           f"| Source dataset | {_cell(b.get('source_dataset', 'n/a'))} |\n\n")

    md += "## Building Performance Index scorecard\n\n"
    md += "| Dimension | Score | Target | Status | Backend evidence |\n"
    md += "|---|---|---|---|---|\n"
    score_rows = [
        ("Overall score", score, 80, grade, f"{len(findings)} findings; {len(missing)} metadata gaps"),
        ("Air quality", dims.get("air", {}).get("score"), 80, None, dims.get("air", {}).get("detail")),
        ("Energy / demand", dims.get("energy", {}).get("score"), 85, None, dims.get("energy", {}).get("detail")),
        ("Thermal comfort", dims.get("comfort", {}).get("score"), 82, None, dims.get("comfort", {}).get("detail")),
        ("Equipment health", dims.get("reliability", {}).get("score"), 85, None,
         dims.get("reliability", {}).get("detail")),
    ]
    for label, row_score, target, status, evidence in score_rows:
        status = status or _score_status(row_score)
        md += (f"| {_cell(label)} | {_fmt(row_score)} | {target} | "
               f"{_cell(status)} | {_cell(evidence)} |\n")

    md += "\n## Operational snapshot\n\n"
    md += "| Metric | Current value | Why it matters |\n|---|---|---|\n"
    md += (f"| Total demand | {_fmt(kpis.get('total_kw'), ' kW')} | Real-time electrical load used by the demand score. |\n"
           f"| Calendar-day energy | {_fmt(kpis.get('kwh'), ' kWh')} | Day-to-date consumption from counted zones. |\n"
           f"| Operating cost | {_fmt(kpis.get('cost'), ' VND', 0)} | Day-to-date energy cost estimate. |\n"
           f"| Occupancy | {_fmt(kpis.get('occupancy'), ' people')} | People load used to interpret comfort and IAQ risk. |\n"
           f"| Comfort high risk | {_fmt(kpis.get('comfort_high'), ' zones')} | Zones outside acceptable comfort conditions. |\n"
           f"| Peak-demand risk | {_fmt(kpis.get('peak_high'), ' zones')} | Zones contributing to demand-window exposure. |\n")

    md += "\n## Priority findings and risk register\n\n"
    if findings:
        for idx, f in enumerate(sorted(findings, key=lambda x: _severity_rank(x.get("severity")))[:12], 1):
            md += (f"### {idx}. {_cell(f.get('finding_type'))} "
                   f"({_cell(f.get('severity'))})\n\n"
                   f"- Evidence: {_cell(f.get('detail'), 260)}\n"
                   f"- Recommended action: {_recommendation_for_finding(f)}\n\n")
    else:
        md += "- No abnormal findings at the latest backend replay anchor.\n"

    md += "\n## Recommended action plan\n\n"
    md += "| Workstream | Action | Owner | Target window |\n|---|---|---|---|\n"
    for workstream, action, owner, window in _recommended_actions(health, kpis, findings, missing):
        md += f"| {_cell(workstream)} | {_cell(action, 92)} | {_cell(owner)} | {_cell(window)} |\n"

    md += "\n## Semantic coverage and data quality\n\n"
    mapped_zone_count = len([1 for devices in equipment_map.values() if devices])
    coverage = (mapped_zone_count / total_zones * 100) if total_zones else 0
    md += ("| Data domain | Coverage / issue | Interpretation |\n|---|---|---|\n"
           f"| Zone-device mapping | {_fmt(coverage, '%')} mapped | Share of zones with at least one mapped device relation. |\n"
           f"| Missing metadata | {len(missing):,} gaps | Items that reduce traceability or automation confidence. |\n"
           f"| Open findings | {len(findings):,} findings | Active exceptions generated from semantic graph and telemetry. |\n")
    if missing:
        md += "\nTop metadata gaps:\n"
        for m in missing[:8]:
            md += f"- **{_cell(m.get('type'))}** - {_cell(m.get('detail'), 160)}\n"
    else:
        md += "\n- All zones and devices are fully mapped in the current semantic graph.\n"

    md += ("\n## Methodology and data provenance\n\n"
           "- Scores are generated from live backend tools, not frontend mock data.\n"
           "- BPI scoring uses transparent 0-100 sub-scores: air quality, energy/demand, "
           "thermal comfort, and equipment reliability.\n"
           "- Status bands are Critical 0-59, Watch 60-79, and Good 80+; dimension targets "
           "match the dashboard cards.\n"
           "- Energy and comfort values come from counted telemetry zones at the replay anchor; "
           "semantic coverage comes from the zone-device graph.\n"
           "- This export is an operations report for triage and decision support; it is not a "
           "third-party audit certificate.\n")

    zone_rows = []
    for z in zones:
        st = zone_state.get(z["entity_key"], {})
        zone_rows.append((z, st, _num(st.get("total_power_kw"), 0)))
    zone_rows.sort(key=lambda item: item[2], reverse=True)
    md += "\n## Appendix A - Zone snapshot, top load zones\n\n"
    md += "| Zone | Type | Area m2 | Occupancy | Temp C | Load kW | Comfort |\n"
    md += "|---|---|---|---|---|---|---|\n"
    for z, st, _ in zone_rows[:18]:
        md += (f"| {_cell(z.get('name'), 56)} | {_cell(z.get('room_type'), 32)} | "
               f"{_fmt(z.get('area_m2'), '', 0)} | {_fmt(st.get('occupancy_count'), '', 0)} | "
               f"{_fmt(st.get('temperature_c'), '', 1)} | {_fmt(st.get('total_power_kw'), '', 1)} | "
               f"{_cell(st.get('comfort_risk', '-'))} |\n")

    md += "\n## Appendix B - Zone-equipment mapping sample\n\n"
    md += "| Zone | Devices |\n|---|---|\n"
    for zk, devices in list(sorted(equipment_map.items()))[:30]:
        names = ", ".join(sorted({_cell(d.get("name"), 50) for d in devices})) or "-"
        md += f"| {_cell(zk)} | {_cell(names, 180)} |\n"

    md += ("\n## EnergyPlus and simulation readiness\n\n"
           "- Geometry, constructions, schedules and internal loads are parsed from IDF inputs.\n"
           "- IdealLoadsAirSystem zone HVAC is available for baseline and counterfactual runs.\n"
           "- The report preserves source-state provenance so control decisions remain auditable.\n")

    summary_fallback = (f"The building has {b.get('zone_count', 0)} zones with "
                        f"{len(findings)} abnormal findings and "
                        f"{len(missing)} metadata gaps.")
    md += "\n## Management assessment\n\n" + llm_text(
        "Write a concise executive assessment in 3 sentences for this building operations report:\n" + md,
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
