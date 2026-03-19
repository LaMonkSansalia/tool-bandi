"""
FastAPI dependencies — DB connection, current project, templates.
"""
from __future__ import annotations
from typing import Generator

from fastapi import Request
from psycopg2.extras import RealDictCursor

from engine.db.pool import get_conn, put_conn

DEFAULT_PROJECT_ID = 1


def get_db() -> Generator:
    """Yield a DB connection from pool, return it after use."""
    conn = get_conn()
    try:
        yield conn
    finally:
        put_conn(conn)


def get_current_project_id(request: Request) -> int:
    """Read current_project_id from session, default to 1."""
    return request.session.get("current_project_id", DEFAULT_PROJECT_ID)


def get_nav_context(request: Request, conn) -> dict:
    """
    Build navigation context shared by all pages.
    No global project switcher — project context is per-page.
    """
    return {}


def get_all_projects(conn) -> list[dict]:
    """Fetch active projects for per-page selectors (bandi list, etc.)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, slug, nome, descrizione_breve
            FROM projects WHERE attivo = TRUE
            ORDER BY nome
        """)
        return [dict(r) for r in cur.fetchall()]
