"""
Dashboard route — 4 stat cards + scadenze imminenti.
Ported from tool-bandi-ui/apps/core/views.py
"""
from fastapi import APIRouter, Depends, Request
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_current_project_id, get_nav_context
from web.main import templates
from web.services.display import enrich_bando_row

router = APIRouter()


@router.get("/")
def dashboard(request: Request, conn=Depends(get_db)):
    pid = get_current_project_id(request)
    nav = get_nav_context(request, conn)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Card 1: Idonei da valutare
        cur.execute(
            "SELECT COUNT(*) AS n FROM project_evaluations WHERE project_id = %s AND stato = 'idoneo'",
            (pid,),
        )
        count_idonei = cur.fetchone()["n"]

        # Card 2: Scadono in 14gg
        cur.execute("""
            SELECT COUNT(*) AS n FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.project_id = %s
              AND pe.stato IN ('idoneo', 'lavorazione')
              AND b.data_scadenza BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
        """, (pid,))
        count_scadono_14 = cur.fetchone()["n"]

        # Card 3: In lavorazione
        cur.execute(
            "SELECT COUNT(*) AS n FROM project_evaluations WHERE project_id = %s AND stato = 'lavorazione'",
            (pid,),
        )
        count_lavorazione = cur.fetchone()["n"]

        # Card 4: Ultima scansione
        cur.execute("SELECT started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        ultima_scansione = row["started_at"] if row else None

        # Tabella scadenze imminenti
        cur.execute("""
            SELECT pe.id AS pe_id, pe.score, pe.stato,
                   b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                   (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.project_id = %s
              AND pe.stato IN ('idoneo', 'lavorazione')
              AND b.data_scadenza BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            ORDER BY b.data_scadenza ASC
            LIMIT 15
        """, (pid,))
        scadenze = [enrich_bando_row(dict(r)) for r in cur.fetchall()]

    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        **nav,
        "active_page": "dashboard",
        "count_idonei": count_idonei,
        "count_scadono_14": count_scadono_14,
        "count_lavorazione": count_lavorazione,
        "ultima_scansione": ultima_scansione,
        "scadenze": scadenze,
    })


@router.get("/switch-project")
def switch_project(request: Request, project_id: int, conn=Depends(get_db)):
    """Change current project in session."""
    from fastapi.responses import RedirectResponse

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM projects WHERE id = %s AND attivo = TRUE", (project_id,))
        if cur.fetchone():
            request.session["current_project_id"] = project_id

    next_url = request.query_params.get("next", "/")
    return RedirectResponse(url=next_url, status_code=303)
