"""Approval-list query construction tests (no DB, no network)."""

from contextlib import contextmanager
from uuid import uuid4

from greenflow.api.routers import actions


def _capture_query(monkeypatch):
    captured = {}

    @contextmanager
    def fake_db_conn():
        yield object()

    def fake_fetch_all(_conn, sql, **params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(actions, "db_conn", fake_db_conn)
    monkeypatch.setattr(actions, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(actions, "_expire_stale_approvals", lambda _conn: None)
    return captured


def test_list_approvals_omits_optional_run_filter(monkeypatch):
    captured = _capture_query(monkeypatch)

    assert actions.list_approvals("building-1", "pending", None) == []
    assert "agent_run_id = :run_id" not in captured["sql"]
    assert "run_id" not in captured["params"]


def test_list_approvals_filters_by_run_when_provided(monkeypatch):
    captured = _capture_query(monkeypatch)
    run_id = uuid4()

    assert actions.list_approvals("building-1", "pending", run_id) == []
    assert "agent_run_id = :run_id" in captured["sql"]
    assert captured["params"]["run_id"] == run_id
