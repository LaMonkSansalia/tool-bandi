"""
Pipeline routes — log view + trigger scan.
Ported from tool-bandi-ui/apps/pipeline/views.py
"""
import logging
import threading
import traceback

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context
from web.main import templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline")


@router.get("")
def pipeline_log(request: Request, conn=Depends(get_db)):
    """Pipeline run history — last 20 runs."""
    nav = get_nav_context(request, conn)

    runs = []
    pipeline_error = ""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, started_at, finished_at, duration_seconds,
                       scraped, inserted, updated, notified,
                       spider_failures, errors, spiders_run
                FROM pipeline_runs
                ORDER BY started_at DESC
                LIMIT 20
            """)
            for r in cur.fetchall():
                row = dict(r)
                row["successo"] = (row.get("spider_failures") or 0) == 0
                row["totale_bandi"] = (row.get("inserted") or 0) + (row.get("updated") or 0)
                runs.append(row)
    except Exception as e:
        logger.warning("pipeline_runs query failed: %s", e)
        pipeline_error = f"Tabella pipeline_runs non disponibile: {e}"
        # Rollback to clean up the failed transaction
        try:
            conn.rollback()
        except Exception:
            pass

    triggered = request.query_params.get("triggered", "")
    trigger_error = request.query_params.get("trigger_error", "")

    return templates.TemplateResponse("pages/pipeline.html", {
        "request": request,
        **nav,
        "active_page": "pipeline",
        "runs": runs,
        "triggered": triggered,
        "pipeline_error": pipeline_error,
        "trigger_error": trigger_error,
    })


# Store last trigger error for display
_last_trigger_error: str = ""


@router.post("/trigger")
def trigger_scan(request: Request):
    """Trigger daily_scan in background thread."""
    def _run():
        global _last_trigger_error
        try:
            from engine.pipeline.flows import daily_scan
            daily_scan()
            _last_trigger_error = ""
        except ImportError as e:
            _last_trigger_error = f"Dipendenza mancante: {e}"
            logger.error("Pipeline import error: %s", e)
        except Exception as e:
            _last_trigger_error = str(e)[:200]
            logger.error("Pipeline error: %s\n%s", e, traceback.format_exc())

    threading.Thread(target=_run, daemon=True).start()
    return RedirectResponse(url="/pipeline?triggered=1", status_code=303)
