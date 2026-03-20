"""
Browser test — verifica interazioni HTMX, form, tab switching, JS errors.
Richiede: uvicorn running + playwright installato.
Esegui: venv/bin/python -m pytest tests/test_browser.py -v
        venv/bin/python -m pytest tests/test_browser.py -v --headed  (per vedere il browser)
"""
import pytest
from playwright.sync_api import Page, expect

BASE = "http://127.0.0.1:8000"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture: cattura errori console JS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def console_errors(page: Page):
    """Raccoglie errori JS dalla console del browser."""
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


# ═══════════════════════════════════════════════════════════════════════════════
# Sidebar navigation
# ═══════════════════════════════════════════════════════════════════════════════

def test_sidebar_has_all_nav_links(page: Page):
    """Sidebar deve avere 6 link di navigazione."""
    page.goto(f"{BASE}/")
    page.wait_for_load_state("networkidle")
    sidebar = page.locator("aside")
    links = sidebar.locator("a[href]")
    count = links.count()
    assert count == 6, f"Sidebar ha {count} link, attesi 6"


def test_sidebar_navigation_works(page: Page):
    """Cliccando su ogni voce sidebar si naviga alla pagina corretta."""
    nav_targets = [
        ("/soggetti", "Soggetti"),
        ("/progetti", "Progetti"),
        ("/bandi", "Bandi"),
        ("/candidature", "Candidature"),
        ("/pipeline", "Pipeline"),
    ]
    for href, label in nav_targets:
        # Fresh navigation each time to avoid hx-boost timing issues
        page.goto(f"{BASE}/")
        page.wait_for_load_state("networkidle")
        link = page.locator(f'aside a[href="{href}"]')
        if link.count() > 0:
            link.click()
            page.wait_for_url(f"**{href}", timeout=5000)
            assert href in page.url, f"Expected URL containing {href}, got {page.url}"


def test_sidebar_toggle(page: Page):
    """Il bottone hamburger deve nascondere/mostrare la sidebar."""
    page.goto(f"{BASE}/")
    page.wait_for_load_state("networkidle")
    sidebar = page.locator("aside")
    expect(sidebar).to_be_visible()
    # Click hamburger
    page.locator("button", has=page.locator("svg path[d*='M3.75 6.75']")).click()
    page.wait_for_timeout(300)  # attendi animazione
    expect(sidebar).to_be_hidden()


# ═══════════════════════════════════════════════════════════════════════════════
# Progetto tab switching (HTMX)
# ═══════════════════════════════════════════════════════════════════════════════

def test_progetto_tab_switching(page: Page, console_errors):
    """Click su tab Profilo carica il contenuto via HTMX senza full reload."""
    page.goto(f"{BASE}/progetti/1")
    page.wait_for_load_state("networkidle")

    # Click tab "Profilo"
    page.locator("button", has_text="Profilo").click()
    page.wait_for_load_state("networkidle")

    # Deve caricare il form profilo con sezioni
    expect(page.get_by_role("heading", name="Descrizione")).to_be_visible(timeout=5000)

    # Click tab "Analisi"
    page.locator("button", has_text="Analisi").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#tab-content")).to_contain_text("Gap", timeout=5000)

    assert len(console_errors) == 0, f"JS errors: {console_errors}"


# ═══════════════════════════════════════════════════════════════════════════════
# Soggetto tab switching (HTMX)
# ═══════════════════════════════════════════════════════════════════════════════

def test_soggetto_tab_switching(page: Page, console_errors):
    """Click su tab Vincoli carica il partial senza full page reload."""
    page.goto(f"{BASE}/soggetti/1")
    page.wait_for_load_state("networkidle")

    # Sidebar deve esserci una sola volta
    assert page.locator("aside").count() == 1

    # Click tab "Vincoli & Vantaggi"
    page.locator("button", has_text="Vincoli").click()
    page.wait_for_load_state("networkidle")

    # Dopo il click, sidebar deve essere ancora 1 (non duplicata)
    assert page.locator("aside").count() == 1, "Sidebar duplicata dopo tab switch"

    # Click tab "Progetti"
    page.locator("button", has_text="Progetti").click()
    page.wait_for_load_state("networkidle")
    assert page.locator("aside").count() == 1, "Sidebar duplicata dopo tab Progetti"

    assert len(console_errors) == 0, f"JS errors: {console_errors}"


# ═══════════════════════════════════════════════════════════════════════════════
# Bando tab switching
# ═══════════════════════════════════════════════════════════════════════════════

def test_bando_tab_switching_with_project(page: Page, console_errors):
    """Bando detail con project: 3 tab funzionanti via HTMX."""
    page.goto(f"{BASE}/bandi/1?project_id=1")
    page.wait_for_load_state("networkidle")

    # Tab Dettaglio
    page.locator("button", has_text="Dettaglio").click()
    page.wait_for_load_state("networkidle")
    assert page.locator("aside").count() == 1, "Sidebar duplicata su tab Dettaglio"

    # Tab Testo
    page.locator("button", has_text="Testo").click()
    page.wait_for_load_state("networkidle")
    assert page.locator("aside").count() == 1, "Sidebar duplicata su tab Testo"

    assert len(console_errors) == 0, f"JS errors: {console_errors}"


# ═══════════════════════════════════════════════════════════════════════════════
# Soggetti list — tab Reali/Simulazioni
# ═══════════════════════════════════════════════════════════════════════════════

def test_soggetti_tab_reali_simulazioni(page: Page):
    """Switch tra tab Reali e Simulazioni con JS."""
    page.goto(f"{BASE}/soggetti")
    page.wait_for_load_state("networkidle")

    # Tab Reali visibile di default
    reali_panel = page.locator("#tab-reali")
    sim_panel = page.locator("#tab-simulazioni")
    expect(reali_panel).to_be_visible()
    expect(sim_panel).to_be_hidden()

    # Click Simulazioni
    page.locator("button", has_text="Simulazioni").click()
    page.wait_for_timeout(200)
    expect(reali_panel).to_be_hidden()
    expect(sim_panel).to_be_visible()

    # Bottone "Nuovo" deve puntare a simulazione
    btn = page.locator("#btn-nuovo-soggetto")
    href = btn.get_attribute("href")
    assert "tipo=simulazione" in href, f"Nuovo Soggetto non punta a simulazione: {href}"


def test_soggetti_nuovo_from_simulazioni_tab(page: Page):
    """Da tab Simulazioni, 'Nuovo Soggetto' deve aprire il form con tipo=simulazione."""
    page.goto(f"{BASE}/soggetti")
    page.wait_for_load_state("networkidle")

    # Switch a Simulazioni
    page.locator("button", has_text="Simulazioni").click()

    # Wait for JS to update the href
    btn = page.locator("#btn-nuovo-soggetto")
    expect(btn).to_have_attribute("href", "/soggetti/nuovo?tipo=simulazione", timeout=2000)

    # Click Nuovo Soggetto
    btn.click()
    page.wait_for_url("**/soggetti/nuovo*", timeout=5000)
    page.wait_for_load_state("networkidle")

    # Form deve avere hidden input tipo=simulazione
    tipo_input = page.locator('input[name="tipo"]')
    expect(tipo_input).to_have_value("simulazione")

    # Badge "Simulazione" visibile nell'header
    expect(page.locator("text=Simulazione")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════════
# Bando testo tab — toggle sorgente
# ═══════════════════════════════════════════════════════════════════════════════

def test_bando_testo_toggle_source(page: Page):
    """Il tab testo deve avere toggle tra testo pulito e sorgente."""
    page.goto(f"{BASE}/bandi/1?project_id=1")
    page.wait_for_load_state("networkidle")

    # Click tab Testo
    page.locator("button", has_text="Testo").click()
    page.wait_for_load_state("networkidle")

    # Cerca il bottone "Mostra sorgente"
    toggle = page.locator("text=Mostra sorgente")
    if toggle.count() > 0:
        toggle.click()
        page.wait_for_timeout(200)
        # Ora deve dire "Mostra testo"
        expect(page.locator("text=Mostra testo")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════════
# Nessun errore JS su navigazione completa
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_console_errors_on_navigation(page: Page, console_errors):
    """Nessun errore JavaScript navigando tutte le pagine principali."""
    routes = ["/", "/bandi", "/soggetti", "/progetti", "/candidature", "/pipeline",
              "/soggetti/1", "/progetti/1", "/bandi/1"]
    for route in routes:
        page.goto(f"{BASE}{route}")
        page.wait_for_load_state("networkidle")
    assert len(console_errors) == 0, f"Console errors: {console_errors}"
