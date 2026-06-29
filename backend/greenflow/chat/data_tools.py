"""Tools truy vấn LỊCH SỬ tòa nhà + kích hành động agent thật cho LLM gọi
(function-calling).

Nguyên tắc an toàn: LLM KHÔNG sinh SQL tự do. Mỗi tool đọc dữ liệu là 1 query
THAM SỐ HOÁ cố định, chỉ nhận tham số có kiểu/whitelist -> không injection,
không quét bậy. LLM chỉ chọn tool + điền tham số; thực thi là code này.

Tool `trigger_agent_action` là ngoại lệ duy nhất có side-effect: nó chỉ được
phép khởi chạy 1 trong 3 button_action cố định (whitelist, giống hệt workflow
nút bấm ở trang Agents & Actions) — không tự ý chạy gì khác. Action thật vẫn
phải qua simulation + policy gate như mọi nơi khác, chat không bypass audit.

"Bây giờ" = replay clock = max(timestamp) trong telemetry (dữ liệu là quá khứ).
"""
from __future__ import annotations

import difflib
import threading

from greenflow.agent import service as agent_service
from greenflow.db import fetch_all, fetch_one
from greenflow.energy_scope import counted_zone_sql

WINDOW_INTERVAL = {"day": "1 day", "week": "7 days", "month": "30 days"}
ZONE_METRICS = {"total_power_kw", "hvac_power_kw", "lighting_power_kw",
                "temperature_c", "co2_ppm", "occupancy_count", "cost_vnd"}


def _not_found(kind: str, value: str, options: list[str]) -> dict:
    """Self-describing tool error (slide §Tools: a good error helps the agent
    recover). Tells the LLM exactly what was wrong, a likely correction, and the
    valid options — so the next tool call can fix itself instead of looping."""
    out: dict = {"error": f"{kind} '{value}' not found", "available": options[:30]}
    close = difflib.get_close_matches(str(value), [str(o) for o in options], n=1)
    if close:
        out["hint"] = f"did you mean '{close[0]}'?"
    return out


def _zone_keys(conn, building_id) -> list[str]:
    return [r["entity_key"] for r in fetch_all(
        conn, "SELECT entity_key FROM zones WHERE building_id = :b ORDER BY entity_key",
        b=building_id)]


def _now(conn, building_id):
    from greenflow.replayclock import anchor
    return anchor(conn, building_id)


def get_building_kpi(conn, building_id, window: str = "day") -> dict:
    """KPI for a window. "day" = calendar-day-to-date ("today"), the SAME source
    the dashboard uses, so Copilot and the dashboard never disagree (QC-01).
    "week"/"month" are rolling look-backs, labelled as such to avoid confusion."""
    from greenflow.agent.tools.timeseries_tool import get_today_energy
    if window not in WINDOW_INTERVAL:
        return _not_found("window", window, list(WINDOW_INTERVAL))
    now = _now(conn, building_id)
    if now is None:
        return {"error": "no data"}

    if window == "day":
        period, window_sql = "today", "timestamp::date = (:now)::date"
    else:
        iv = WINDOW_INTERVAL.get(window, "7 days")
        period = {"week": "last 7 days", "month": "last 30 days"}.get(window, window)
        window_sql = "timestamp > :now - interval '" + iv + "' AND timestamp <= :now"

    row = fetch_one(conn, f"""
        WITH w AS (SELECT t.* FROM telemetry_zone_15m t
                   JOIN zones z ON z.id = t.zone_id
                   WHERE t.building_id = :b AND {counted_zone_sql('z')} AND {window_sql}),
             peak AS (SELECT timestamp, sum(total_power_kw) kw FROM w GROUP BY 1)
        SELECT round(sum(energy_kwh)::numeric,1) energy_kwh,
               round(sum(cost_vnd)::numeric,0) cost_vnd,
               (SELECT round(max(kw)::numeric,1) FROM peak) peak_kw,
               count(*) FILTER (WHERE comfort_risk = 'high') high_comfort_rows
        FROM w""", b=building_id, now=now) or {}
    out = {"window": window, "period": period, "as_of": str(now),
           **{k: float(v) if v is not None else None for k, v in row.items()}}
    if window == "day":
        # energy/cost from the shared source of truth -> identical to dashboard
        e = get_today_energy(conn, building_id, now)
        out["energy_kwh"] = round(e["kwh"], 1)
        out["cost_vnd"] = round(e["cost"], 0)
    return out


def get_zone_timeseries(conn, building_id, zone_key: str, metric: str = "total_power_kw",
                        hours: int = 6) -> dict:
    if metric not in ZONE_METRICS:
        return _not_found("metric", metric, sorted(ZONE_METRICS))
    keys = _zone_keys(conn, building_id)
    if zone_key not in keys:
        return _not_found("zone", zone_key, keys)
    now = _now(conn, building_id)
    rows = fetch_all(conn, f"""
        SELECT timestamp AS ts, {metric} AS value FROM telemetry_zone_15m
        WHERE building_id = :b AND zone_id = (SELECT id FROM zones WHERE entity_key = :zk)
          AND timestamp > :now - interval '{int(hours)} hours' AND timestamp <= :now
        ORDER BY timestamp""", b=building_id, zk=zone_key, now=now)
    return {"zone_key": zone_key, "metric": metric, "hours": hours,
            "points": [{"ts": str(r["ts"]), "value": float(r["value"] or 0)} for r in rows]}


def get_top_consumers(conn, building_id, window: str = "day", limit: int = 5) -> dict:
    if window not in WINDOW_INTERVAL:
        return _not_found("window", window, list(WINDOW_INTERVAL))
    iv = WINDOW_INTERVAL.get(window, "1 day")
    now = _now(conn, building_id)
    rows = fetch_all(conn, f"""
        SELECT z.entity_key, z.name, round(sum(t.energy_kwh)::numeric,1) energy_kwh
        FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
        WHERE t.building_id = :b AND t.timestamp > :now - interval '{iv}'
          AND t.timestamp <= :now AND {counted_zone_sql('z')}
        GROUP BY z.entity_key, z.name ORDER BY energy_kwh DESC LIMIT :lim""",
        b=building_id, now=now, lim=int(limit))
    return {"window": window, "top": [dict(r) | {"energy_kwh": float(r["energy_kwh"])}
            for r in rows]}


def get_alerts(conn, building_id, status: str = "open") -> dict:
    if status not in ("open", "resolved"):
        return _not_found("status", status, ["open", "resolved"])
    cond = "resolved_at IS NULL" if status == "open" else "resolved_at IS NOT NULL"
    rows = fetch_all(conn, f"""
        SELECT a.alert_type, a.severity, a.message, a.created_at, z.name zone
        FROM alerts a LEFT JOIN zones z ON z.id = a.zone_id
        WHERE a.building_id = :b AND {cond}
        ORDER BY a.created_at DESC LIMIT 20""", b=building_id)
    return {"status": status, "alerts": [dict(r) | {"created_at": str(r["created_at"])}
            for r in rows]}


def list_zones(conn, building_id) -> dict:
    rows = fetch_all(conn, """
        SELECT entity_key, name, room_type, round(area_m2::numeric,1) area_m2,
               energy_scope, counts_toward_energy, scope_reason
        FROM zones WHERE building_id = :b ORDER BY name""", b=building_id)
    return {"zones": [dict(r) for r in rows]}


def search_system_docs(conn, building_id, query: str, limit: int = 5) -> dict:
    """Search GreenFlow's own documentation — architecture and how each metric /
    index is computed, capabilities, anomaly rules, the agent loop. Lexical
    full-text over the knowledge base (the always-on RAG adds dense matches on
    top); use for 'how does the system work / how is X computed' questions."""
    try:
        n = max(1, min(8, int(limit)))
    except (TypeError, ValueError):
        n = 5
    rows = fetch_all(conn, """
        SELECT title, content FROM kb_chunks
        WHERE to_tsvector('simple', coalesce(title,'') || ' ' || content)
              @@ websearch_to_tsquery('simple', :q)
        ORDER BY ts_rank(
            to_tsvector('simple', coalesce(title,'') || ' ' || content),
            websearch_to_tsquery('simple', :q)) DESC
        LIMIT :n""", q=query, n=n)
    if not rows:  # no lexical hit → fall back to the system overview so the model has grounding
        rows = fetch_all(conn, """
            SELECT title, content FROM kb_chunks WHERE doc_type = 'system'
            ORDER BY id LIMIT :n""", n=n)
    return {"query": query, "docs": [dict(r) for r in rows]}


ACTION_BUTTONS = {"run_optimization", "peak_strategy", "run_prediction"}


def trigger_agent_action(conn, building_id, action: str) -> dict:
    """Start a real LangGraph run (whitelisted button_action) in the
    background; mirrors the dashboard buttons exactly, including
    simulation + policy gate. Returns immediately with a run_id the
    frontend polls (/agent/runs/{id}, /agent/runs/{id}/logs) for live
    step-by-step progress — this tool never blocks the chat request."""
    if action not in ACTION_BUTTONS:
        return {"error": f"action must be one of {sorted(ACTION_BUTTONS)}"}
    run_id = agent_service.start_run(building_id, "button", button_action=action)
    thread = threading.Thread(
        target=agent_service.execute_run,
        args=(run_id, building_id, "button"),
        kwargs={"button_action": action},
        daemon=True)
    thread.start()
    return {"run_id": run_id, "status": "running", "action": action,
            "note": "Run started; poll /agent/runs/{run_id} and "
                    "/agent/runs/{run_id}/logs for live progress."}


# OpenAI/Groq function-calling schemas
TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "get_building_kpi",
        "description": "Total energy (kWh), cost (VND), peak power (kW) and comfort issues for a recent window.",
        "parameters": {"type": "object", "properties": {
            "window": {"type": "string", "enum": ["day", "week", "month"]}}, "required": ["window"]}}},
    {"type": "function", "function": {
        "name": "get_zone_timeseries",
        "description": "Recent time-series of one metric for one zone (by entity_key).",
        "parameters": {"type": "object", "properties": {
            "zone_key": {"type": "string"},
            "metric": {"type": "string", "enum": sorted(ZONE_METRICS)},
            # ["integer","string"]: vài model emit số dạng string -> Groq validate chặt;
            # nhận cả hai rồi int() coerce trong hàm.
            "hours": {"type": ["integer", "string"]}}, "required": ["zone_key", "metric"]}}},
    {"type": "function", "function": {
        "name": "get_top_consumers",
        "description": "Zones using the most energy in a window.",
        "parameters": {"type": "object", "properties": {
            "window": {"type": "string", "enum": ["day", "week", "month"]},
            "limit": {"type": ["integer", "string"]}}, "required": ["window"]}}},
    {"type": "function", "function": {
        "name": "get_alerts",
        "description": "Current building alerts (anomalies, faults).",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["open", "resolved"]}}}}},
    {"type": "function", "function": {
        "name": "list_zones",
        "description": "List zones with name, room type, area.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "search_system_docs",
        "description": (
            "Search GreenFlow's OWN documentation: how the system is built and how a metric or "
            "index is computed (e.g. how the Air Quality score, Building Health score, comfort, "
            "EUI, or cost is calculated), what the product can do, the anomaly rules, the agent "
            "loop, and the policy gate. Use this for questions about how the SYSTEM works or how "
            "a number is derived. For the live building's actual values use the data tools "
            "(get_building_kpi, get_alerts, etc.) instead."),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "trigger_agent_action",
        "description": (
            "Start a REAL agentic workflow run in the background — only call this when the "
            "user explicitly asks to run/start/trigger something, never just to answer a "
            "question. run_optimization: full optimize (predict->control->simulate->policy-> "
            "execute). peak_strategy: pre-cool/peak-shaving strategy for the afternoon peak. "
            "run_prediction: short-horizon forecast only, no actions. Returns a run_id "
            "immediately; the run itself takes a few seconds and is shown to the user as live "
            "step-by-step progress, so do not wait for it — just confirm you started it."),
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": sorted(ACTION_BUTTONS)}},
            "required": ["action"]}}},
]

_DISPATCH = {"get_building_kpi": get_building_kpi, "get_zone_timeseries": get_zone_timeseries,
             "get_top_consumers": get_top_consumers, "get_alerts": get_alerts,
             "list_zones": list_zones, "trigger_agent_action": trigger_agent_action,
             "search_system_docs": search_system_docs}


def dispatch(name: str, args: dict, conn, building_id) -> dict:
    # KHÔNG nuốt lỗi ở đây: để service bọc savepoint (begin_nested) -> lỗi 1 tool
    # rollback savepoint, không phá transaction đang lưu lịch sử chat.
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    return fn(conn, building_id, **args)
