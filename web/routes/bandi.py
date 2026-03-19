"""
Bandi routes — list + detail + bulk actions.
Ported from tool-bandi-ui/apps/bandi/views.py
"""
import threading
from math import ceil

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context, get_all_projects
from web.main import templates
from web.services.display import (
    STATO_META, TIPO_FP_LABELS, TIPO_FP_CSS,
    enrich_bando_row, as_list, score_meta,
)

router = APIRouter(prefix="/bandi")

PER_PAGE = 25


@router.get("")
def bandi_list(request: Request, conn=Depends(get_db)):
    """Lista bandi con filtri, ricerca, paginazione. Progetto via query param (D3)."""
    nav = get_nav_context(request, conn)
    all_projects = get_all_projects(conn)
    qp = request.query_params

    # Project from query param (spec §5.4.1: "Valuta per:")
    pid_str = qp.get("project_id", "").strip()
    pid = int(pid_str) if pid_str.isdigit() else None

    # Read filters
    solo_aperti = qp.get("solo_aperti", "1") != "0"
    nascondi_archiviati = qp.get("nascondi_archiviati", "1") != "0"
    q = qp.get("q", "").strip()
    stato_filter = qp.getlist("stato")
    tipo_fp = qp.get("tipo_fp", "").strip()
    score_min = qp.get("score_min", "").strip()
    scadenza_giorni = qp.get("scadenza_giorni", "").strip()
    portale_filter = qp.get("portale", "").strip()
    page = max(1, int(qp.get("page", "1") or "1"))

    # Build query — with or without project context
    conditions: list[str] = []
    params: list = []
    if pid:
        conditions.append("pe.project_id = %s")
        params.append(pid)

    if nascondi_archiviati:
        conditions.append("pe.stato != 'archiviato'")
    if solo_aperti:
        conditions.append("b.data_scadenza >= CURRENT_DATE")
    if q:
        conditions.append("(b.titolo ILIKE %s OR b.ente_erogatore ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if stato_filter:
        placeholders = ",".join(["%s"] * len(stato_filter))
        conditions.append(f"pe.stato IN ({placeholders})")
        params += stato_filter
    if tipo_fp:
        conditions.append("b.tipo_finanziamento = %s")
        params.append(tipo_fp)
    if score_min and score_min.isdigit():
        conditions.append("pe.score >= %s")
        params.append(int(score_min))
    if scadenza_giorni and scadenza_giorni.isdigit():
        n = int(scadenza_giorni)
        conditions.append(f"b.data_scadenza <= CURRENT_DATE + INTERVAL '{n} days'")
    if portale_filter:
        conditions.append("b.portale = %s")
        params.append(portale_filter)

    where = " AND ".join(conditions) if conditions else "TRUE"

    if pid:
        # With project: show evaluations
        sql = f"""
            SELECT
                pe.id AS pe_id, pe.stato, pe.score, pe.hard_stop_reason,
                b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                b.tipo_finanziamento, b.portale,
                COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE {where}
            ORDER BY pe.score DESC NULLS LAST, b.data_scadenza ASC
        """
    else:
        # Without project: show all bandi (no evaluation data)
        bandi_conditions = []
        bandi_params: list = []
        if solo_aperti:
            bandi_conditions.append("b.data_scadenza >= CURRENT_DATE")
        if q:
            bandi_conditions.append("(b.titolo ILIKE %s OR b.ente_erogatore ILIKE %s)")
            bandi_params += [f"%{q}%", f"%{q}%"]
        if tipo_fp:
            bandi_conditions.append("b.tipo_finanziamento = %s")
            bandi_params.append(tipo_fp)
        if scadenza_giorni and scadenza_giorni.isdigit():
            n = int(scadenza_giorni)
            bandi_conditions.append(f"b.data_scadenza <= CURRENT_DATE + INTERVAL '{n} days'")
        if portale_filter:
            bandi_conditions.append("b.portale = %s")
            bandi_params.append(portale_filter)

        bandi_where = " AND ".join(bandi_conditions) if bandi_conditions else "TRUE"
        sql = f"""
            SELECT
                NULL::int AS pe_id, NULL AS stato, NULL::int AS score, NULL AS hard_stop_reason,
                b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                b.tipo_finanziamento, b.portale,
                COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti
            FROM bandi b
            WHERE {bandi_where}
            ORDER BY b.data_scadenza ASC
        """
        params = bandi_params

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        all_rows = [enrich_bando_row(dict(r)) for r in cur.fetchall()]

    # Pagination
    total = len(all_rows)
    total_pages = max(1, ceil(total / PER_PAGE))
    page = min(page, total_pages)
    start = (page - 1) * PER_PAGE
    rows = all_rows[start : start + PER_PAGE]

    # Filter dropdown options
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT portale FROM bandi
            WHERE portale IS NOT NULL ORDER BY portale
        """)
        portali = [r["portale"] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT tipo_finanziamento FROM bandi
            WHERE tipo_finanziamento IS NOT NULL ORDER BY tipo_finanziamento
        """)
        tipi_fp_options = [
            (r["tipo_finanziamento"], TIPO_FP_LABELS.get(r["tipo_finanziamento"], r["tipo_finanziamento"]))
            for r in cur.fetchall()
        ]

    last_scaduto = None

    filters = {
        "solo_aperti": solo_aperti,
        "nascondi_archiviati": nascondi_archiviati,
        "q": q,
        "stato": stato_filter,
        "tipo_fp": tipo_fp,
        "score_min": score_min,
        "scadenza_giorni": scadenza_giorni,
        "portale": portale_filter,
    }

    ctx = {
        "request": request,
        **nav,
        "active_page": "bandi",
        "rows": rows,
        "total_count": total,
        "page": page,
        "total_pages": total_pages,
        "filters": filters,
        "portali": portali,
        "tipi_fp_options": tipi_fp_options,
        "stati_choices": list(STATO_META.items()),
        "last_scaduto": last_scaduto,
        "has_active_filters": any([stato_filter, tipo_fp, score_min, scadenza_giorni, portale_filter, q]),
        "all_projects": all_projects,
        "selected_project_id": pid,
    }

    # HTMX partial: return only table rows
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/bandi_table_rows.html", ctx)

    return templates.TemplateResponse("pages/bandi_list.html", ctx)


@router.get("/{bando_id}")
def bando_detail(request: Request, bando_id: int, conn=Depends(get_db)):
    """Scheda bando — 3 tab. Progetto via query param (D4)."""
    nav = get_nav_context(request, conn)
    all_projects = get_all_projects(conn)
    qp = request.query_params

    pid_str = qp.get("project_id", "").strip()
    pid = int(pid_str) if pid_str.isdigit() else None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if pid:
            cur.execute("""
                SELECT pe.id AS pe_id, pe.stato, pe.score, pe.hard_stop_reason,
                       pe.score_breakdown, pe.gap_analysis, pe.yellow_flags,
                       pe.workspace_checklist, pe.motivo_scarto,
                       b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                       b.tipo_finanziamento,
                       COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                       (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti,
                       b.raw_text, b.criteri_valutazione, b.metadata,
                       b.url_fonte, b.portale
                FROM project_evaluations pe
                JOIN bandi b ON pe.bando_id = b.id
                WHERE b.id = %s AND pe.project_id = %s
            """, (bando_id, pid))
            row = cur.fetchone()
        else:
            # No project: show bando info without evaluation
            cur.execute("""
                SELECT NULL::int AS pe_id, NULL AS stato, NULL::int AS score,
                       NULL AS hard_stop_reason, NULL AS score_breakdown,
                       NULL AS gap_analysis, NULL AS yellow_flags,
                       NULL AS workspace_checklist, NULL AS motivo_scarto,
                       b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                       b.tipo_finanziamento,
                       COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                       (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti,
                       b.raw_text, b.criteri_valutazione, b.metadata,
                       b.url_fonte, b.portale
                FROM bandi b WHERE b.id = %s
            """, (bando_id,))
            row = cur.fetchone()

    if not row:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<h1>Bando non trovato</h1>", status_code=404)

    data = enrich_bando_row(dict(row))

    # Normalize JSONB
    data["score_breakdown"] = as_list(data.get("score_breakdown"))
    data["gap_analysis"] = as_list(data.get("gap_analysis"))
    data["yellow_flags"] = as_list(data.get("yellow_flags"))

    # Pro/Contro for Decisione tab
    pro_list = [i for i in data["score_breakdown"] if isinstance(i, dict) and i.get("matched")]
    contro_list = [i for i in data["gap_analysis"] if isinstance(i, dict)]
    contro_list += [{**i, "is_yellow": True} for i in data["yellow_flags"] if isinstance(i, dict)]

    # State-dependent action flags
    stato = data["stato"]
    data["can_avvia"] = stato == "idoneo"
    data["can_segna_pronto"] = stato == "lavorazione"
    data["can_segna_inviato"] = stato == "pronto"
    data["can_torna_idoneo"] = stato == "lavorazione"
    data["can_torna_lavorazione"] = stato == "pronto"
    data["can_scartare"] = stato in ("nuovo", "idoneo", "lavorazione", "pronto")
    data["can_rivalutare"] = stato in ("nuovo", "idoneo", "lavorazione")
    data["can_archiviare"] = stato in ("inviato", "scartato")
    data["can_ripristinare"] = stato in ("scartato", "archiviato")

    active_tab = request.query_params.get("tab", "decisione" if pid else "dettaglio")

    return templates.TemplateResponse("pages/bando_detail.html", {
        "request": request,
        **nav,
        "active_page": "bandi",
        "bando": data,
        "pro_list": pro_list,
        "contro_list": contro_list,
        "active_tab": active_tab,
        "all_projects": all_projects,
        "selected_project_id": pid,
    })


@router.get("/{bando_id}/tab/{tab_name}")
def bando_tab(request: Request, bando_id: int, tab_name: str, conn=Depends(get_db)):
    """HTMX: return tab content partial."""
    pid_str = request.query_params.get("project_id", "").strip()
    pid = int(pid_str) if pid_str.isdigit() else None
    if not pid:
        pid = 1  # fallback for tab requests

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT pe.id AS pe_id, pe.stato, pe.score, pe.hard_stop_reason,
                   pe.score_breakdown, pe.gap_analysis, pe.yellow_flags,
                   pe.motivo_scarto,
                   b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                   b.tipo_finanziamento,
                   COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                   (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti,
                   b.raw_text, b.metadata, b.url_fonte, b.portale
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE b.id = %s AND pe.project_id = %s
        """, (bando_id, pid))
        row = cur.fetchone()

    if not row:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    data = enrich_bando_row(dict(row))
    data["score_breakdown"] = as_list(data.get("score_breakdown"))
    data["gap_analysis"] = as_list(data.get("gap_analysis"))
    data["yellow_flags"] = as_list(data.get("yellow_flags"))

    pro_list = [i for i in data["score_breakdown"] if isinstance(i, dict) and i.get("matched")]
    contro_list = [i for i in data["gap_analysis"] if isinstance(i, dict)]
    contro_list += [{**i, "is_yellow": True} for i in data["yellow_flags"] if isinstance(i, dict)]

    template_map = {
        "decisione": "partials/bando_tab_decisione.html",
        "dettaglio": "partials/bando_tab_dettaglio.html",
        "testo": "partials/bando_tab_testo.html",
    }
    template_name = template_map.get(tab_name, "partials/bando_tab_decisione.html")

    return templates.TemplateResponse(template_name, {
        "request": request,
        "bando": data,
        "pro_list": pro_list,
        "contro_list": contro_list,
    })


@router.post("/bulk-action")
def bandi_bulk_action(
    request: Request,
    action: str = Form(""),
    pe_ids: list[int] = Form([]),
    conn=Depends(get_db),
):
    """Bulk actions: archivia scaduti / rivaluta."""
    if not pe_ids:
        return RedirectResponse(url="/bandi", status_code=303)

    if action == "archivia_scaduti":
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE project_evaluations pe
                SET stato = 'archiviato', updated_at = NOW()
                FROM bandi b
                WHERE pe.bando_id = b.id
                  AND pe.id = ANY(%s)
                  AND b.data_scadenza < CURRENT_DATE
                  AND pe.stato NOT IN ('archiviato', 'inviato')
            """, (pe_ids,))
            conn.commit()

    elif action == "rivaluta":
        def _run(ids):
            try:
                from engine.pipeline.flows import rivaluta_singolo
                for pe_id in ids:
                    rivaluta_singolo(pe_id)
            except Exception:
                pass
        threading.Thread(target=_run, args=(pe_ids,), daemon=True).start()

    referer = request.headers.get("referer", "/bandi")
    return RedirectResponse(url=referer, status_code=303)
