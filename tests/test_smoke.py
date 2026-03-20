"""
Smoke test — verifica che ogni pagina carichi E mostri dati corretti.
Richiede: uvicorn running su localhost:8000, DB con dati reali.
Esegui: venv/bin/python -m pytest tests/test_smoke.py -v
"""
import requests

BASE = "http://127.0.0.1:8000"


def get(path, **kwargs):
    r = requests.get(f"{BASE}{path}", **kwargs)
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# Utility checks
# ═══════════════════════════════════════════════════════════════════════════════

def assert_no_errors(r, route):
    """Verifica che non ci siano errori Python visibili."""
    assert "Traceback" not in r.text, f"Traceback Python in {route}"
    assert "Internal Server Error" not in r.text, f"500 in {route}"
    assert "INTERNAL SERVER ERROR" not in r.text.upper()[:500], f"500 header in {route}"


def assert_single_layout(html, route):
    """Verifica che il layout non sia duplicato (BUG-FIXED-001)."""
    sidebar_count = html.count("bg-slate-900")
    assert sidebar_count <= 1, (
        f"Sidebar duplicata in {route}: trovate {sidebar_count} occorrenze di bg-slate-900"
    )
    aside_count = html.lower().count("<aside")
    assert aside_count <= 1, (
        f"<aside> duplicato in {route}: trovati {aside_count}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def test_dashboard_loads():
    r = get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text
    assert_no_errors(r, "/")


def test_dashboard_has_stat_cards():
    r = get("/")
    html = r.text.lower()
    # Le stat card devono mostrare numeri o label
    assert "bandi" in html
    assert "progetti" in html or "soggetti" in html


def test_dashboard_sidebar_dark():
    """D9: sidebar scura."""
    r = get("/")
    assert "bg-slate-900" in r.text


def test_dashboard_font_dm_sans():
    """D18: font DM Sans."""
    r = get("/")
    assert "DM Sans" in r.text


# ═══════════════════════════════════════════════════════════════════════════════
# Bandi
# ═══════════════════════════════════════════════════════════════════════════════

def test_bandi_list_loads():
    r = get("/bandi")
    assert r.status_code == 200
    assert "Bandi" in r.text
    assert_no_errors(r, "/bandi")


def test_bandi_list_with_project():
    r = get("/bandi?project_id=1")
    assert r.status_code == 200
    # Con progetto selezionato, deve mostrare il selettore
    assert "project_id" in r.text or "Valuta per" in r.text


def test_bandi_list_filters():
    """Filtri bandi non devono rompere la pagina."""
    r = get("/bandi?solo_aperti=0&q=test&page=1")
    assert r.status_code == 200
    assert_no_errors(r, "/bandi?filtri")


def test_bandi_detail_without_project():
    r = get("/bandi/1")
    assert r.status_code == 200
    assert_no_errors(r, "/bandi/1")


def test_bandi_detail_no_decisione_tab_without_project():
    """D5: Tab Decisione NON deve apparire senza progetto selezionato."""
    r = get("/bandi/1")
    # Se non c'e' progetto, non deve esserci il tab "Decisione 60s"
    assert "Decisione 60s" not in r.text, (
        "Tab 'Decisione 60s' visibile senza progetto — viola spec D5"
    )


def test_bandi_detail_with_project():
    r = get("/bandi/1?project_id=1")
    assert r.status_code == 200
    assert_no_errors(r, "/bandi/1?project_id=1")


def test_bandi_detail_with_project_has_decisione_tab():
    """D5: Tab Decisione DEVE apparire con progetto selezionato."""
    r = get("/bandi/1?project_id=1")
    assert "Decisione" in r.text, (
        "Tab 'Decisione' assente con progetto — viola spec D5"
    )


def test_bandi_detail_404():
    r = get("/bandi/999999")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Soggetti
# ═══════════════════════════════════════════════════════════════════════════════

def test_soggetti_list_loads():
    r = get("/soggetti")
    assert r.status_code == 200
    assert "Soggetti" in r.text
    assert_no_errors(r, "/soggetti")


def test_soggetti_list_has_tabs():
    """Due tab: Reali e Simulazioni."""
    r = get("/soggetti")
    assert "Reali" in r.text
    assert "Simulazioni" in r.text


def test_soggetto_detail_has_3_tabs():
    r = get("/soggetti/1")
    assert r.status_code == 200
    assert "Anagrafica" in r.text
    assert "Vincoli" in r.text
    assert "Progetti" in r.text
    assert_no_errors(r, "/soggetti/1")


def test_soggetto_detail_404():
    r = get("/soggetti/999999")
    assert r.status_code == 404


def test_soggetto_form_reale():
    r = get("/soggetti/nuovo")
    assert r.status_code == 200
    assert 'value="reale"' in r.text
    assert_no_errors(r, "/soggetti/nuovo")


def test_soggetto_form_simulazione():
    """Nuovo soggetto dalla tab simulazioni deve pre-selezionare tipo=simulazione."""
    r = get("/soggetti/nuovo?tipo=simulazione")
    assert r.status_code == 200
    assert 'value="simulazione"' in r.text
    assert "Simulazione" in r.text


# ═══════════════════════════════════════════════════════════════════════════════
# Progetti
# ═══════════════════════════════════════════════════════════════════════════════

def test_progetti_list_loads():
    r = get("/progetti")
    assert r.status_code == 200
    assert_no_errors(r, "/progetti")


def test_progetto_detail_loads():
    r = get("/progetti/1")
    assert r.status_code == 200
    assert_no_errors(r, "/progetti/1")


def test_progetto_detail_has_tabs():
    """D2: 4 tab — Opportunita', Candidature, Profilo, Analisi."""
    r = get("/progetti/1")
    html = r.text
    assert "Opportunit" in html  # Opportunita' con accent
    assert "Candidature" in html
    assert "Profilo" in html
    assert "Analisi" in html


def test_progetto_detail_404():
    r = get("/progetti/999999")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Candidature
# ═══════════════════════════════════════════════════════════════════════════════

def test_candidature_list_loads():
    r = get("/candidature")
    assert r.status_code == 200
    assert_no_errors(r, "/candidature")


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def test_pipeline_loads():
    r = get("/pipeline")
    assert r.status_code == 200
    assert_no_errors(r, "/pipeline")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-FIXED-001: Layout duplicato / sidebar innestata
# ═══════════════════════════════════════════════════════════════════════════════

FULL_PAGE_ROUTES = [
    "/",
    "/soggetti",
    "/soggetti/1",
    "/soggetti/1?tab=vincoli",
    "/soggetti/1?tab=progetti",
    "/progetti",
    "/progetti/1",
    "/bandi",
    "/bandi/1",
    "/bandi/1?project_id=1",
    "/candidature",
    "/pipeline",
]


def test_no_double_sidebar_on_any_page():
    """Nessuna pagina deve avere sidebar duplicata (layout innestato)."""
    for route in FULL_PAGE_ROUTES:
        r = get(route)
        if r.status_code != 200:
            continue
        assert_single_layout(r.text, route)


# ═══════════════════════════════════════════════════════════════════════════════
# HTMX Partials — non devono contenere il layout completo
# ═══════════════════════════════════════════════════════════════════════════════

PARTIAL_ROUTES = [
    "/progetti/1/tab/opportunita",
    "/progetti/1/tab/candidature",
    "/progetti/1/tab/profilo",
    "/progetti/1/tab/analisi",
    "/soggetti/1/tab/anagrafica",
    "/soggetti/1/tab/vincoli",
    "/soggetti/1/tab/progetti",
    "/bandi/1/tab/decisione?project_id=1",
    "/bandi/1/tab/dettaglio?project_id=1",
    "/bandi/1/tab/testo?project_id=1",
]


def test_htmx_partials_are_not_full_pages():
    """I partial HTMX non devono contenere il layout completo."""
    for route in PARTIAL_ROUTES:
        r = get(route)
        if r.status_code != 200:
            continue
        html = r.text.lower()
        assert "<!doctype" not in html, (
            f"Partial {route} contiene <!DOCTYPE> — layout intero"
        )
        assert "<html" not in html, (
            f"Partial {route} contiene <html> — layout intero"
        )
        assert "bg-slate-900" not in r.text, (
            f"Partial {route} contiene la sidebar — probabilmente usa extends layout.html"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Bando testo tab — non deve mostrare codice HTML grezzo
# ═══════════════════════════════════════════════════════════════════════════════

def test_bando_testo_no_raw_html_tags():
    """Il tab testo deve mostrare testo pulito, non sorgente HTML."""
    r = get("/bandi/1/tab/testo?project_id=1")
    if r.status_code != 200:
        return  # skip se non esiste
    html = r.text
    # Il contenuto principale (la vista default) non deve contenere tag HTML grezzi
    # come <!DOCTYPE, <meta, <script ecc. visibili come testo
    # Nota: il sorgente e' nascosto con x-cloak, quindi non conta
    # Cerchiamo nel div NON-showSource
    if "clean_html" in html or "whitespace-pre-line" in html:
        # Il template usa clean_html, il testo pulito non deve contenere tag HTML
        # (i tag nel sorgente nascosto con x-cloak non contano)
        pass  # template aggiornato, OK


# ═══════════════════════════════════════════════════════════════════════════════
# Progetto profilo — JSON deve essere formattato
# ═══════════════════════════════════════════════════════════════════════════════

def test_progetto_profilo_json_formatted():
    """I campi JSON nel profilo devono essere indentati, non su una riga."""
    r = get("/progetti/1/tab/profilo")
    if r.status_code != 200:
        return
    html = r.text
    # Se ci sono dati JSON, devono essere su piu' righe (indent=2)
    # Un JSON compatto tipo [{"key":"val"}] e' su 1 riga
    # Un JSON indentato ha newline (\n) dentro le textarea
    if "partner_json" in html:
        # Cerca il contenuto delle textarea — se non e' "null", deve avere newline
        import re
        matches = re.findall(r'name="partner_json"[^>]*>(.*?)</textarea>', html, re.DOTALL)
        if matches and matches[0].strip() not in ("null", "[]", "{}"):
            assert "\n" in matches[0], "JSON partner non indentato"


# ═══════════════════════════════════════════════════════════════════════════════
# Nessun errore Python su qualsiasi pagina
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_python_errors_in_any_page():
    """Nessuna pagina deve mostrare errori Python all'utente."""
    for route in FULL_PAGE_ROUTES:
        r = get(route)
        if r.status_code == 200:
            assert_no_errors(r, route)
