"""Agent narrates what was notable — after each run and on a periodic monitor
cycle — as an assistant chat message, so the conversation doubles as an ops log.

Deterministic templates (no LLM in the path) so reports are reliable; the run
already carries the findings/actions, the monitor cycle scans open faults.
"""
from __future__ import annotations

from datetime import timedelta

from ..db import db_conn, fetch_all, fetch_one

MONITOR_SESSION_TITLE = "🛰 Agent monitor"


def _fmt_finding(f) -> str:
    if isinstance(f, dict):
        for k in ("message", "description", "label", "summary", "reason"):
            if f.get(k):
                tag = " · ".join(str(x) for x in (f.get("severity"),
                      f.get("zone") or f.get("zone_key") or f.get("zone_name")) if x)
                return f"{f[k]}" + (f" ({tag})" if tag else "")
        return str(f)
    return str(f)


def _fmt_action(a) -> str:
    if not isinstance(a, dict):
        return str(a)
    bits = [str(a.get("action_type") or a.get("type") or "action")]
    z = a.get("zone") or a.get("zone_key") or a.get("target_id")
    if z:
        bits.append(str(z))
    s = " · ".join(bits)
    save = a.get("expected_saving_kwh")
    if save:
        try:
            s += f" (~{float(save):.1f} kWh)"
        except (TypeError, ValueError):
            pass
    why = a.get("reason") or a.get("explanation")
    if why:
        s += f" — {why}"
    return s


def build_run_report(final: dict) -> str:
    intent = (final.get("intent") or final.get("button_action") or "analysis")
    lines = [f"**Session report — {str(intent).replace('_', ' ')}**"]
    fa = (final.get("final_answer") or "").strip()
    if fa:
        lines.append(fa)
    findings = final.get("abnormal_findings") or []
    if findings:
        lines.append(f"\n⚠️ {len(findings)} notable finding(s):")
        lines += [f"- {_fmt_finding(f)}" for f in findings[:5]]
    plan = final.get("final_action_plan") or final.get("candidate_actions") or []
    if plan:
        lines.append(f"\n🔧 {len(plan)} action(s) proposed:")
        lines += [f"- {_fmt_action(a)}" for a in plan[:5]]
    else:
        lines.append("\nNo control actions were needed.")
    return "\n".join(lines)


def build_monitor_report(conn, building_id: str, now) -> str | None:
    """Open-fault digest for the periodic monitor; None = nothing notable."""
    rows = fetch_all(conn, """
        SELECT severity, message FROM alerts
        WHERE building_id = :b AND resolved_at IS NULL
        ORDER BY created_at DESC LIMIT 8
    """, b=building_id)
    if not rows:
        return None
    by_sev: dict[str, int] = {}
    for r in rows:
        by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
    head = ", ".join(f"{n} {s}" for s, n in by_sev.items())
    t = now.strftime("%a %d/%m %H:%M") if hasattr(now, "strftime") else str(now)
    lines = [f"**Monitor — {t}**", f"{len(rows)} open fault(s): {head}."]
    lines += [f"- {r['message']}" for r in rows[:5]]
    return "\n".join(lines)


def _post(conn, building_id: str, session_id: str, text: str) -> None:
    from ..chat.service import _ensure_session, _save_message  # lazy: avoid import cycle
    sid = _ensure_session(conn, session_id, building_id)
    _save_message(conn, sid, "assistant", text)


def post_run_report(building_id: str, session_id: str, final: dict) -> None:
    """Best-effort: narrate a finished run into its chat session."""
    try:
        with db_conn() as conn:
            _post(conn, building_id, session_id, build_run_report(final))
    except Exception:
        pass  # a report must never break the run


def get_or_create_monitor_session(conn, building_id: str) -> str:
    row = fetch_one(conn, """
        SELECT id FROM chat_sessions WHERE building_id = :b AND title = :t
        ORDER BY created_at LIMIT 1
    """, b=building_id, t=MONITOR_SESSION_TITLE)
    if row:
        return str(row["id"])
    row = fetch_one(conn, """
        INSERT INTO chat_sessions (building_id, title) VALUES (:b, :t) RETURNING id
    """, b=building_id, t=MONITOR_SESSION_TITLE)
    return str(row["id"])


def run_monitor_cycle(building_id: str) -> bool:
    """Scan anomalies and, if anything is open, post a digest to the monitor
    session. Returns True if a report was posted."""
    from .anomaly import scan_anomalies
    from ..replayclock import anchor
    try:
        with db_conn() as conn:
            now = anchor(conn, building_id)
            scan_anomalies(conn, building_id, now - timedelta(hours=24), now)
            report = build_monitor_report(conn, building_id, now)
            if not report:
                return False
            sid = get_or_create_monitor_session(conn, building_id)
            from ..chat.service import _save_message
            _save_message(conn, sid, "assistant", report)
            return True
    except Exception:
        return False
