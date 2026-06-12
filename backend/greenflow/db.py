"""Database access: synchronous SQLAlchemy Core engine + helpers.

Sync + psycopg keeps scripts and FastAPI simple (FastAPI runs sync routes in
a threadpool). All queries are written against the schema in db/schema.sql.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from .config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True,
                                pool_size=5, max_overflow=10)
    return _engine


@contextmanager
def db_conn() -> Iterator[Connection]:
    with get_engine().begin() as conn:
        yield conn


def fetch_all(conn: Connection, sql: str, **params: Any) -> list[dict]:
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def fetch_one(conn: Connection, sql: str, **params: Any) -> dict | None:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def execute(conn: Connection, sql: str, **params: Any) -> None:
    conn.execute(text(sql), params)
