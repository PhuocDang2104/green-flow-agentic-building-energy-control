"""Input router + intent classifier + entity resolver.

Buttons map to fixed intents. Chatbot queries are classified by keyword rules
(bilingual vi/en), optionally refined by the LLM when one is configured.
"""

from __future__ import annotations

import re

from ..llm import llm_text
from ..state import GreenFlowState
from ..tools import db_tool

BUTTON_INTENTS = {
    "run_optimization": "optimization_request",
    "building_semantic_report": "report_request",
    "hvac_elec_report": "report_request",
    "peak_strategy": "peak_strategy_query",
    "compare_baseline_optimized": "baseline_comparison_query",
    "run_prediction": "energy_query_prediction",
}

INTENTS = [
    "semantic_query", "hvac_elec_query", "energy_query", "comfort_query",
    "occupancy_query", "what_if_simulation_query", "optimization_request",
    "peak_strategy_query", "baseline_comparison_query", "report_request",
    "explain_action_query", "general_help",
]

_KEYWORD_RULES: list[tuple[str, str]] = [
    (r"what.?if|nếu .*thì|giả sử|simulate|mô phỏng|setpoint", "what_if_simulation_query"),
    (r"optimi|tối ưu", "optimization_request"),
    (r"peak|cao điểm|demand response", "peak_strategy_query"),
    (r"baseline|so sánh|compare", "baseline_comparison_query"),
    (r"report|báo cáo|pdf", "report_request"),
    (r"comfort|nhiệt độ|nóng|lạnh|temperature|humid", "comfort_query"),
    (r"occupan|người|empty|trống|vắng", "occupancy_query"),
    (r"hvac|điều hòa|đèn|light|outlet|thiết bị|device|terminal|ahu", "hvac_elec_query"),
    (r"energy|năng lượng|điện|kwh|load|công suất|cost|chi phí", "energy_query"),
    (r"why|tại sao|explain|giải thích|action", "explain_action_query"),
    (r"zone|tầng|floor|phòng|room|building|tòa nhà|vấn đề|issue|problem", "semantic_query"),
]


def run(state: GreenFlowState) -> dict:
    entrypoint = state.get("entrypoint", "chatbot")

    if entrypoint == "button":
        button = state.get("button_action") or ""
        intent = BUTTON_INTENTS.get(button, "general_help")
        # report buttons carry the concrete report type
        update: dict = {"intent": intent}
        if button in ("building_semantic_report", "hvac_elec_report"):
            update["report_type"] = button if button.endswith("report") else None
            update["report_type"] = {"building_semantic_report": "building_semantic_report",
                                     "hvac_elec_report": "hvac_elec_report"}[button]
        if button == "peak_strategy":
            update["scenario_config"] = {**state.get("scenario_config", {}),
                                         "peak_strategy": True}
        return update

    if entrypoint == "approval_resume":
        return {"intent": "approval_resume"}

    query = (state.get("user_query") or "").lower()
    intent = _classify_keywords(query)
    # Optional LLM refinement via the shared router (only when AGENT_LLM_POLISH is
    # on); llm_text returns the keyword intent unchanged otherwise -> no-op default.
    candidate = llm_text(
        "Classify this building-operations question into exactly one intent "
        f"from {INTENTS}. Reply with the intent only.\nQuestion: {query}",
        fallback=intent).strip().strip('"').lower()
    if candidate in INTENTS:
        intent = candidate

    return {"intent": intent, **_resolve_entities(state, query)}


def _classify_keywords(query: str) -> str:
    for pattern, intent in _KEYWORD_RULES:
        if re.search(pattern, query, re.IGNORECASE):
            return intent
    return "general_help"


def _resolve_entities(state: GreenFlowState, query: str) -> dict:
    """Match zone names/types mentioned in the query to entity keys."""
    zones = db_tool.get_zones(state["building_id"])
    matched: list[str] = []
    aliases = {
        "open office": "open_office", "openoffice": "open_office",
        "văn phòng mở": "open_office", "meeting": "meeting_room",
        "họp": "meeting_room", "amenity": "amenity", "tiện ích": "amenity",
        "circulation": "hallway", "hành lang": "hallway", "office": "office",
    }
    for alias, room_type in aliases.items():
        if alias in query:
            matched.extend(z["entity_key"] for z in zones
                           if z["room_type"] == room_type)
    for z in zones:
        if z["entity_key"].removeprefix("zone_storey0_").replace("_", " ") in query:
            matched.append(z["entity_key"])
    return {"selected_zone_ids": sorted(set(matched))} if matched else {}
