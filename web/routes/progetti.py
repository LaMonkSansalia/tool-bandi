"""
Progetti routes — list, detail (4 tabs), save profilo, save scoring, create.
Ported from tool-bandi-ui/apps/progetti/views.py
"""
import json
import re
import threading

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context
from web.main import templates
from web.services.display import enrich_bando_row
from web.services.completezza import (
    PROFILO_DEFAULT, SETTORI, COFINANZIAMENTO_FONTI, ZONE_SPECIALI_OPTIONS,
    check_completezza, normalize_profilo, parse_int_or_none,
)

router = APIRouter(prefix="/progetti")


def _load_opportunita(conn, pk: int) -> tuple[list, dict]:
    """Load bandi valutati per un progetto + stats rapide."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT pe.id AS pe_id, pe.score, pe.stato,
                   b.id AS bando_id, b.titolo, b.ente_erogatore, b.data_scadenza,
                   (b.data_scadenza - CURRENT_DATE)::int AS giorni_rimasti
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.project_id = %s
              AND pe.stato NOT IN ('nuovo', 'archiviato')
            ORDER BY pe.score DESC NULLS LAST, b.data_scadenza ASC
        """, (pk,))
        rows = [enrich_bando_row(dict(r)) for r in cur.fetchall()]

        cur.execute("""
            SELECT stato, COUNT(*) AS n
            FROM project_evaluations
            WHERE project_id = %s AND stato NOT IN ('nuovo', 'archiviato')
            GROUP BY stato
        """, (pk,))
        stats = {r["stato"]: r["n"] for r in cur.fetchall()}

        cur.execute("""
            SELECT COUNT(*) AS n FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.project_id = %s
              AND pe.stato IN ('idoneo', 'lavorazione')
              AND b.data_scadenza BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
        """, (pk,))
        stats["scadono_14gg"] = cur.fetchone()["n"]

    return rows, stats


def _load_project(conn, pk: int) -> dict | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, nome, slug, profilo, scoring_rules, attivo, soggetto_id, descrizione_breve "
            "FROM projects WHERE id = %s",
            (pk,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return dict(row)


@router.get("")
def progetti_list(request: Request, conn=Depends(get_db)):
    """Lista progetti raggruppata per soggetto."""
    nav = get_nav_context(request, conn)
    settori_map = {k: v for k, v in SETTORI}

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT p.id, p.nome, p.slug, p.profilo, p.soggetto_id,
                   s.nome AS soggetto_nome,
                   COUNT(pe.id) FILTER (WHERE pe.stato NOT IN ('nuovo', 'archiviato')) AS n_candidature
            FROM projects p
            LEFT JOIN soggetti s ON s.id = p.soggetto_id
            LEFT JOIN project_evaluations pe ON pe.project_id = p.id
            WHERE p.attivo = TRUE
            GROUP BY p.id, p.nome, p.slug, p.profilo, p.soggetto_id, s.nome
            ORDER BY s.nome NULLS LAST, p.nome
        """)
        rows = [dict(r) for r in cur.fetchall()]

        # All soggetti for create modal
        cur.execute("SELECT id, nome FROM soggetti WHERE attivo = TRUE ORDER BY nome")
        soggetti = [dict(r) for r in cur.fetchall()]

    progetti = []
    for p in rows:
        profilo = normalize_profilo(p.get("profilo"))
        _, _, completezza_pct = check_completezza(profilo)
        settore = profilo.get("settore", "")
        progetti.append({
            "id": p["id"],
            "nome": p["nome"],
            "slug": p["slug"],
            "soggetto_id": p["soggetto_id"],
            "soggetto_nome": p["soggetto_nome"] or "Nessun soggetto",
            "settore_label": settori_map.get(settore, ""),
            "n_candidature": p["n_candidature"] or 0,
            "completezza_pct": completezza_pct,
        })

    # Group by soggetto
    grouped = {}
    for p in progetti:
        key = p["soggetto_nome"]
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(p)

    return templates.TemplateResponse("pages/progetti_list.html", {
        "request": request,
        **nav,
        "active_page": "progetti",
        "grouped_progetti": grouped,
        "total_progetti": len(progetti),
        "soggetti": soggetti,
    })


@router.post("/nuovo")
def progetto_create(
    request: Request,
    nome: str = Form(""),
    soggetto_id: int = Form(0),
    conn=Depends(get_db),
):
    """Crea nuovo progetto."""
    nome = nome.strip()
    if not nome:
        return RedirectResponse(url="/progetti", status_code=303)

    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    sog_id = soggetto_id if soggetto_id > 0 else None

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO projects (nome, slug, attivo, profilo, scoring_rules, soggetto_id, created_at, updated_at)
            VALUES (%s, %s, TRUE, '{}'::jsonb, '{}'::jsonb, %s, NOW(), NOW())
            RETURNING id
        """, (nome, slug, sog_id))
        new_id = cur.fetchone()[0]
        conn.commit()

    return RedirectResponse(url=f"/progetti/{new_id}", status_code=303)


@router.get("/{pk}")
def progetto_detail(request: Request, pk: int, conn=Depends(get_db)):
    """Dettaglio progetto — 4 tab HTMX."""
    nav = get_nav_context(request, conn)
    proj = _load_project(conn, pk)

    if not proj:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<h1>Progetto non trovato</h1>", status_code=404)

    profilo = normalize_profilo(proj["profilo"])
    completezza_items, completezza_done, completezza_pct = check_completezza(profilo)

    # Word count for descrizione estesa
    desc = profilo.get("descrizione_estesa") or ""
    parole_count = len(desc.split()) if desc.strip() else 0

    # Scoring rules
    scoring_raw = proj["scoring_rules"] or {}
    if isinstance(scoring_raw, str):
        scoring_raw = json.loads(scoring_raw)
    scoring_json = json.dumps(scoring_raw, indent=2, ensure_ascii=False)

    # Gap analysis aggregata
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COALESCE(gap->>'tipo', gap->>'categoria', 'Gap generico') AS tipo,
                gap->>'suggerimento'  AS suggerimento,
                COUNT(*)              AS bandi_impattati
            FROM project_evaluations pe,
                 jsonb_array_elements(pe.gap_analysis) AS gap
            WHERE pe.project_id = %s
              AND pe.stato != 'nuovo'
              AND pe.gap_analysis IS NOT NULL
              AND jsonb_typeof(pe.gap_analysis) = 'array'
            GROUP BY tipo, suggerimento
            ORDER BY bandi_impattati DESC
            LIMIT 20
        """, (pk,))
        gap_rows = [dict(r) for r in cur.fetchall()]

    # Soggetto associato
    soggetto = None
    if proj.get("soggetto_id"):
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, nome, forma_giuridica, regime_fiscale, profilo FROM soggetti WHERE id = %s",
                (proj["soggetto_id"],),
            )
            sog_row = cur.fetchone()
            if sog_row:
                soggetto = dict(sog_row)
                sog_profilo = soggetto.get("profilo") or {}
                if isinstance(sog_profilo, str):
                    sog_profilo = json.loads(sog_profilo)
                soggetto["ateco"] = sog_profilo.get("ateco", "")
                soggetto["dipendenti"] = sog_profilo.get("dipendenti", 0)

    # Candidature count
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT stato, COUNT(*) AS n
            FROM project_evaluations
            WHERE project_id = %s AND stato NOT IN ('nuovo', 'archiviato')
            GROUP BY stato
        """, (pk,))
        candidature_stats = {r["stato"]: r["n"] for r in cur.fetchall()}

    # Opportunità: bandi valutati per questo progetto (tab default)
    opportunita = []
    opportunita_stats = {}
    active_tab = request.query_params.get("tab", "opportunita")
    if active_tab == "opportunita" or not request.headers.get("HX-Request"):
        opportunita, opportunita_stats = _load_opportunita(conn, pk)
    saved = request.query_params.get("saved", "")
    error = request.query_params.get("error", "")
    rivaluta_avviato = request.query_params.get("rivaluta", "")

    ctx = {
        "request": request,
        **nav,
        "active_page": "progetti",
        "proj": proj,
        "profilo": profilo,
        "soggetto": soggetto,
        "completezza_items": completezza_items,
        "completezza_done": completezza_done,
        "completezza_total": len(completezza_items),
        "completezza_pct": completezza_pct,
        "parole_count": parole_count,
        "scoring_json": scoring_json,
        "gap_rows": gap_rows,
        "candidature_stats": candidature_stats,
        "opportunita": opportunita,
        "opportunita_stats": opportunita_stats,
        "active_tab": active_tab,
        "saved": saved,
        "error": error,
        "rivaluta_avviato": rivaluta_avviato,
        "SETTORI": SETTORI,
        "COFINANZIAMENTO_FONTI": COFINANZIAMENTO_FONTI,
        "ZONE_SPECIALI_OPTIONS": ZONE_SPECIALI_OPTIONS,
    }

    # HTMX partial: return only tab content
    if request.headers.get("HX-Request") and request.query_params.get("tab"):
        tab_map = {
            "opportunita": "partials/progetto_tab_opportunita.html",
            "candidature": "partials/progetto_tab_candidature.html",
            "profilo": "partials/progetto_tab_profilo.html",
            "analisi": "partials/progetto_tab_analisi.html",
        }
        tpl = tab_map.get(active_tab, "partials/progetto_tab_opportunita.html")
        return templates.TemplateResponse(tpl, ctx)

    return templates.TemplateResponse("pages/progetto_detail.html", ctx)


@router.get("/{pk}/tab/{tab_name}")
def progetto_tab(request: Request, pk: int, tab_name: str, conn=Depends(get_db)):
    """HTMX: return tab content partial."""
    proj = _load_project(conn, pk)
    if not proj:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    profilo = normalize_profilo(proj["profilo"])
    completezza_items, completezza_done, completezza_pct = check_completezza(profilo)
    desc = profilo.get("descrizione_estesa") or ""
    parole_count = len(desc.split()) if desc.strip() else 0

    scoring_raw = proj["scoring_rules"] or {}
    if isinstance(scoring_raw, str):
        scoring_raw = json.loads(scoring_raw)
    scoring_json = json.dumps(scoring_raw, indent=2, ensure_ascii=False)

    gap_rows = []
    if tab_name == "analisi":
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COALESCE(gap->>'tipo', gap->>'categoria', 'Gap generico') AS tipo,
                    gap->>'suggerimento'  AS suggerimento,
                    COUNT(*)              AS bandi_impattati
                FROM project_evaluations pe,
                     jsonb_array_elements(pe.gap_analysis) AS gap
                WHERE pe.project_id = %s
                  AND pe.stato != 'nuovo'
                  AND pe.gap_analysis IS NOT NULL
                  AND jsonb_typeof(pe.gap_analysis) = 'array'
                GROUP BY tipo, suggerimento
                ORDER BY bandi_impattati DESC
                LIMIT 20
            """, (pk,))
            gap_rows = [dict(r) for r in cur.fetchall()]

    candidature_stats = {}
    if tab_name == "candidature":
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT stato, COUNT(*) AS n
                FROM project_evaluations
                WHERE project_id = %s AND stato NOT IN ('nuovo', 'archiviato')
                GROUP BY stato
            """, (pk,))
            candidature_stats = {r["stato"]: r["n"] for r in cur.fetchall()}

    soggetto = None
    if proj.get("soggetto_id"):
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, nome, forma_giuridica, regime_fiscale, profilo FROM soggetti WHERE id = %s",
                (proj["soggetto_id"],),
            )
            sog_row = cur.fetchone()
            if sog_row:
                soggetto = dict(sog_row)
                sog_profilo = soggetto.get("profilo") or {}
                if isinstance(sog_profilo, str):
                    sog_profilo = json.loads(sog_profilo)
                soggetto["ateco"] = sog_profilo.get("ateco", "")
                soggetto["dipendenti"] = sog_profilo.get("dipendenti", 0)

    ctx = {
        "request": request,
        "proj": proj,
        "profilo": profilo,
        "soggetto": soggetto,
        "completezza_items": completezza_items,
        "completezza_done": completezza_done,
        "completezza_total": len(completezza_items),
        "completezza_pct": completezza_pct,
        "parole_count": parole_count,
        "scoring_json": scoring_json,
        "gap_rows": gap_rows,
        "candidature_stats": candidature_stats,
        "SETTORI": SETTORI,
        "COFINANZIAMENTO_FONTI": COFINANZIAMENTO_FONTI,
        "ZONE_SPECIALI_OPTIONS": ZONE_SPECIALI_OPTIONS,
    }

    # Load opportunita data if needed
    opportunita = []
    opportunita_stats = {}
    if tab_name == "opportunita":
        opportunita, opportunita_stats = _load_opportunita(conn, pk)
    ctx["opportunita"] = opportunita
    ctx["opportunita_stats"] = opportunita_stats

    tab_map = {
        "opportunita": "partials/progetto_tab_opportunita.html",
        "candidature": "partials/progetto_tab_candidature.html",
        "profilo": "partials/progetto_tab_profilo.html",
        "analisi": "partials/progetto_tab_analisi.html",
    }
    tpl = tab_map.get(tab_name, "partials/progetto_tab_opportunita.html")
    return templates.TemplateResponse(tpl, ctx)


@router.post("/{pk}/profilo")
def progetto_save_profilo(
    request: Request,
    pk: int,
    conn=Depends(get_db),
    descrizione_breve: str = Form(""),
    descrizione_estesa: str = Form(""),
    settore: str = Form(""),
    keywords: str = Form(""),
    comuni_target: str = Form(""),
    costituita: str = Form("1"),
    budget_min: str = Form(""),
    budget_max: str = Form(""),
    cofinanziamento_pct: str = Form(""),
    cofinanziamento_fonte: str = Form(""),
    referenze_simili: str = Form(""),
    avvio_previsto: str = Form(""),
    durata_mesi: str = Form("24"),
    pf_innovativita: str = Form(""),
    pf_impatto: str = Form(""),
    pf_sostenibilita: str = Form(""),
    partner_json: str = Form("[]"),
    piano_lavoro_json: str = Form("[]"),
    kpi_json: str = Form("[]"),
    documenti_supporto_json: str = Form("[]"),
):
    """Salva profilo JSONB del progetto."""
    proj = _load_project(conn, pk)
    if not proj:
        return RedirectResponse(url="/progetti", status_code=303)

    def _csv_to_list(val):
        return [x.strip() for x in val.split(",") if x.strip()]

    def _json_field(val, fallback):
        try:
            return json.loads(val) if val.strip() else fallback
        except (ValueError, TypeError):
            return fallback

    profilo = {
        "descrizione_breve": descrizione_breve.strip()[:140],
        "descrizione_estesa": descrizione_estesa.strip(),
        "settore": settore.strip(),
        "keywords": _csv_to_list(keywords),
        "comuni_target": _csv_to_list(comuni_target),
        "zone_speciali": [],  # handled separately if multi-select
        "costituita": costituita == "1",
        "budget_min": parse_int_or_none(budget_min),
        "budget_max": parse_int_or_none(budget_max),
        "cofinanziamento_pct": parse_int_or_none(cofinanziamento_pct),
        "cofinanziamento_fonte": cofinanziamento_fonte.strip(),
        "partner": _json_field(partner_json, []),
        "piano_lavoro": _json_field(piano_lavoro_json, []),
        "kpi": _json_field(kpi_json, []),
        "punti_di_forza": {
            "innovativita": pf_innovativita.strip(),
            "impatto_sociale": pf_impatto.strip(),
            "sostenibilita": pf_sostenibilita.strip(),
        },
        "referenze_simili": referenze_simili.strip(),
        "avvio_previsto": avvio_previsto.strip(),
        "durata_mesi": parse_int_or_none(durata_mesi) or 24,
        "documenti_supporto": _json_field(documenti_supporto_json, []),
    }

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE projects SET profilo = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(profilo, ensure_ascii=False), pk),
        )
        conn.commit()

    return RedirectResponse(url=f"/progetti/{pk}?tab=profilo&saved=1", status_code=303)


@router.post("/{pk}/scoring")
def progetto_save_scoring(
    request: Request,
    pk: int,
    scoring_rules_json: str = Form("{}"),
    rivaluta: str = Form("0"),
    conn=Depends(get_db),
):
    """Salva scoring_rules + opzionale ri-valuta tutti."""
    proj = _load_project(conn, pk)
    if not proj:
        return RedirectResponse(url="/progetti", status_code=303)

    try:
        scoring_rules = json.loads(scoring_rules_json) if scoring_rules_json.strip() else {}
    except (ValueError, TypeError):
        return RedirectResponse(url=f"/progetti/{pk}?tab=scoring&error=json_invalid", status_code=303)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE projects SET scoring_rules = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(scoring_rules, ensure_ascii=False), pk),
        )
        conn.commit()

    if rivaluta == "1":
        def _run(project_id):
            try:
                from engine.pipeline.flows import rivaluta_progetto
                rivaluta_progetto(project_id)
            except Exception:
                pass
        threading.Thread(target=_run, args=(pk,), daemon=True).start()

    suffix = "&rivaluta=1" if rivaluta == "1" else ""
    return RedirectResponse(url=f"/progetti/{pk}?tab=scoring&saved=1{suffix}", status_code=303)
