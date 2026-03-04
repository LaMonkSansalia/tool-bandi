"""
Pipeline Monitor — logs each scan run to DB and provides run history.

Stores run logs in a `pipeline_runs` table (created via migration 003).
Each run records: started_at, finished_at, scraped, inserted, updated,
notified, spider_failures, errors.

Usage:
    from engine.pipeline.monitor import RunMonitor

    with RunMonitor() as monitor:
        # ... pipeline tasks ...
        monitor.set_result(scraped=50, inserted=3, ...)

    # Or use directly:
    log_run(summary_dict)
    get_last_run_summary()
    get_run_history(limit=30)
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Fallback: JSON file log if DB is unavailable
LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "pipeline_runs.jsonl"


def _ensure_log_dir() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _try_db_log(run_data: dict[str, Any]) -> bool:
    """Attempt to log run to DB. Returns True on success."""
    try:
        import psycopg2
        from engine.config import DATABASE_URL

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Create table if it doesn't exist (idempotent)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id SERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ,
                duration_seconds INT,
                scraped INT DEFAULT 0,
                inserted INT DEFAULT 0,
                updated INT DEFAULT 0,
                notified INT DEFAULT 0,
                spider_failures INT DEFAULT 0,
                errors TEXT,
                spiders_run TEXT[],
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute("""
            INSERT INTO pipeline_runs
                (started_at, finished_at, duration_seconds, scraped, inserted,
                 updated, notified, spider_failures, errors, spiders_run)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            run_data.get("started_at"),
            run_data.get("finished_at"),
            run_data.get("duration_seconds"),
            run_data.get("scraped", 0),
            run_data.get("inserted", 0),
            run_data.get("updated", 0),
            run_data.get("notified", 0),
            run_data.get("spider_failures", 0),
            run_data.get("errors"),
            run_data.get("spiders_run", []),
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"DB log failed: {e}")
        return False


def _file_log(run_data: dict[str, Any]) -> None:
    """Fallback: append run data to JSONL file."""
    _ensure_log_dir()
    line = json.dumps(run_data, default=str)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_run(run_data: dict[str, Any]) -> None:
    """Log a pipeline run (DB with JSONL fallback)."""
    if not _try_db_log(run_data):
        _file_log(run_data)
        logger.info("Run logged to file (DB unavailable)")
    else:
        logger.info(f"Run logged to DB: {run_data.get('scraped', 0)} scraped")


def get_last_run_summary() -> dict[str, Any] | None:
    """Get the most recent pipeline run summary."""
    try:
        import psycopg2
        from engine.config import DATABASE_URL

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT started_at, finished_at, duration_seconds,
                   scraped, inserted, updated, notified, spider_failures, errors
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return None

        return {
            "started_at": row[0].strftime("%d/%m/%Y %H:%M") if row[0] else None,
            "finished_at": row[1].strftime("%d/%m/%Y %H:%M") if row[1] else None,
            "duration_seconds": row[2],
            "scraped": row[3],
            "inserted": row[4],
            "updated": row[5],
            "notified": row[6],
            "spider_failures": row[7],
            "errors": row[8],
        }

    except Exception as e:
        logger.warning(f"Could not load last run from DB: {e}")
        # Fallback: read last line of JSONL
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE) as f:
                    lines = f.readlines()
                if lines:
                    return json.loads(lines[-1])
            except Exception:
                pass
        return None


def get_run_history(limit: int = 30) -> list[dict[str, Any]]:
    """Get recent pipeline run history."""
    try:
        import psycopg2
        from engine.config import DATABASE_URL
        import pandas as pd

        conn = psycopg2.connect(DATABASE_URL)
        df = pd.read_sql(f"""
            SELECT started_at, duration_seconds, scraped, inserted,
                   updated, notified, spider_failures
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT {limit}
        """, conn)
        conn.close()
        return df.to_dict("records")

    except Exception as e:
        logger.warning(f"Could not load run history: {e}")
        # Fallback: JSONL file
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE) as f:
                    lines = f.readlines()[-limit:]
                return [json.loads(line) for line in reversed(lines) if line.strip()]
            except Exception:
                pass
        return []


# ─────────────────────────────────────────────
# CONTEXT MANAGER
# ─────────────────────────────────────────────

class RunMonitor:
    """
    Context manager that automatically logs pipeline run duration and results.

    Usage:
        with RunMonitor(spiders=["invitalia", ...]) as monitor:
            result = daily_scan()
            monitor.set_result(result)
    """

    def __init__(self, spiders: list[str] | None = None):
        self.spiders = spiders or []
        self.started_at = datetime.now()
        self._result: dict[str, Any] = {}
        self._errors: list[str] = []

    def set_result(self, result: dict[str, Any]) -> None:
        self._result = result

    def add_error(self, error: str) -> None:
        self._errors.append(error)

    def __enter__(self) -> "RunMonitor":
        logger.info(f"Pipeline run started at {self.started_at.isoformat()}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        finished_at = datetime.now()
        duration = int((finished_at - self.started_at).total_seconds())

        if exc_val:
            self._errors.append(str(exc_val))

        run_data = {
            "started_at": self.started_at,
            "finished_at": finished_at,
            "duration_seconds": duration,
            "scraped": self._result.get("scraped", 0),
            "inserted": self._result.get("inserted", 0),
            "updated": self._result.get("updated", 0),
            "notified": self._result.get("notified", 0),
            "spider_failures": self._result.get("spider_failures", 0),
            "errors": "; ".join(self._errors) if self._errors else None,
            "spiders_run": self.spiders,
        }

        log_run(run_data)

        if exc_type:
            logger.error(f"Pipeline run failed after {duration}s: {exc_val}")
            return False  # re-raise exception

        logger.info(
            f"Pipeline run complete in {duration}s: "
            f"scraped={run_data['scraped']}, inserted={run_data['inserted']}"
        )
        return False
