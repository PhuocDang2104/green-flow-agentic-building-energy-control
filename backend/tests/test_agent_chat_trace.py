"""Persistence contract for agent runs embedded in chat history."""

import json
from contextlib import contextmanager

from greenflow.agent import service


class FakeConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params):
        self.statements.append((str(statement), params))


def test_start_run_persists_chat_trace_event_atomically(monkeypatch):
    conn = FakeConnection()

    @contextmanager
    def fake_db_conn():
        yield conn

    monkeypatch.setattr(service, "db_conn", fake_db_conn)

    run_id = service.start_run(
        "building-1",
        "button",
        button_action="run_prediction",
        session_id="session-1",
    )

    assert len(conn.statements) == 2
    assert conn.statements[0][1]["id"] == run_id
    message = conn.statements[1][1]
    assert message["session"] == "session-1"
    assert message["content"] == "Started **Run Prediction**."
    tools = json.loads(message["tools"])
    assert tools[0]["name"] == "trigger_agent_action"
    assert tools[0]["result"]["run_id"] == run_id


def test_start_run_without_session_does_not_create_chat_event(monkeypatch):
    conn = FakeConnection()

    @contextmanager
    def fake_db_conn():
        yield conn

    monkeypatch.setattr(service, "db_conn", fake_db_conn)

    service.start_run("building-1", "button", button_action="run_prediction")

    assert len(conn.statements) == 1
