"""
Candidature routes — list, workspace (4 tab), state transitions, checklist, note.
Ported from tool-bandi-ui/apps/candidature/views.py
Currently uses project_evaluations table (migration 011 adds separate candidatura table).
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context, get_all_projects
from web.main import templates
from web.services.display import enrich_bando_row, as_list
from web.services.state_machine import (
    TRANSITIONS, STATI_SCARTABILI, STATI_ARCHIVIABILI, STATI_RIPRISTINABILI,
    validate_transition, build_initial_checklist,
)

router = APIRouter(prefix="/candidature")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_workspace(conn, pe_id: int) -> dict | None:
    """Load workspace data (project_evaluation + bando + project)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                pe.id AS pe_id, pe.stato, pe.score, pe.hard_stop_reason,
                pe.score_breakdown, pe.gap_analysis, pe.yellow_flags,
                pe.workspace_checklist, pe.workspace_notes,
                pe.workspace_completezza, pe.motivo_scarto,
                pe.data_invio, pe.protocollo_ricevuto,
                pe.project_id,
                b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                b.tipo_finanziamento,
                COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti,
                b.url_fonte, b.portale,
                p.nome AS progetto_nome,
                s.nome AS soggetto_nome
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            JOIN projects p ON pe.project_id = p.id
            LEFT JOIN soggetti s ON p.soggetto_id = s.id
            WHERE pe.id = %s
        """, (pe_id,))
        row = cur.fetchone()

    if not row:
        return None

    data = enrich_bando_row(dict(row))
    data["workspace_checklist"] = as_list(data.get("workspace_checklist"))
    data["workspace_notes"] = as_list(data.get("workspace_notes"))
    data["score_breakdown"] = as_list(data.get("score_breakdown"))
    data["gap_analysis"] = as_list(data.get("gap_analysis"))
    data["yellow_flags"] = as_list(data.get("yellow_flags"))
    return data


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
def candidature_list(request: Request, conn=Depends(get_db)):
    """Lista candidature trasversale (D8) con filtri stato/progetto/soggetto."""
    nav = get_nav_context(request, conn)
    all_projects = get_all_projects(conn)
    qp = request.query_params

    # Filters
    stato_filter = qp.get("stato", "").strip()
    progetto_filter = qp.get("project_id", "").strip()

    conditions = ["pe.stato IN ('lavorazione', 'pronto', 'inviato')"]
    params: list = []

    if stato_filter:
        conditions.append("pe.stato = %s")
        params.append(stato_filter)
    if progetto_filter and progetto_filter.isdigit():
        conditions.append("pe.project_id = %s")
        params.append(int(progetto_filter))

    where = " AND ".join(conditions)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            SELECT pe.id AS pe_id, pe.stato, pe.score,
                   pe.workspace_completezza,
                   b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                   b.tipo_finanziamento,
                   COALESCE(b.importo_max, b.budget_totale) AS budget_display,
                   (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti,
                   p.nome AS progetto_nome,
                   s.nome AS soggetto_nome
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            JOIN projects p ON pe.project_id = p.id
            LEFT JOIN soggetti s ON p.soggetto_id = s.id
            WHERE {where}
            ORDER BY
                CASE pe.stato
                    WHEN 'lavorazione' THEN 1
                    WHEN 'pronto' THEN 2
                    WHEN 'inviato' THEN 3
                END,
                b.data_scadenza ASC NULLS LAST
        """, params)
        rows = [enrich_bando_row(dict(r)) for r in cur.fetchall()]

    # Stats
    stats = {"lavorazione": 0, "pronto": 0, "inviato": 0}
    for r in rows:
        if r["stato"] in stats:
            stats[r["stato"]] += 1

    return templates.TemplateResponse("pages/candidature_list.html", {
        "request": request,
        **nav,
        "active_page": "candidature",
        "rows": rows,
        "stats": stats,
        "total": len(rows),
        "all_projects": all_projects,
        "filters": {
            "stato": stato_filter,
            "project_id": progetto_filter,
        },
    })


# ── Workspace ─────────────────────────────────────────────────────────────────

@router.get("/{pe_id}")
def workspace(request: Request, pe_id: int, conn=Depends(get_db)):
    """Workspace candidatura — 4 tab HTMX (D12: valutazione→documenti→checklist→note_invio)."""
    nav = get_nav_context(request, conn)
    data = _load_workspace(conn, pe_id)

    if not data:
        return HTMLResponse("<h1>Workspace non trovato</h1>", status_code=404)

    # Checklist stats
    checklist = data["workspace_checklist"]
    total_items = len(checklist)
    done_items = sum(1 for i in checklist if isinstance(i, dict) and i.get("completato"))

    # Action flags
    stato = data["stato"]
    data["can_segna_pronto"] = stato == "lavorazione"
    data["can_segna_inviato"] = stato == "pronto"
    data["can_torna_idoneo"] = stato == "lavorazione"
    data["can_torna_lavorazione"] = stato == "pronto"
    data["can_scartare"] = stato in ("lavorazione", "pronto")

    # D12: tab order valutazione→documenti→checklist→note_invio
    active_tab = request.query_params.get("tab", "valutazione")

    ctx = {
        "request": request,
        **nav,
        "active_page": "candidature",
        "pe": data,
        "checklist": checklist,
        "total_items": total_items,
        "done_items": done_items,
        "notes": data["workspace_notes"],
        "active_tab": active_tab,
    }

    return templates.TemplateResponse("pages/candidatura_workspace.html", ctx)


@router.get("/{pe_id}/tab/{tab_name}")
def workspace_tab(request: Request, pe_id: int, tab_name: str, conn=Depends(get_db)):
    """HTMX: return workspace tab partial."""
    data = _load_workspace(conn, pe_id)

    if not data:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    checklist = data["workspace_checklist"]
    total_items = len(checklist)
    done_items = sum(1 for i in checklist if isinstance(i, dict) and i.get("completato"))

    stato = data["stato"]
    data["can_segna_pronto"] = stato == "lavorazione"
    data["can_segna_inviato"] = stato == "pronto"
    data["can_torna_idoneo"] = stato == "lavorazione"
    data["can_torna_lavorazione"] = stato == "pronto"
    data["can_scartare"] = stato in ("lavorazione", "pronto")

    ctx = {
        "request": request,
        "pe": data,
        "checklist": checklist,
        "total_items": total_items,
        "done_items": done_items,
        "notes": data["workspace_notes"],
    }

    # D12: tab order valutazione→documenti→checklist→note_invio
    tab_map = {
        "valutazione": "partials/workspace_tab_overview.html",
        "documenti": "partials/workspace_tab_documenti.html",
        "checklist": "partials/workspace_tab_checklist.html",
        "note_invio": "partials/workspace_tab_note.html",
    }
    tpl = tab_map.get(tab_name, "partials/workspace_tab_overview.html")
    return templates.TemplateResponse(tpl, ctx)


# ── State transitions ─────────────────────────────────────────────────────────

@router.post("/{pe_id}/stato")
def state_action(
    request: Request,
    pe_id: int,
    action: str = Form(""),
    motivo_scarto: str = Form(""),
    data_invio: str = Form(""),
    protocollo_ricevuto: str = Form(""),
    conn=Depends(get_db),
):
    """Esegui transizione di stato."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, stato, bando_id, gap_analysis FROM project_evaluations WHERE id = %s",
            (pe_id,),
        )
        row = cur.fetchone()

    if not row:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    stato_attuale = row["stato"]
    bando_id = row["bando_id"]

    # Validate
    is_valid, error_msg = validate_transition(action, stato_attuale)
    if not is_valid:
        return RedirectResponse(url=f"/bandi/{bando_id}", status_code=303)

    _, nuovo_stato = TRANSITIONS[action]

    # Build UPDATE
    set_parts = ["stato = %s", "updated_at = NOW()"]
    params: list = [nuovo_stato]

    if action == "scarta":
        set_parts.append("motivo_scarto = %s")
        params.append(motivo_scarto.strip() or None)
    elif action == "segna_inviato":
        if not data_invio.strip():
            return RedirectResponse(url=f"/candidature/{pe_id}?tab=overview", status_code=303)
        set_parts.extend(["data_invio = %s", "protocollo_ricevuto = %s"])
        params.extend([data_invio.strip(), protocollo_ricevuto.strip() or None])
    elif action == "avvia_lavorazione":
        checklist = build_initial_checklist(row["gap_analysis"])
        set_parts.append("workspace_checklist = %s")
        params.append(json.dumps(checklist))

    params.append(pe_id)

    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE project_evaluations SET {', '.join(set_parts)} WHERE id = %s",
            params,
        )
        conn.commit()

    # Redirect
    if action == "avvia_lavorazione":
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)
    if stato_attuale in ("lavorazione", "pronto") and nuovo_stato in ("lavorazione", "pronto"):
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)
    return RedirectResponse(url=f"/bandi/{bando_id}", status_code=303)


# ── Checklist CRUD ────────────────────────────────────────────────────────────

@router.post("/{pe_id}/checklist/{item_id}")
def checklist_update(
    request: Request,
    pe_id: int,
    item_id: str,
    conn=Depends(get_db),
):
    """HTMX: toggle checklist item, return updated item partial."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT workspace_checklist FROM project_evaluations WHERE id = %s",
            (pe_id,),
        )
        row = cur.fetchone()

    if not row:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    checklist = as_list(row["workspace_checklist"])

    # Toggle completato
    target_item = None
    for item in checklist:
        if isinstance(item, dict) and item.get("id") == item_id:
            item["completato"] = not item.get("completato", False)
            target_item = item
            break

    if not target_item:
        return HTMLResponse("<p>Item non trovato</p>", status_code=404)

    total = len(checklist)
    done = sum(1 for i in checklist if isinstance(i, dict) and i.get("completato"))
    completezza = int(done / total * 100) if total else 0

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE project_evaluations SET workspace_checklist = %s, workspace_completezza = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(checklist), completezza, pe_id),
        )
        conn.commit()

    return templates.TemplateResponse("partials/checklist_item.html", {
        "request": request,
        "item": target_item,
        "pe_id": pe_id,
        "done_items": done,
        "total_items": total,
    })


@router.post("/{pe_id}/checklist")
def checklist_add(
    request: Request,
    pe_id: int,
    label: str = Form(""),
    conn=Depends(get_db),
):
    """Aggiunge item manuale alla checklist."""
    label = label.strip()
    if not label:
        return RedirectResponse(url=f"/candidature/{pe_id}?tab=checklist", status_code=303)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT workspace_checklist FROM project_evaluations WHERE id = %s",
            (pe_id,),
        )
        row = cur.fetchone()

    if not row:
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)

    checklist = as_list(row["workspace_checklist"])
    new_item = {
        "id": f"manual_{len(checklist)}_{int(datetime.now().timestamp())}",
        "label": label,
        "completato": False,
        "nota": "",
        "tipo": "manuale",
    }
    checklist.append(new_item)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE project_evaluations SET workspace_checklist = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(checklist), pe_id),
        )
        conn.commit()

    return RedirectResponse(url=f"/candidature/{pe_id}?tab=checklist", status_code=303)


# ── Note CRUD ─────────────────────────────────────────────────────────────────

@router.post("/{pe_id}/note")
def note_add(
    request: Request,
    pe_id: int,
    testo: str = Form(""),
    conn=Depends(get_db),
):
    """Aggiunge nota cronologica."""
    testo = testo.strip()
    if not testo:
        return RedirectResponse(url=f"/candidature/{pe_id}?tab=note_invio", status_code=303)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT workspace_notes FROM project_evaluations WHERE id = %s",
            (pe_id,),
        )
        row = cur.fetchone()

    if not row:
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)

    notes = as_list(row["workspace_notes"])
    notes.append({
        "testo": testo,
        "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE project_evaluations SET workspace_notes = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(notes), pe_id),
        )
        conn.commit()

    return RedirectResponse(url=f"/candidature/{pe_id}?tab=note_invio", status_code=303)
