"""
Connection pool singleton — shared across web routes and engine modules.
Uses psycopg2 ThreadedConnectionPool for thread-safe access.
"""
from __future__ import annotations
import logging

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from engine.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None


def init_pool(minconn: int = 2, maxconn: int = 10) -> None:
    """Initialize the global connection pool. Call once at app startup."""
    global _pool
    if _pool is not None:
        return
    _pool = ThreadedConnectionPool(minconn, maxconn, DATABASE_URL)
    logger.info(f"DB pool initialized (min={minconn}, max={maxconn})")


def close_pool() -> None:
    """Close the pool. Call at app shutdown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("DB pool closed")


def get_conn():
    """
    Get a connection from the pool.
    Usage:
        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(...)
                rows = cur.fetchall()
            conn.commit()
        finally:
            put_conn(conn)
    """
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() first")
    return _pool.getconn()


def put_conn(conn) -> None:
    """Return a connection to the pool."""
    if _pool is not None:
        _pool.putconn(conn)
