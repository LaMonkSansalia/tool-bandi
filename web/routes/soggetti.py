"""
Soggetti routes — list, detail, create, update, duplicate as simulation.
"""
import json
import re

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_nav_context
from web.main import templates

router = APIRouter(prefix="/soggetti")


def _load_soggetto(conn, soggetto_id: int) -> dict | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, slug, nome, forma_giuridica, regime_fiscale, profilo, attivo FROM soggetti WHERE id = %s",
            (soggetto_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    s = dict(row)
    raw = s.get("profilo") or {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    s["profilo"] = raw
    return s


@router.get("")
def soggetti_list(request: Request, conn=Depends(get_db)):
    """Lista soggetti — reali + simulazioni."""
    nav = get_nav_context(request, conn)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # All soggetti with project count
        cur.execute("""
            SELECT s.id, s.slug, s.nome, s.forma_giuridica, s.regime_fiscale,
                   s.profilo, s.attivo,
                   COUNT(p.id) AS n_progetti
            FROM soggetti s
            LEFT JOIN projects p ON p.soggetto_id = s.id AND p.attivo = TRUE
            GROUP BY s.id
            ORDER BY s.nome
        """)
        rows = [dict(r) for r in cur.fetchall()]

    FORME_LABELS = {
        "impresa_individuale": "Impresa Individuale",
        "srl": "SRL",
        "srls": "SRLS",
        "snc": "SNC",
        "sas": "SAS",
        "cooperativa": "Cooperativa",
        "associazione": "Associazione",
        "fondazione": "Fondazione",
        "consorzio": "Consorzio",
        "ente_pubblico": "Ente Pubblico",
    }
    REGIME_LABELS = {
        "forfettario": "Forfettario",
        "ordinario": "Ordinario",
        "semplificato": "Semplificato",
    }

    for s in rows:
        raw = s.get("profilo") or {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        s["profilo"] = raw
        tipo = raw.get("tipo", "reale")
        s["tipo"] = tipo
        s["simulazione_di"] = raw.get("simulazione_di")
        s["forma_label"] = FORME_LABELS.get(s.get("forma_giuridica", ""), s.get("forma_giuridica", ""))
        s["regime_label"] = REGIME_LABELS.get(s.get("regime_fiscale", ""), s.get("regime_fiscale", ""))
        s["ateco"] = raw.get("ateco", "")
        s["sede"] = raw.get("sede", "")

    reali = [s for s in rows if s["tipo"] == "reale"]
    simulazioni = [s for s in rows if s["tipo"] == "simulazione"]

    active_tab = request.query_params.get("tab", "reali")

    return templates.TemplateResponse("pages/soggetti_list.html", {
        "request": request,
        **nav,
        "active_page": "soggetti",
        "reali": reali,
        "simulazioni": simulazioni,
        "active_tab": active_tab,
        "FORME_LABELS": FORME_LABELS,
    })


@router.get("/nuovo")
def soggetto_new(request: Request, conn=Depends(get_db)):
    """Form creazione nuovo soggetto."""
    nav = get_nav_context(request, conn)
    tipo = request.query_params.get("tipo", "reale")
    if tipo not in ("reale", "simulazione"):
        tipo = "reale"
    return templates.TemplateResponse("pages/soggetto_form.html", {
        "request": request,
        **nav,
        "active_page": "soggetti",
        "soggetto": None,
        "mode": "create",
        "tipo": tipo,
    })


@router.post("/nuovo")
def soggetto_create(
    request: Request,
    nome: str = Form(""),
    forma_giuridica: str = Form(""),
    regime_fiscale: str = Form(""),
    ateco: str = Form(""),
    sede: str = Form(""),
    piva: str = Form(""),
    dipendenti: str = Form("0"),
    fatturato: str = Form(""),
    anno_costituzione: str = Form(""),
    tipo: str = Form("reale"),
    conn=Depends(get_db),
):
    """Crea nuovo soggetto."""
    nome = nome.strip()
    if not nome:
        return RedirectResponse(url="/soggetti", status_code=303)

    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    if tipo not in ("reale", "simulazione"):
        tipo = "reale"

    profilo = {
        "tipo": tipo,
        "ateco": ateco.strip(),
        "sede": sede.strip(),
        "piva": piva.strip(),
        "dipendenti": _safe_int(dipendenti, 0),
        "fatturato": _safe_int(fatturato, None),
        "anno_costituzione": _safe_int(anno_costituzione, None),
        "hard_stops": [],
        "vantaggi": [],
    }

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO soggetti (slug, nome, forma_giuridica, regime_fiscale, profilo, attivo)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (slug, nome, forma_giuridica.strip(), regime_fiscale.strip(),
              json.dumps(profilo, ensure_ascii=False)))
        new_id = cur.fetchone()[0]
        conn.commit()

    return RedirectResponse(url=f"/soggetti/{new_id}", status_code=303)


@router.get("/{soggetto_id}")
def soggetto_detail(request: Request, soggetto_id: int, conn=Depends(get_db)):
    """Dettaglio soggetto — anagrafica, progetti, hard stops."""
    nav = get_nav_context(request, conn)
    s = _load_soggetto(conn, soggetto_id)

    if not s:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<h1>Soggetto non trovato</h1>", status_code=404)

    # Progetti associati
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT p.id, p.nome, p.slug, p.profilo,
                   COUNT(pe.id) FILTER (WHERE pe.stato NOT IN ('nuovo', 'archiviato')) AS n_candidature
            FROM projects p
            LEFT JOIN project_evaluations pe ON pe.project_id = p.id
            WHERE p.soggetto_id = %s AND p.attivo = TRUE
            GROUP BY p.id
            ORDER BY p.nome
        """, (soggetto_id,))
        progetti = [dict(r) for r in cur.fetchall()]

    # Hard stops dal profilo
    profilo = s["profilo"]
    hard_stops = profilo.get("hard_stops", [])
    vantaggi = profilo.get("vantaggi", [])

    saved = request.query_params.get("saved", "")
    active_tab = request.query_params.get("tab", "anagrafica")

    return templates.TemplateResponse("pages/soggetto_detail.html", {
        "request": request,
        **nav,
        "active_page": "soggetti",
        "soggetto": s,
        "progetti": progetti,
        "hard_stops": hard_stops,
        "vantaggi": vantaggi,
        "saved": saved,
        "active_tab": active_tab,
    })


@router.get("/{soggetto_id}/tab/{tab_name}")
def soggetto_tab(request: Request, soggetto_id: int, tab_name: str, conn=Depends(get_db)):
    """HTMX: return tab content partial."""
    s = _load_soggetto(conn, soggetto_id)
    if not s:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT p.id, p.nome, p.slug, p.profilo,
                   COUNT(pe.id) FILTER (WHERE pe.stato NOT IN ('nuovo', 'archiviato')) AS n_candidature
            FROM projects p
            LEFT JOIN project_evaluations pe ON pe.project_id = p.id
            WHERE p.soggetto_id = %s AND p.attivo = TRUE
            GROUP BY p.id
            ORDER BY p.nome
        """, (soggetto_id,))
        progetti = [dict(r) for r in cur.fetchall()]

    profilo = s["profilo"]
    ctx = {
        "request": request,
        "soggetto": s,
        "progetti": progetti,
        "hard_stops": profilo.get("hard_stops", []),
        "vantaggi": profilo.get("vantaggi", []),
    }

    tab_map = {
        "anagrafica": "partials/soggetto_tab_anagrafica.html",
        "vincoli": "partials/soggetto_tab_vincoli.html",
        "progetti": "partials/soggetto_tab_progetti.html",
    }
    tpl = tab_map.get(tab_name, "partials/soggetto_tab_anagrafica.html")
    return templates.TemplateResponse(tpl, ctx)


@router.post("/{soggetto_id}")
def soggetto_update(
    request: Request,
    soggetto_id: int,
    nome: str = Form(""),
    forma_giuridica: str = Form(""),
    regime_fiscale: str = Form(""),
    ateco: str = Form(""),
    sede: str = Form(""),
    piva: str = Form(""),
    dipendenti: str = Form("0"),
    fatturato: str = Form(""),
    anno_costituzione: str = Form(""),
    conn=Depends(get_db),
):
    """Aggiorna soggetto."""
    s = _load_soggetto(conn, soggetto_id)
    if not s:
        return RedirectResponse(url="/soggetti", status_code=303)

    # Merge profilo preservando hard_stops e vantaggi esistenti
    old_profilo = s["profilo"]
    profilo = {
        **old_profilo,
        "ateco": ateco.strip(),
        "sede": sede.strip(),
        "piva": piva.strip(),
        "dipendenti": _safe_int(dipendenti, 0),
        "fatturato": _safe_int(fatturato, None),
        "anno_costituzione": _safe_int(anno_costituzione, None),
    }

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE soggetti
            SET nome = %s, forma_giuridica = %s, regime_fiscale = %s,
                profilo = %s
            WHERE id = %s
        """, (nome.strip(), forma_giuridica.strip(), regime_fiscale.strip(),
              json.dumps(profilo, ensure_ascii=False), soggetto_id))
        conn.commit()

    return RedirectResponse(url=f"/soggetti/{soggetto_id}?saved=1", status_code=303)


@router.post("/{soggetto_id}/duplica")
def soggetto_duplica(request: Request, soggetto_id: int, conn=Depends(get_db)):
    """Duplica soggetto come simulazione."""
    s = _load_soggetto(conn, soggetto_id)
    if not s:
        return RedirectResponse(url="/soggetti", status_code=303)

    new_nome = f"{s['nome']} (simulazione)"
    new_slug = f"{s['slug']}-sim"

    profilo = {
        **s["profilo"],
        "tipo": "simulazione",
        "simulazione_di": soggetto_id,
    }

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO soggetti (slug, nome, forma_giuridica, regime_fiscale, profilo, attivo)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (new_slug, new_nome, s["forma_giuridica"], s["regime_fiscale"],
              json.dumps(profilo, ensure_ascii=False)))
        new_id = cur.fetchone()[0]
        conn.commit()

    return RedirectResponse(url=f"/soggetti/{new_id}?tab=anagrafica", status_code=303)


@router.post("/{soggetto_id}/vincolo")
def soggetto_add_vincolo(
    request: Request,
    soggetto_id: int,
    label: str = Form(""),
    motivo: str = Form(""),
    conn=Depends(get_db),
):
    """Aggiunge vincolo (hard stop) al soggetto."""
    s = _load_soggetto(conn, soggetto_id)
    if not s or not label.strip():
        return RedirectResponse(url=f"/soggetti/{soggetto_id}?tab=vincoli", status_code=303)

    profilo = s["profilo"]
    hard_stops = profilo.get("hard_stops", [])
    hard_stops.append({"label": label.strip(), "motivo": motivo.strip()})
    profilo["hard_stops"] = hard_stops

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE soggetti SET profilo = %s WHERE id = %s",
            (json.dumps(profilo, ensure_ascii=False), soggetto_id),
        )
        conn.commit()

    return RedirectResponse(url=f"/soggetti/{soggetto_id}?tab=vincoli&saved=1", status_code=303)


@router.post("/{soggetto_id}/vantaggio")
def soggetto_add_vantaggio(
    request: Request,
    soggetto_id: int,
    label: str = Form(""),
    dettaglio: str = Form(""),
    conn=Depends(get_db),
):
    """Aggiunge vantaggio competitivo al soggetto."""
    s = _load_soggetto(conn, soggetto_id)
    if not s or not label.strip():
        return RedirectResponse(url=f"/soggetti/{soggetto_id}?tab=vincoli", status_code=303)

    profilo = s["profilo"]
    vantaggi = profilo.get("vantaggi", [])
    vantaggi.append({"label": label.strip(), "dettaglio": dettaglio.strip()})
    profilo["vantaggi"] = vantaggi

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE soggetti SET profilo = %s WHERE id = %s",
            (json.dumps(profilo, ensure_ascii=False), soggetto_id),
        )
        conn.commit()

    return RedirectResponse(url=f"/soggetti/{soggetto_id}?tab=vincoli&saved=1", status_code=303)


def _safe_int(val, default=None):
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default
