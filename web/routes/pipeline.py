"""
Pipeline routes — log view + trigger scan.
Ported from tool-bandi-ui/apps/pipeline/views.py
"""
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context
from web.main import templates

router = APIRouter(prefix="/pipeline")


@router.get("")
def pipeline_log(request: Request, conn=Depends(get_db)):
    """Pipeline run history — last 20 runs."""
    nav = get_nav_context(request, conn)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, started_at, finished_at, duration_seconds,
                   scraped, inserted, updated, notified,
                   spider_failures, errors, spiders_run
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 20
        """)
        runs = []
        for r in cur.fetchall():
            row = dict(r)
            row["successo"] = (row.get("spider_failures") or 0) == 0
            row["totale_bandi"] = (row.get("inserted") or 0) + (row.get("updated") or 0)
            runs.append(row)

    triggered = request.query_params.get("triggered", "")

    return templates.TemplateResponse("pages/pipeline.html", {
        "request": request,
        **nav,
        "active_page": "pipeline",
        "runs": runs,
        "triggered": triggered,
    })


@router.post("/trigger")
def trigger_scan(request: Request):
    """Trigger daily_scan in background thread."""
    def _run():
        try:
            from engine.pipeline.flows import daily_scan
            daily_scan()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return RedirectResponse(url="/pipeline?triggered=1", status_code=303)
