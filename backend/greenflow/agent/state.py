"""Shared GreenFlowState used by every node in the orchestration graph.

Mirrors the LangGraph Orchestration Blueprint §5.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


class GreenFlowState(TypedDict, total=False):
    # Request context
    request_id: str
    user_id: str
    building_id: str
    session_id: str
    entrypoint: Literal["chatbot", "button", "approval_resume"]

    # User input
    user_query: Optional[str]
    button_action: Optional[str]
    selected_floor_id: Optional[str]
    selected_zone_ids: list[str]
    selected_device_ids: list[str]
    scenario_config: dict

    # Intent and plan
    intent: Optional[str]
    orchestration_plan: list[dict]
    current_plan_step: int

    # Building semantic context
    building_summary: dict
    floors: list[dict]
    zones: list[dict]
    zone_equipment_map: dict
    semantic_context: dict
    abnormal_findings: list[dict]
    missing_metadata: list[dict]

    # Dynamic state
    latest_zone_state: dict
    latest_device_state: dict
    occupancy_state: dict
    weather_state: dict
    baseline_state: dict

    # Prediction
    forecast_horizon_minutes: int
    forecast_result: dict
    comfort_risk: dict
    peak_risk: dict
    demand_forecast: dict  # day-ahead 24h HVAC demand + pre-cool recommendation
    forecast_confidence: float
    prediction_explanation: dict

    # Control
    candidate_actions: list[dict]
    ranked_actions: list[dict]
    selected_actions: list[dict]
    final_action_plan: list[dict]

    # Simulation
    simulation_result: dict
    baseline_vs_action: dict
    baseline_vs_optimized: dict

    # Policy / approval
    policy_decisions: list[dict]
    approval_required: bool
    approval_requests: list[dict]
    human_decision: Optional[dict]

    # Execution
    execution_result: dict

    # Report / response
    report_type: Optional[str]
    report_markdown: Optional[str]
    pdf_path: Optional[str]
    report_id: Optional[str]
    dashboard_cards: list[dict]
    viewer_updates: list[dict]
    final_answer: str
    related_entities: list[dict]
    suggested_buttons: list[str]

    # Observability
    run_id: str
    agent_logs: list[dict]
    errors: list[dict]


def new_state(**kwargs: Any) -> GreenFlowState:
    state: GreenFlowState = {
        "selected_zone_ids": [],
        "selected_device_ids": [],
        "scenario_config": {},
        "orchestration_plan": [],
        "current_plan_step": 0,
        "abnormal_findings": [],
        "missing_metadata": [],
        "candidate_actions": [],
        "ranked_actions": [],
        "selected_actions": [],
        "final_action_plan": [],
        "policy_decisions": [],
        "approval_requests": [],
        "approval_required": False,
        "dashboard_cards": [],
        "viewer_updates": [],
        "related_entities": [],
        "suggested_buttons": [],
        "agent_logs": [],
        "errors": [],
        "forecast_horizon_minutes": 60,
        "final_answer": "",
    }
    state.update(kwargs)  # type: ignore[typeddict-item]
    return state
