# BUGS.md — Bug Tracker

## Come usare

1. Esegui smoke test: `venv/bin/python -m pytest tests/test_smoke.py -v`
2. Esegui browser test: `venv/bin/python -m pytest tests/test_browser.py -v`
3. Per ogni test FAILED, copia qui il nome del test + output
4. Dai questo file a Claude Code con: "Fixa tutti i bug in BUGS.md"

## Bug risolti

### BUG-FIXED-001: Sidebar doppia innestata
- **Pagina:** `/bandi/83?project_id=1`, `/soggetti/2?tab=vincoli`
- **Causa:** tab_bar macro appendeva `/tab/key` dopo query string; soggetto tabs usavano full page URL in `hx-get`
- **Fix:** separato base_url da query_string nella macro; creata route partial `/soggetti/{id}/tab/{name}`
- **Test:** `test_no_double_sidebar_on_any_page`, `test_htmx_partials_are_not_full_pages`

### BUG-FIXED-002: Bandi list full-screen (perde navigazione)
- **Pagina:** `/bandi`
- **Causa:** `hx-boost="true"` su body inviava `HX-Request` header; la route restituiva il partial invece della full page
- **Fix:** check `HX-Target == "bandi-table"` instead of `HX-Request`
- **Test:** `test_bandi_list_loads`, `test_no_double_sidebar_on_any_page`

### BUG-FIXED-003: Bando testo mostra HTML grezzo
- **Pagina:** `/bandi/53` tab Testo
- **Causa:** `raw_text` contiene HTML della pagina sorgente, mostrato in `<pre>` senza pulizia
- **Fix:** filtro Jinja2 `clean_html` (rimuove script/style/tags), toggle "Mostra sorgente"
- **Test:** `test_bando_testo_no_raw_html_tags`, `test_bando_testo_toggle_source`

### BUG-FIXED-004: JSON illeggibile nel profilo progetto
- **Pagina:** `/progetti/1` tab Profilo
- **Causa:** `| tojson` produceva JSON compatto su una riga
- **Fix:** `| tojson(indent=2)` + textarea rows aumentati
- **Test:** `test_progetto_profilo_json_formatted`

### BUG-FIXED-005: Soggetto tipo sempre "reale"
- **Pagina:** `/soggetti` → Nuovo dalla tab Simulazioni
- **Causa:** form non passava `tipo`; route ignorava contesto tab attiva
- **Fix:** query param `?tipo=simulazione`, hidden input nel form, route legge tipo
- **Test:** `test_soggetto_form_simulazione`, `test_soggetti_nuovo_from_simulazioni_tab`

### BUG-FIXED-006: hx-boost non passa query params su link JS-modificati
- **Pagina:** `/soggetti` → click "Nuovo" dopo switch tab
- **Causa:** hx-boost intercetta click su `<a>` ma non rispetta href modificato via JS
- **Fix:** `hx-boost="false"` sul bottone "Nuovo Soggetto" (forza navigazione browser)
- **Test:** `test_soggetti_nuovo_from_simulazioni_tab`

### BUG-FIXED-007: Salva Profilo rompe le tab (BUG-UI-001)
- **Pagina:** `/progetti/3?tab=profilo`
- **Causa:** `hx-boost="true"` su body intercettava form POST; redirect 303 seguito da HTMX con `HX-Request` header → server restituiva partial senza tab
- **Fix:** `hx-boost="false"` su entrambi i form; check server-side tightened a `HX-Target == "tab-content"`
- **Commit:** `14357c8`

### BUG-FIXED-008: JSON raw visibile nel tab Profilo (BUG-UI-002)
- **Pagina:** `/progetti/3?tab=profilo`
- **Causa:** partner, piano_lavoro, kpi, documenti_supporto mostrati come JSON grezzo in textarea
- **Fix:** Alpine.js dynamic forms con `x-data`, `x-for`, add/remove, hidden input serialized
- **Commit:** `57030c8`

### BUG-FIXED-009: Pipeline fallisce sempre (BUG-UI-003)
- **Pagina:** `/pipeline`
- **Causa:** query `pipeline_runs` senza try/except crashava se tabella non esisteva
- **Fix:** try/except con rollback + messaggi errore in UI + `hx-boost="false"` su form trigger
- **Commit:** `ba20c7f`

### BUG-FIXED-010: Salvataggio profilo perde dati (BUG-UI-004)
- **Pagina:** `/progetti/3?tab=profilo`
- **Causa:** `tipo_investimento` nel form ma non nel POST handler (perso); `costituita` default `Form("1")` = sempre True; `zone_speciali` hardcoded `[]`
- **Fix:** aggiunto tipo_investimento al handler; fix default costituita a `Form("")`; aggiunto zone_speciali multi-checkbox + getlist()
- **Commit:** `d7e7fe6`

### BUG-FIXED-011: Soggetto save non rivaluta hard stops (BUG-LOGIC-001)
- **Pagina:** `/soggetti/{id}`
- **Causa:** salvataggio soggetto aggiornava DB ma non ricalcolava hard stops / score sui progetti associati
- **Fix:** dopo save, query progetti del soggetto + `rivaluta_progetto()` in background thread per ciascuno
- **Commit:** `85db886`

### BUG-FIXED-012: Qualifiche soggetto decorative (BUG-LOGIC-002)
- **Causa:** `qualifica_match` handler esisteva in configurable_scorer.py ma i 3 template di scoring non lo includevano
- **Fix:** aggiunto `qualifica_match` rule a ICT/Freelancer, Turismo/Cultura, E-commerce/PMI
- **Commit:** `361fe2d`

### BUG-FIXED-013: Profilo save non rivaluta bandi (BUG-LOGIC-003)
- **Pagina:** `/progetti/{id}?tab=profilo`
- **Causa:** salvataggio profilo aggiornava JSONB ma non ricalcolava score/hard_stops sulle valutazioni
- **Fix:** background thread `rivaluta_progetto()` dopo save profilo, messaggio "Rivalutazione in corso" in UI
- **Commit:** `fbe8012`

### BUG-FIXED-014: Tab Opportunita' senza CTA (BUG-LOGIC-004)
- **Pagina:** `/progetti/{id}` tab Opportunita'
- **Causa:** empty state mostrava solo "Nessun bando valutato" senza azione suggerita
- **Fix:** icona search, testo descrittivo, link "Avvia scansione" a /pipeline
- **Commit:** `b05bc52`

### BUG-FIXED-015: Sidebar doppia — fix generico a livello middleware
- **Pagina:** tutte (ricorrente: `/bandi/{id}?project_id=X`, soggetti vincoli, workspace)
- **Causa:** `hx-boost="true"` su body intercettava form POST nelle tab partial; redirect 303 con HX-Request restituiva pagina completa con layout → sidebar iniettata dentro il contenuto
- **Fix 3 livelli:**
  1. **Middleware `HTMXLayoutMiddleware`** — rileva richieste HTMX partial (HX-Target != body) che ricevono layout completo e lo stripa, estraendo solo il contenuto
  2. **`hx-boost="false"` su 6 form in partials** — progetto_tab_scoring, soggetto_tab_vincoli (2 form), workspace_tab_note, workspace_tab_checklist, workspace_tab_documenti_full
  3. **Audit completo** — verificati tutti i 37 partial (nessuno estende layout), tutti gli hx-get (puntano a tab partial), tutte le route (restituiscono partial corretti)

### BUG-FIXED-016: DB staging vuoto — contatori tutti a 0 (A-01)
- **Pagina:** Tutte (dashboard, progetti, soggetti)
- **Causa:** Dati bandi (125 bandi, 250 evaluations) esistevano solo nel DB locale engine-postgres-1, mai migrati su staging. Volume bandi-ui_pgdata corretto ma le tabelle erano vuote.
- **Fix:** pg_dump locale + restore su staging (TRUNCATE + INSERT con --column-inserts --disable-triggers)

### BUG-FIXED-017: Tab active non evidenziato al click (B-01)
- **Pagina:** soggetto_detail, progetto_detail, candidatura_workspace
- **Causa:** Tab button inline senza onclick handler per switch classi CSS (bando_detail usava tab_bar macro con onclick, le altre pagine no)
- **Fix:** Aggiunto onclick handler su tutti i tab button inline (3 pagine)

### BUG-FIXED-018: Stat card dashboard non cliccabili (B-02)
- **Pagina:** Dashboard /
- **Causa:** Macro stat_card non supportava href
- **Fix:** Aggiunto parametro href alla macro stat_card + wrapping in `<a>` se presente. 8 card ora linkano a pagine filtrate.

### BUG-FIXED-019: Valori DB raw nelle label (B-08)
- **Pagina:** progetto_detail, progetto_tab_analisi
- **Causa:** `soggetto.forma_giuridica` mostrato raw (es. `impresa_individuale`)
- **Fix:** Filtro Jinja2 `forma_label` (+ `regime_label`, `settore_label`) registrato in main.py usando dict da FORME_GIURIDICHE

### BUG-FIXED-020: "Completezza50%" senza spazio (B-09)
- **Pagina:** /progetti (lista)
- **Causa:** Container completezza bar troppo stretto (w-24 = 96px) per "Completezza" + "50%"
- **Fix:** Allargato a w-32 (128px)

### BUG-FIXED-021: Vincoli non calcolati dall'engine (B-05)
- **Pagina:** /soggetti/{id} tab Vincoli & Vantaggi
- **Causa:** Mostrava solo vincoli manuali dal profilo JSONB, ignorava hard_stop_reason dalle project_evaluations
- **Fix:** Nuova query _get_vincoli_calcolati() aggrega hard_stop_reason per soggetto, mostra vincoli calcolati sopra quelli manuali con conteggio bandi bloccati

## Bug aperti (audit manuale)

### BUG-AUDIT-B03: Dashboard incompleta — mancano 5 blocchi spec
- **Pagina:** Dashboard /
- **Spec:** §5.1 richiede candidature per stato, nuovi bandi, progetti incompleti, hard stop impattanti, timeline
- **Priorita':** Media

### BUG-AUDIT-B04: Lista soggetti — card anziché tabella
- **Pagina:** /soggetti
- **Spec:** §5.2.1 richiede tabella con hard stop count, bandi bloccati, completezza
- **Priorita':** Media

### BUG-AUDIT-B07: Slug interno visibile in tab Progetti
- **Pagina:** /soggetti/{id} tab Progetti
- **Priorita':** Bassa

### BUG-AUDIT-B10: Score medio e bandi match mancanti in lista progetti
- **Pagina:** /progetti
- **Spec:** §5.3.1 richiede score medio + bandi compatibili
- **Priorita':** Media

### BUG-AUDIT-B11: Scoring rules vuote (non pre-compilate)
- **Pagina:** /progetti/{id} tab Profilo
- **Priorita':** Media

### BUG-AUDIT-B12: PDS senza settore
- **Pagina:** /progetti
- **Priorita':** Bassa

### BUG-AUDIT-B13: Tab Analisi — sotto-sezioni spec mancanti
- **Pagina:** /progetti/{id} tab Analisi
- **Priorita':** Bassa
