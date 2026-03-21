"""
Dashboard route — stat cards + scadenze imminenti + blocchi aggiuntivi §5.1.
Ported from tool-bandi-ui/apps/core/views.py
"""
import json

from fastapi import APIRouter, Depends, Request
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context
from web.main import templates
from web.services.display import enrich_bando_row
from web.services.completezza import normalize_profilo, check_completezza

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

        # ── Blocchi aggiuntivi §5.1 ──

        # Candidature per stato (tutti i progetti)
        cur.execute("""
            SELECT stato, COUNT(*) AS n
            FROM project_evaluations
            WHERE stato NOT IN ('nuovo', 'archiviato')
            GROUP BY stato
            ORDER BY n DESC
        """)
        candidature_per_stato = {r["stato"]: r["n"] for r in cur.fetchall()}

        # Nuovi bandi (ultimi 10)
        cur.execute("""
            SELECT id, titolo, ente_erogatore, created_at
            FROM bandi
            ORDER BY created_at DESC
            LIMIT 10
        """)
        nuovi_bandi = [dict(r) for r in cur.fetchall()]

        # Progetti incompleti (completezza < 75%)
        cur.execute("""
            SELECT id, nome, profilo FROM projects WHERE attivo = TRUE
        """)
        all_projects = [dict(r) for r in cur.fetchall()]

        progetti_incompleti = []
        for p in all_projects:
            profilo = normalize_profilo(p.get("profilo"))
            _, _, pct = check_completezza(profilo)
            if pct < 75:
                progetti_incompleti.append({
                    "id": p["id"], "nome": p["nome"], "completezza_pct": pct,
                })
        progetti_incompleti.sort(key=lambda x: x["completezza_pct"])

        # Hard stop piu' impattanti (tutti i soggetti)
        cur.execute("""
            SELECT pe.hard_stop_reason AS label,
                   COUNT(DISTINCT pe.bando_id) AS bandi_bloccati,
                   COUNT(DISTINCT p.soggetto_id) AS soggetti_impattati
            FROM project_evaluations pe
            JOIN projects p ON pe.project_id = p.id
            WHERE pe.hard_stop_reason IS NOT NULL
              AND pe.hard_stop_reason != ''
            GROUP BY pe.hard_stop_reason
            ORDER BY bandi_bloccati DESC
            LIMIT 10
        """)
        hard_stops_top = [dict(r) for r in cur.fetchall()]

        # Timeline attivita' (ultime 15 valutazioni)
        cur.execute("""
            SELECT pe.stato, pe.score, pe.updated_at,
                   b.titolo, p.nome AS progetto_nome
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            JOIN projects p ON pe.project_id = p.id
            WHERE pe.updated_at IS NOT NULL
            ORDER BY pe.updated_at DESC
            LIMIT 15
        """)
        timeline_rows = cur.fetchall()

    timeline = []
    for r in timeline_rows:
        dt = r["updated_at"]
        data_str = dt.strftime("%d/%m/%Y %H:%M") if dt else ""
        titolo_short = (r["titolo"] or "")[:40]
        if len(r["titolo"] or "") > 40:
            titolo_short += "..."
        timeline.append({
            "tipo": "valutazione",
            "descrizione": f"{r['progetto_nome']} → {r['stato']} (score: {r['score'] or '—'}) — {titolo_short}",
            "data": data_str,
        })

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
        "candidature_per_stato": candidature_per_stato,
        "nuovi_bandi": nuovi_bandi,
        "progetti_incompleti": progetti_incompleti,
        "hard_stops_top": hard_stops_top,
        "timeline": timeline,
    })


