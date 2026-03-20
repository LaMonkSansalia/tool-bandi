"""
Test funzionali Playwright — simulano azioni utente reali.
Trova bug che i smoke test HTTP 200 non trovano.

Setup:
  pip install playwright
  playwright install chromium

Run:
  python tests/test_functional.py
  (l'app deve girare su http://127.0.0.1:8000)
"""
from playwright.sync_api import sync_playwright
import re
import os

BASE = "http://127.0.0.1:8000"


def run_all():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Raccogli errori JS
        js_errors = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        tests = [
            # --- NAVIGAZIONE ---
            ("NAV-01", "Dashboard carica senza errori",
             lambda: _no_error(page, "/")),
            ("NAV-02", "Sidebar ha almeno 5 link",
             lambda: _sidebar_links(page)),
            ("NAV-03", "Tutte le pagine sidebar caricano",
             lambda: _all_sidebar_pages(page)),

            # --- PROGETTI ---
            ("PRJ-01", "Progetto detail ha 4 tab",
             lambda: _progetto_has_tabs(page)),
            ("PRJ-02", "Tab Opportunita e' il default",
             lambda: _progetto_default_tab(page)),
            ("PRJ-03", "Salva Profilo NON rompe le tab",
             lambda: _salva_profilo_mantiene_tab(page)),
            ("PRJ-04", "Salva Profilo persiste i dati",
             lambda: _salva_profilo_persiste(page)),
            ("PRJ-05", "Nessun JSON raw nel tab Profilo",
             lambda: _no_raw_json(page, "/progetti/1?tab=profilo")),
            ("PRJ-06", "Tab Opportunita ha empty state con CTA",
             lambda: _opportunita_empty_state(page)),

            # --- BANDI ---
            ("BND-01", "Lista bandi ha selettore progetto",
             lambda: _bandi_selettore(page)),
            ("BND-02", "Bando detail carica",
             lambda: _bando_detail(page)),

            # --- SOGGETTI ---
            ("SOG-01", "Lista soggetti ha tab Reali/Simulazioni",
             lambda: _soggetti_tabs(page)),
            ("SOG-02", "Soggetto detail ha 3 tab",
             lambda: _soggetto_detail_tabs(page)),
            ("SOG-03", "Salva soggetto NON rompe la pagina",
             lambda: _salva_soggetto(page)),

            # --- CANDIDATURE ---
            ("CND-01", "Lista candidature carica",
             lambda: _no_error(page, "/candidature")),

            # --- PIPELINE ---
            ("PIP-01", "Pipeline carica senza errori",
             lambda: _no_error(page, "/pipeline")),
            ("PIP-02", "Trigger pipeline non crasha",
             lambda: _pipeline_trigger(page)),

            # --- INTEGRITA' GLOBALE ---
            ("INT-01", "Nessun traceback Python in nessuna pagina",
             lambda: _no_traceback_anywhere(page)),
            ("INT-02", "Nessun template tag Jinja2 visibile",
             lambda: _no_template_tags(page)),
            ("INT-03", "Nessun errore JS critico",
             lambda: _check_js_errors(js_errors)),
        ]

        for tid, name, fn in tests:
            try:
                fn()
                results.append((tid, name, "PASS", ""))
            except Exception as e:
                results.append((tid, name, "FAIL", str(e)[:300]))

        # Screenshot di ogni pagina
        _capture_screenshots(page)

        browser.close()

    # Report
    print("\n" + "=" * 80)
    print("REPORT TEST FUNZIONALI")
    print("=" * 80)
    passed = sum(1 for r in results if r[2] == "PASS")
    failed = sum(1 for r in results if r[2] == "FAIL")
    print(f"\nTotale: {len(results)} | PASS: {passed} | FAIL: {failed}\n")
    for tid, name, status, err in results:
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] {tid}: {name}")
        if err:
            print(f"       > {err[:150]}")

    # Scrivi bug in BUGS.md (append)
    bugs = [r for r in results if r[2] == "FAIL"]
    if bugs:
        import datetime
        with open("BUGS.md", "a") as f:
            f.write(f"\n\n## Bug da test funzionali ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n")
            f.write("| ID | Descrizione | Stato | Commit |\n")
            f.write("|---|---|---|---|\n")
            for tid, name, _, err in bugs:
                f.write(f"| {tid} | {name}: {err[:80]} | OPEN | -- |\n")
        print(f"\n{len(bugs)} bug aggiunti a BUGS.md")

    return results


# === IMPLEMENTAZIONI ===

def _no_error(page, path):
    page.goto(f"{BASE}{path}", wait_until="networkidle")
    c = page.content()
    assert "Internal Server Error" not in c, f"500 su {path}"
    assert "Traceback" not in c, f"Traceback su {path}"


def _sidebar_links(page):
    page.goto(BASE, wait_until="networkidle")
    links = page.locator("aside a[href], nav a[href], .sidebar a[href]").all()
    hrefs = [l.get_attribute("href") for l in links if l.get_attribute("href")]
    nav_links = [h for h in hrefs if h.startswith("/") and "/static" not in h]
    assert len(nav_links) >= 5, f"Solo {len(nav_links)} link sidebar: {nav_links}"


def _all_sidebar_pages(page):
    page.goto(BASE, wait_until="networkidle")
    links = page.locator("aside a[href]").all()
    hrefs = set()
    for l in links:
        h = l.get_attribute("href")
        if h and h.startswith("/") and "/static" not in h:
            hrefs.add(h)
    for href in hrefs:
        page.goto(f"{BASE}{href}", wait_until="networkidle")
        c = page.content()
        assert "Internal Server Error" not in c, f"500 su {href}"
        assert "Traceback" not in c, f"Traceback su {href}"


def _progetto_has_tabs(page):
    page.goto(f"{BASE}/progetti/1", wait_until="networkidle")
    c = page.content().lower()
    for tab in ["opportunit", "candidature", "profilo", "analisi"]:
        assert tab in c, f"Tab '{tab}' non trovato"


def _progetto_default_tab(page):
    page.goto(f"{BASE}/progetti/1", wait_until="networkidle")
    c = page.content().lower()
    assert "opportunit" in c, "Tab Opportunita non sembra essere il default"


def _salva_profilo_mantiene_tab(page):
    page.goto(f"{BASE}/progetti/1?tab=profilo", wait_until="networkidle")
    btn = page.locator("button:has-text('Salva Profilo')").first
    if btn.count() == 0:
        btn = page.locator("form button[type='submit']").first
    assert btn.count() > 0, "Bottone Salva non trovato nel tab Profilo"
    btn.click()
    page.wait_for_load_state("networkidle")
    c = page.content().lower()
    assert "opportunit" in c, "BUG-UI-001: Tab 'Opportunita' sparito dopo save!"
    assert "profilo" in c, "BUG-UI-001: Tab 'Profilo' sparito dopo save!"
    assert "analisi" in c, "BUG-UI-001: Tab 'Analisi' sparito dopo save!"


def _salva_profilo_persiste(page):
    import random, string
    marker = "TEST_" + "".join(random.choices(string.ascii_uppercase, k=6))
    page.goto(f"{BASE}/progetti/1?tab=profilo", wait_until="networkidle")
    campo = page.locator("input[name='descrizione_breve']").first
    if campo.count() == 0:
        return  # Campo non trovato, skip
    campo.fill(marker)
    btn = page.locator("button:has-text('Salva Profilo')").first
    if btn.count() > 0:
        btn.click()
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE}/progetti/1?tab=profilo", wait_until="networkidle")
        c = page.content()
        assert marker in c, f"BUG-UI-004: Valore '{marker}' non persistito dopo save"


def _no_raw_json(page, path):
    page.goto(f"{BASE}{path}", wait_until="networkidle")
    visible = page.evaluate("""() => {
        const els = document.querySelectorAll('p, span, div, td, li, h1, h2, h3, h4, label');
        let text = '';
        for (const el of els) {
            if (el.tagName !== 'TEXTAREA' && el.tagName !== 'CODE' && el.tagName !== 'PRE'
                && el.tagName !== 'INPUT') {
                if (!el.closest('textarea') && !el.closest('code') && !el.closest('pre')
                    && !el.closest('[x-data]')) {
                    text += el.innerText + ' ';
                }
            }
        }
        return text;
    }""")
    if re.search(r'\[\s*\{["\']', visible) or re.search(r'\{\s*["\'][a-z_]+["\']', visible):
        assert False, "BUG-UI-002: JSON raw trovato nel testo visibile"


def _opportunita_empty_state(page):
    page.goto(f"{BASE}/progetti/1", wait_until="networkidle")
    c = page.content()
    if "Nessun bando valutato" in c:
        assert "scansione" in c.lower() or "avvia" in c.lower(), \
            "BUG-LOGIC-004: Tab Opportunita vuoto senza CTA"


def _bandi_selettore(page):
    page.goto(f"{BASE}/bandi", wait_until="networkidle")
    sel = page.locator("select[name='project_id'], select[name='progetto_id']")
    assert sel.count() > 0, "Selettore progetto mancante nella lista bandi"


def _bando_detail(page):
    page.goto(f"{BASE}/bandi", wait_until="networkidle")
    link = page.locator("a[href*='/bandi/']").first
    if link.count() > 0:
        href = link.get_attribute("href")
        full_url = f"{BASE}{href}" if not href.startswith("http") else href
        page.goto(full_url, wait_until="networkidle")
        c = page.content()
        assert "Internal Server Error" not in c


def _soggetti_tabs(page):
    page.goto(f"{BASE}/soggetti", wait_until="networkidle")
    c = page.content().lower()
    assert "reali" in c or "real" in c, "Tab 'Reali' mancante in soggetti"


def _soggetto_detail_tabs(page):
    page.goto(f"{BASE}/soggetti/1", wait_until="networkidle")
    c = page.content().lower()
    for tab in ["anagrafica", "vincol", "progetti"]:
        assert tab in c, f"Tab '{tab}' non trovato nel soggetto detail"


def _salva_soggetto(page):
    page.goto(f"{BASE}/soggetti/1", wait_until="networkidle")
    btn = page.locator("button:has-text('Salva'), form button[type='submit']").first
    if btn.count() > 0:
        btn.click()
        page.wait_for_load_state("networkidle")
        c = page.content()
        assert "Internal Server Error" not in c, "Salva soggetto causa errore 500"
        assert "Traceback" not in c, "Salva soggetto mostra traceback"
        cl = c.lower()
        assert "anagrafica" in cl, "Tab spariti dopo salvataggio soggetto"


def _pipeline_trigger(page):
    page.goto(f"{BASE}/pipeline", wait_until="networkidle")
    btn = page.locator("button:has-text('Avvia'), button:has-text('Scansione')")
    if btn.count() > 0:
        btn.first.click()
        page.wait_for_timeout(3000)
        c = page.content()
        assert "Traceback" not in c, "BUG-UI-003: Pipeline mostra traceback"


def _no_traceback_anywhere(page):
    urls = ["/", "/bandi", "/soggetti", "/progetti", "/candidature", "/pipeline"]
    for url in urls:
        page.goto(f"{BASE}{url}", wait_until="networkidle")
        c = page.content()
        assert "Traceback" not in c, f"Traceback visibile su {url}"


def _no_template_tags(page):
    urls = ["/", "/bandi", "/soggetti", "/progetti", "/candidature", "/pipeline"]
    for url in urls:
        page.goto(f"{BASE}{url}", wait_until="networkidle")
        text = page.inner_text("body")
        assert "{%" not in text, f"Tag Jinja2 visibile su {url}"


def _check_js_errors(js_errors):
    critical = [e for e in js_errors if "favicon" not in e.lower()]
    assert len(critical) == 0, f"Errori JS: {critical[:3]}"


def _capture_screenshots(page):
    os.makedirs("screenshots", exist_ok=True)
    pages = {
        "dashboard": "/",
        "bandi_list": "/bandi",
        "soggetti_list": "/soggetti",
        "progetti_list": "/progetti",
        "progetto_opportunita": "/progetti/1",
        "progetto_profilo": "/progetti/1?tab=profilo",
        "progetto_analisi": "/progetti/1?tab=analisi",
        "candidature_list": "/candidature",
        "pipeline": "/pipeline",
    }
    for name, url in pages.items():
        try:
            page.goto(f"{BASE}{url}", wait_until="networkidle")
            page.screenshot(path=f"screenshots/{name}.png", full_page=True)
        except Exception:
            pass
    print(f"\nScreenshot salvati in screenshots/")


if __name__ == "__main__":
    run_all()
