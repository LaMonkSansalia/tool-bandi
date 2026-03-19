"""
Dashboard route — 4 stat cards + scadenze imminenti.
Ported from tool-bandi-ui/apps/core/views.py
"""
from fastapi import APIRouter, Depends, Request
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context
from web.main import templates
from web.services.display import enrich_bando_row

router = APIRouter()


@router.get("/")
def dashboard(request: Request, conn=Depends(get_db)):
    nav = get_nav_context(request, conn)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Card 1: Bandi totali monitorati
        cur.execute("SELECT COUNT(*) AS n FROM bandi")
        count_bandi = cur.fetchone()["n"]

        # Card 2: Idonei (tutti i progetti)
        cur.execute("SELECT COUNT(*) AS n FROM project_evaluations WHERE stato = 'idoneo'")
        count_idonei = cur.fetchone()["n"]

        # Card 3: In lavorazione (tutti i progetti)
        cur.execute("SELECT COUNT(*) AS n FROM project_evaluations WHERE stato = 'lavorazione'")
        count_lavorazione = cur.fetchone()["n"]

        # Card 4: Scadono in 14gg (tutti i progetti)
        cur.execute("""
            SELECT COUNT(*) AS n FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.stato IN ('idoneo', 'lavorazione')
              AND b.data_scadenza BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
        """)
        count_scadono_14 = cur.fetchone()["n"]

        # Card 5: Ultima scansione
        cur.execute("SELECT started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        ultima_scansione = row["started_at"] if row else None

        # Card 6: Progetti attivi
        cur.execute("SELECT COUNT(*) AS n FROM projects WHERE attivo = TRUE")
        count_progetti = cur.fetchone()["n"]

        # Card 7: Soggetti
        cur.execute("SELECT COUNT(*) AS n FROM soggetti WHERE COALESCE(profilo->>'tipo', 'reale') = 'reale'")
        count_soggetti = cur.fetchone()["n"]

        # Tabella scadenze imminenti (trasversale)
        cur.execute("""
            SELECT pe.id AS pe_id, pe.score, pe.stato,
                   b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                   (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti,
                   p.nome AS progetto_nome
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            JOIN projects p ON pe.project_id = p.id
            WHERE pe.stato IN ('idoneo', 'lavorazione')
              AND b.data_scadenza BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            ORDER BY b.data_scadenza ASC
            LIMIT 15
        """)
        scadenze = [enrich_bando_row(dict(r)) for r in cur.fetchall()]

        # Nuovi bandi ultimi 7 giorni
        cur.execute("""
            SELECT COUNT(*) AS n FROM bandi
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        count_nuovi_7gg = cur.fetchone()["n"]

    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        **nav,
        "active_page": "dashboard",
        "count_bandi": count_bandi,
        "count_idonei": count_idonei,
        "count_lavorazione": count_lavorazione,
        "count_scadono_14": count_scadono_14,
        "ultima_scansione": ultima_scansione,
        "count_progetti": count_progetti,
        "count_soggetti": count_soggetti,
        "count_nuovi_7gg": count_nuovi_7gg,
        "scadenze": scadenze,
    })


