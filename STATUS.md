# Tool Bandi — Contesto & Status

**Versione:** 0.8.3-dev
**Ultimo aggiornamento:** 2026-03-20
**Repo:** GitHub — LaMonkSansalia/tool-bandi (rinominato da bandiresearcher il 2026-03-20)
**Inizio progetto:** 2026-03-02

---

## Cos'e'

Sistema per ricercare, analizzare, valutare e candidarsi a bandi pubblici italiani (finanziamenti, contributi, agevolazioni). Multi-soggetto, multi-progetto, multi-candidatura.

**Utente tipo:** consulente/imprenditore italiano che gestisce progetti propri e di clienti.
**Principio:** Human-in-the-loop obbligatorio. Il sistema prepara, l'umano decide e invia.

---

## Stack Tecnologico (attuale)

| Layer | Tecnologia | Note |
|-------|-----------|------|
| Engine | Python 3.14 + psycopg2 | Scrapy, Docling, Claude AI, ~10.920 LOC |
| Web framework | FastAPI + Jinja2 | Server-rendered, un processo Python |
| Interattivita' | HTMX + Alpine.js | Partial updates, modali, tab (~30KB) |
| Stile | Tailwind CSS (CDN dev, standalone CLI prod) | Classi dal mockup React |
| Database | PostgreSQL 16 + pgvector | Embeddings + full-text |
| Notifiche | Telegram bot | Alert nuovi bandi, scadenze, errori |
| Orchestrazione | Prefect 3.x | daily_scan cron "0 8 * * *" |
| Container | Docker: web (uvicorn) + db (pgvector) | 2 servizi |

---

## Architettura — 5 Entita'

```
SOGGETTO  → chi si candida (P.IVA, forma giuridica, sede) → determina hard stops
PROGETTO  → per cosa ci si candida (settore, budget, keywords) → determina scoring
BANDO     → opportunita' scraped (ente, scadenza, requisiti) → entita' indipendente
VALUTAZIONE = bando x progetto x soggetto → score, idoneita', gap analysis (READ-ONLY)
CANDIDATURA = workspace operativo → documenti, checklist, stati, note
```

**3 layer engine:**
1. **Intelligence** — Scraping + parsing PDF + profili
2. **Reasoning** — Hard stops + configurable scoring + gap analysis
3. **Execution** — Document generation + package builder

---

## Struttura Progetto

```
tool-bandi/
  engine/                  # Core Python (~10.920 LOC)
    scrapers/              # 7 spiders (invitalia, regione_sicilia, mimit, padigitale, inpa, comune_palermo, euroinfosicilia)
    parsers/               # Docling + Claude structurer (PDF → JSON)
    eligibility/           # hard_stops, configurable_scorer, gap_analyzer, rules
    generators/            # PDF (WeasyPrint), DOCX (python-docx), content (DSPy+Claude)
    pipeline/flows.py      # daily_scan, rivaluta_singolo, rivaluta_progetto
    projects/manager.py    # CRUD (soggetti, candidature, documenti)
    notifications/         # Telegram bot + alerts
    db/
      pool.py              # ThreadedConnectionPool singleton
      migrations/001-014   # Schema SQL

  web/                     # FastAPI web UI
    main.py                # App, Jinja2, static, lifespan, 8 router
    deps.py                # Depends: get_db, get_current_project_id, get_nav_context
    routes/                # 8 file (dashboard, soggetti, progetti, bandi, candidature, documenti, pipeline)
    services/              # display.py, state_machine.py, completezza.py
    templates/             # layout + 12 pages + 17 partials + 5 components
    static/                # htmx.min.js, alpine.min.js, input.css

  context/                 # Dati di contesto (company_profile, skills_matrix, bandi_target)
  sprints/                 # Documentazione sprint 0-4
  Dockerfile               # python:3.12-slim + uvicorn
  docker-compose.yml       # 2 servizi: web + db
```

---

## Progetti Attivi

| ID | Progetto | Soggetto | Settore | Scoring Template |
|----|----------|----------|---------|-----------------|
| 1 | La Monica ICT | La Monica Luciano (P.IVA) | ICT/Freelancer | ict_freelancer |
| 2 | Paese Delle Stelle | La Monica Luciano (P.IVA) | Turismo/Cultura | turismo_cultura |

**Soggetto principale:** La Monica Luciano — P.IVA, impresa individuale, regime forfettario, ATECO 62.20.10, Sicilia

---

## DB Schema (migrazioni)

| # | Migrazione | Stato |
|---|-----------|-------|
| 001 | Schema base (bandi, bando_documenti, bando_requisiti) | Deployato |
| 002 | company_embeddings (pgvector) | Deployato |
| 003 | bando_documenti_generati | Deployato |
| 004 | tipo_finanziamento + aliquota_fondo_perduto | Deployato |
| 005 | projects + project_evaluations (multi-progetto) | Deployato |
| 006 | Extended bandi (criteri_valutazione, documenti_da_allegare, parsing_confidence) | Deployato |
| 007 | (varie estensioni) | Deployato |
| 008 | Soggetti table | Deployato |
| 009 | Workspace fields (checklist, notes, completezza) su project_evaluations | Deployato |
| 010 | Seed soggetti (lamonica_piva, 250 evaluations migrate) | Deployato |
| 011 | Tabella `candidatura` (stati: bozza→lavorazione→sospesa→pronta→inviata→abbandonata) | Creata, non deployata |
| 012 | `documento_candidatura` + `versione_documento` (UUID PK, versioning, AI gen) | Creata, non deployata |
| 013 | Estensioni `soggetti` (tipo, simulazione_di, campi elevati da JSONB) | TODO |
| 014 | `hard_stop_reason` TEXT → `hard_stops` JSONB | Creata, non deployata |

---

## File di Riferimento (AUTORITA')

| File | Ruolo |
|------|-------|
| `context/spec/tool-bandi-spec (1).md` | Spec UI/UX — autorita' per navigazione, pagine, tab, flussi |
| `context/spec/tool-bandi-mockup.jsx` | Mockup React — autorita' per layout visuale, colori, componenti |

**Regola:** Quando spec e piano divergono → la spec vince (piu' recente).

---

## Changelog Completo

### v0.1.0 — Sprint 0: Fondamenta (2026-03-02)

- [x] Docker Compose: PostgreSQL 16 + pgvector, Redis 7, Prefect 3.x, Streamlit
- [x] Schema DB: 4 tabelle core (bandi, bando_documenti, bando_requisiti, bando_documenti_generati)
- [x] pgvector extension per embeddings (company_embeddings)
- [x] Python requirements + config centralizzato (config.py)
- [x] Company profile loader (load_profile.py)
- [x] Streamlit entry point con pagina profilo
- [x] Setup script per inizializzazione rapida

### v0.2.0 — Sprint 1: Prima Pipeline (2026-03-02)

- [x] **Invitalia Spider** — crawl bandi, estrazione metadata, download PDF
- [x] **Docling + Claude Parser** — markdown extraction da PDF, strutturazione JSON con DSPy
- [x] **Eligibility Engine (3 moduli):**
  - `hard_stops.py` — esclusione automatica da profilo aziendale
  - `scorer.py` — score 0-100 con bonus (Sicilia +15, under35 +10, ATECO +20, ZES +10, nuova impresa +10)
  - `gap_analyzer.py` — identifica requisiti mancanti (recuperabili vs bloccanti)
- [x] **Streamlit UI:**
  - Dashboard con metriche (trovati oggi/settimana, scadenze urgenti, score medio)
  - Lista bandi con filtri (stato, score, scadenza, ente)
  - Detail con requirements checklist, score breakdown, gap analysis
- [x] Scrapy → PostgreSQL pipeline con dedup (URL + SHA256 hash)
- [x] State machine: 8 stati (nuovo→analisi→idoneo→scartato→lavorazione→pronto→inviato→archiviato)

### v0.3.0 — Sprint 2: Scrapers & Scheduling (2026-03-02)

- [x] **6 production spiders:** regione_sicilia, mimit, padigitale, inpa, comune_palermo, euroinfosicilia
- [x] MePA spider: DEFERRED (richiede accreditamento fornitore)
- [x] **Prefect Flow** (`daily_scan()`) — cron "0 8 * * *", scraping parallelo + parsing + eligibility
- [x] **Telegram Bot** — notifica su nuovo bando compatibile (score > threshold), inline buttons
- [x] **Alert System** — nuovo bando, urgenza (< 14gg), aggiornamento bando, spider failure
- [x] Amendment detection (rettifiche) — auto-link a parent bando, warning se in lavorazione/pronto
- [x] Config page Streamlit: toggle portali, set score threshold, storico esecuzioni

### v0.4.0 — Sprint 3: Document Generator (2026-03-02)

- [x] **Template Engine** (WeasyPrint + Jinja2):
  - proposta_tecnica.html, dichiarazione_sostitutiva.html (DPR 445/2000), allegato_a.html, cv_impresa.html
  - base.css — stile formale documenti PA italiani
- [x] **DOCX Generator** (python-docx) — output Word per portali PA
- [x] **Claude Content Generator** (DSPy):
  - Genera proposta tecnica da company_profile + skills_matrix
  - SOLO dati verificati, placeholder "⚠️ TO FILL MANUALLY" per importi
  - Audit trail con fonti usate
- [x] **Fact Checker** — verifica ogni claim vs dati aziendali, BLOCCA output se claim non verificato
- [x] **Document Versioning** — v1, v2, v3... (mai sovrascrive)
- [x] **Package Builder:**
  - Crea cartella `output/bandi/{YYYYMMDD}_{slug}/`
  - Include visura camerale, README, checklist_invio, submission_info.json
- [x] Pagina gestione documenti Streamlit: review, approve, version comparison, download ZIP

### v0.5.0 — Sprint 4: Polish & Automation (2026-03-02)

- [x] **Telegram Bot interattivo:**
  - `[📄 Dettagli]` → link diretto Streamlit
  - `[✅ Analizza]` → trigger parsing + eligibility in background
  - `[❌ Ignora]` → scarta
  - `[📂 Genera Documenti]` → avvia generatore
  - Comandi: `/bandi`, `/scadenze`, `/status`, `/help`
- [x] **Alert progressivi scadenze** — 30, 14, 7, 3, 1 giorno (solo idoneo/lavorazione)
- [x] **Streamlit UI polish:**
  - Dashboard: Plotly charts (bar, histogram, Gantt, pie)
  - Kanban view con cambio stato
  - Color coding urgenza (rosso < 7gg, arancione < 14gg, verde > 14gg)
  - Full-text search, CSV export
- [x] **Monitoring** (RunMonitor + JSONL fallback + alert Telegram su failure)
- [x] **Manutenzione automatica:**
  - Backup giornaliero PostgreSQL
  - Auto-archivia bandi scaduti > 30gg
  - Cleanup settimanale (vacuum, purge scartati vecchi)

### v0.6.0 — Sprint 5: Multi-Project + Soggetti (2026-03-03 → 2026-03-19)

- [x] **Architettura multi-progetto:**
  - Migration 005: `projects` + `project_evaluations` (bandi oggettivi, valutazioni per-progetto)
  - Migration 004: tipo_finanziamento + aliquota_fondo_perduto
  - Migration 006: campi estesi bandi (criteri, documenti, confidence)
- [x] **Configurable Scoring Engine:**
  - JSONB rules per progetto (9 handler types)
  - 3 template built-in: ICT/Freelancer, Turismo/Cultura, E-commerce/PMI
  - region_match, ateco_match, keyword matching, importo checks, beneficiary matching
- [x] **Separazione Soggetti / Progetti:**
  - Migration 008: tabella soggetti
  - Migration 009: workspace fields su project_evaluations
  - Migration 010: seed soggetti, 250 evaluations migrate
  - Soggetto → hard stops (anagrafica), Progetto → scoring (keywords, settore)
- [x] **Progetti attivi:**
  - La Monica ICT (ID 1) — 125 bandi migrati, 91+ idonei
  - Paese Delle Stelle (ID 2) — 91 idonei su valutazione retroattiva
- [x] **Django 5.2 + Unfold (tool-bandi-ui/) — PRIMO WEB LAYER:**
  - Auth (luciano@toolbandi.local)
  - CurrentProjectMiddleware + context processor
  - Project switcher dinamico in sidebar
  - Dashboard, Bandi list/detail, Candidature workspace, Progetti detail, Pipeline
  - State machine completa (9 transizioni, 27 test)
  - Workspace 4 tab (Overview, Checklist, Documenti, Note)
  - Gap analysis aggregata, scoring rules editor, completezza 12 check
  - 40+ assertions, QA finale passato
- [x] **Streamlit UI refactoring:**
  - Migrato a st.navigation() API
  - Sidebar unificata con project selector
  - Landing page = Lista Bandi

### v0.6.1 — tool-bandi-ui: Django Web Layer (2026-03-03 → 2026-03-19)

**Stack:** Django 5.2 LTS + Unfold Admin Framework + PostgreSQL (shared DB con engine)
**Repo:** tool-bandi-ui/ (separato, poi ritirato)
**Nota:** Zero ORM — tutto raw SQL con psycopg2. Django usato solo come HTTP + template layer.

#### Infrastruttura
- [x] Django project + venv + requirements.txt
- [x] Auth funzionante (luciano@toolbandi.local)
- [x] Migrazioni 008-010 applicate (soggetti, workspace fields, seed)
- [x] `CurrentProjectMiddleware` — inietta project_id in ogni request via session
- [x] Context processor `current_project` — progetto corrente + lista progetti per template
- [x] Unfold `SITE_DROPDOWN` con project switcher dinamico
- [x] Tabelle DB unmanaged: bandi, project_evaluations, projects, soggetti, pipeline_runs

#### US-011: Lista Bandi
- [x] SQL dinamica con WHERE condizionali + paginazione (25/page)
- [x] 7 filtri: solo_aperti (default ON), nascondi_archiviati, search `q`, stato[], tipo_fp, score_min, scadenza_giorni, portale
- [x] Display metadata: STATO_META (7 stati + badge CSS), TIPO_FP_LABELS (6 tipi), score badge (verde/arancione/rosso)
- [x] Budget formatter (€1.5M, €500K), giorni formatter ("Scaduto", "Oggi!", "7gg")
- [x] Dropdown filtri dinamici (portali, tipi_finanziamento da DISTINCT query)

#### US-012: Filtri + Empty State + Bulk Actions
- [x] Empty state con ultimo bando scaduto
- [x] `archivia_scaduti` — bulk UPDATE stato='archiviato' per bandi scaduti
- [x] `rivaluta` — async Thread chiama `engine.pipeline.flows.rivaluta_singolo()` per PE

#### US-013: Scheda Bando Detail
- [x] 4 tab: Decisione 60s, Dettaglio, Valutazione, Testo/Documenti/Esito (nome tab context-dependent)
- [x] Tab Decisione: pro (score_breakdown matched) vs contro (gap_analysis + yellow_flags)
- [x] 9 action flags stato-dipendenti (can_avvia, can_segna_pronto, can_segna_inviato, can_torna_idoneo, can_torna_lavorazione, can_scartare, can_rivalutare, can_archiviare, can_ripristinare)
- [x] Urgenza: badge rosso se scadenza <= 14gg

#### US-020: Avvia Lavorazione
- [x] Transizione idoneo → lavorazione
- [x] Auto-genera workspace_checklist da gap_analysis (`_build_initial_checklist()`)
- [x] Ogni gap diventa item checklist con id, label, completato=false, nota=suggerimento, tipo=auto

#### US-021: Workspace Candidatura (4 Tab)
- [x] Tab 1 Overview: score, stato, budget, giorni, gap summary
- [x] Tab 2 Requisiti & Checklist: toggle interattivo (AJAX fetch → JSON), add manuale, `workspace_completezza` = done/total * 100
- [x] Tab 3 Documenti: placeholder upload/gestione
- [x] Tab 4 Note & Decisioni: CRUD cronologico con timestamp DD/MM/YYYY HH:MM

#### US-023: State Machine Completa (9 transizioni)
- [x] TRANSITIONS dict: avvia_lavorazione, segna_pronto, segna_inviato (con data_invio + protocollo), torna_idoneo, torna_lavorazione, scarta (con motivo_scarto), archivia, ripristina
- [x] Validazione: STATI_SCARTABILI, STATI_ARCHIVIABILI, STATI_RIPRISTINABILI
- [x] Modal conferma per azioni distruttive

#### US-030: Profilo Progetto (7 sezioni)
- [x] PROFILO_DEFAULT: 16 campi (descrizione_breve/estesa, settore, keywords[], comuni_target[], zone_speciali[], costituita, budget_min/max, cofinanziamento_pct/fonte, partner[], piano_lavoro[], kpi[], punti_di_forza{}, referenze, documenti_supporto[])
- [x] 8 SETTORI, 5 COFINANZIAMENTO_FONTI, 4 ZONE_SPECIALI_OPTIONS
- [x] Form con 7 sezioni: Identita', Descrizione, Economico, Partner, Piano Lavoro, KPI, Punti di Forza
- [x] CSV → list per keywords/comuni, JSON parsing per partner/piano/kpi

#### US-031: Gap Analysis Aggregata
- [x] Query JSONB: jsonb_array_elements(gap_analysis) GROUP BY tipo, suggerimento ORDER BY bandi_impattati DESC LIMIT 20
- [x] Mostra quali gap impattano piu' bandi trasversalmente

#### US-032: Scoring Rules Editor + Ri-valuta
- [x] JSON editor per scoring_rules
- [x] Checkbox "Rivaluta tutti i bandi" → async Thread chiama `rivaluta_progetto(project_id)`
- [x] Validazione JSON, redirect con errore se invalido

#### US-050: Dashboard
- [x] 4 stat card: Idonei da valutare, Scadono in 14gg, In lavorazione, Ultima scansione
- [x] Tabella ScadenzeImminenti (15 righe, idonei/lavorazione entro 30gg, ordinate per scadenza ASC)

#### US-051: Pipeline
- [x] Tabella ultime 20 pipeline_runs (started_at, duration, scraped, inserted, updated, notified, failures, errors)
- [x] Trigger manuale: POST → async daily_scan(), redirect con ?triggered=1

#### US-052: QA Finale
- [x] 12 test end-to-end (login, lista filtri, project switcher, view bando, state transitions, dashboard, profilo, scoring)
- [x] 27/27 assertions passing
- [x] Fixtures: 2 progetti, 3 bandi, 4 evaluations, 1 pipeline_run

#### Completezza Checklist (12 item)
- [x] descrizione_breve (non vuota), settore + >=3 keywords, >=1 comune_target, descrizione_estesa >=500 parole, budget_min, cofinanziamento_pct, >=1 partner, >=1 partner con lettera_intento, >=2 fasi piano_lavoro, >=2 KPI, >=1 documento_supporto, referenze non vuote

---

### v0.7.0-dev — Rebuild FastAPI (2026-03-19)

**Decisione:** Django sostituito con FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CSS.
Motivo: Django ORM non usato (tutto raw SQL), troppo overhead per il caso d'uso.
Engine Python chiamato direttamente dalle route FastAPI (zero serializzazione).

**Consolidamento repo (2026-03-20):**
- tool-bandi-ui/ (Django) ritirato — repo GitHub archiviato come `tool-bandi-ui-archived`
- Repo GitHub `bandiresearcher` rinominato → `tool-bandi` (unico repo attivo)
- Spec, mockup e screenshot copiati in `context/spec/` prima dell'archiviazione
- Un solo repo, un solo processo, un solo linguaggio (Python)

**Commit checkpoint:** `57f0212` — 84 file, 7954 LOC

#### Fase 0: Foundation
- [x] FastAPI skeleton: main.py, Jinja2 config, static mount, lifespan (pool init/close)
- [x] `engine/db/pool.py`: ThreadedConnectionPool singleton
- [x] Layout base template: sidebar, header, HTMX/Alpine config
- [x] Componenti Jinja2 macro: badge, card, stat_card, prog_bar, tabs, empty_state
- [x] HTMX 1.9 + Alpine.js 3.x in static/
- [x] Tailwind CSS CDN
- [x] docker-compose.yml (2 servizi: web + db)
- [x] Session middleware (current_project_id + flash)

#### Fase 1: Core read-only
- [x] Dashboard: 4 stat card + tabella scadenze prossime
- [x] Bandi list: 7 filtri (stato, tipo_fp, score_min, scadenza, portale, search) + paginazione 25/page
- [x] Bando detail: 3 tab HTMX (Decisione, Dettaglio, Testo) + action buttons
- [x] Pipeline: log scansioni + trigger manuale (BackgroundTasks)
- [x] Services: display.py (STATO_META, TIPO_FP_LABELS, enrich_bando_row)

#### Fase 2: Soggetti + Progetti
- [x] Soggetti: list (2 tab reali/simulazioni), detail, create, update, duplicate as simulation
- [x] Progetti: list raggruppata per soggetto, detail con 4 tab HTMX
- [x] Tab Profilo: 7 sezioni form (identita', economici, soggetto, descrizione, partner, KPI, punti forza)
- [x] Tab Analisi: gap analysis aggregata con bandi impattati
- [x] Tab Scoring: JSON editor + rivaluta asincrono (background thread)
- [x] Tab Candidature: stats per stato
- [x] Service completezza.py: 12 check items, normalize_profilo, SETTORI, ZONE_SPECIALI

#### Fase 3: Candidatura + State Machine
- [x] Candidature list: stats per stato + tabella ordinata per scadenza
- [x] Workspace: 4 tab HTMX (overview, checklist, documenti, note)
- [x] State machine: TRANSITIONS dict (idoneo→lavorazione→pronto→inviato + scarta/archivia/ripristina)
- [x] Checklist: HTMX toggle singolo item, add manuale, progress bar
- [x] Note: CRUD cronologico (newest first)
- [x] State transitions: avvia_lavorazione (auto-genera checklist da gap_analysis), segna_pronto, segna_inviato (con data+protocollo), scarta (con motivo)

#### Fase 4: Gestione Documenti
- [x] Migration 012: documento_candidatura + versione_documento
- [x] CRUD documenti: create, detail/editor, save markdown, change stato
- [x] AI generation: background thread con engine.generators.content_generator
- [x] Export: PDF (pdf_generator), DOCX (docx_generator)
- [x] ZIP export: tutti i documenti approvati in memoria
- [x] Versioning: auto-increment, cronologia versioni in sidebar editor
- [x] 9 categorie documento, 5 stati (mancante→bozza→in_revisione→approvato→da_firmare)

---

### v0.7.1-dev — Riallineamento Spec D1-D20 (2026-03-20)

20 divergenze identificate tra implementazione e spec UI/UX. Le Fasi 0-4 avevano portato le Django views 1:1 in FastAPI. Questo sprint allinea tutto alla spec.

#### Commit: 6b03d0e — D1+D2+D6+D9+D16+D17+D18
- [x] D1: Rimosso project switcher globale dalla sidebar e deps.py
- [x] D2: Tab Progetto riordinati: Opportunita'(DEFAULT)→Candidature→Profilo→Analisi
- [x] D2: Scoring Rules integrato come sotto-sezione del tab Profilo
- [x] D2: Creato progetto_tab_opportunita.html (bandi valutati per progetto)
- [x] D6: Dashboard trasversale con 7 stat card (bandi, nuovi, idonei, lavorazione, scadenze, progetti, soggetti)
- [x] D9: Sidebar scura bg-slate-900 con testo bianco (spec mockup)
- [x] D16: Stat card cross-project (non filtrate per progetto)
- [x] D17: Stat card con gradient (bg-gradient-to-br)
- [x] D18: Font DM Sans via Google Fonts + tailwind config

#### Commit: edb230f — D3+D4+D5
- [x] D3: Dropdown "Valuta per:" in bandi list (query param project_id)
- [x] D4: Dropdown "Valuta per:" in bando detail header
- [x] D5: Tab Decisione e action buttons condizionali (solo con progetto)

#### Commit: 2667abf — D8+D12+D13
- [x] D8: Lista candidature trasversale (tutti i progetti), filtri stato/progetto
- [x] D12: Workspace tab order: Valutazione→Documenti→Checklist→Note&Invio
- [x] D13: Colonne Progetto/Soggetto nella lista candidature

#### Commit: d41bfee — D7
- [x] D7: Soggetti 3 tab (Anagrafica, Vincoli & Vantaggi, Progetti)
- [x] D7: CRUD vincoli e vantaggi via form POST (profilo JSONB)

#### Commit: 388f8a3 — D11+D20
- [x] D11: Action buttons puntano a /candidature/{pe_id}/stato (fix URL)
- [x] D20: Tab Analisi arricchito con stats rapide, completezza, soggetto

#### Debito tecnico
- [x] D10: **Documentato**, non implementato. State machine usa project_evaluations con vecchi stati (idoneo→lavorazione→pronto→inviato). Spec prevede tabella candidatura separata con nuovi stati (bozza→lavorazione→sospesa→pronta→inviata→abbandonata). Piano migrazione documentato in state_machine.py. Migration 011 creata ma non deployata.

---

### Consolidamento repo (2026-03-20)

- Repo GitHub `bandiresearcher` rinominato → `tool-bandi`
- Repo GitHub `tool-bandi` (Django) rinominato → `tool-bandi-ui-archived` e archiviato
- Spec, mockup, screenshot copiati in `context/spec/` prima dell'archiviazione
- Cartella locale `tool-bandi-ui/` spostata in `_archivio/`
- `requirements.txt` pinnato con 17 dipendenze dirette
- venv consolidato (venv_new promosso, shebangs fixati, pango installato)

### Primo avvio locale (2026-03-20)

- Commit `f0b0fbd`: 2 fix, 26/26 route rispondono 200
- Fix 1: `dashboard.py` — `soggetti.tipo` → `profilo->>'tipo'` (migration 013 non deployata)
- Fix 2: `documenti.py` — `_table_exists()` guard per `documento_candidatura` (migration 012 non deployata, fallback a lista vuota)
- Avvio: `venv/bin/uvicorn web.main:app --reload --port 8000`

---

### v0.7.2-dev — Bug fix UI + Test suite (2026-03-20)

- [x] 6 bug fix UI: sidebar doppia, bandi list rotto, raw HTML nel tab testo, JSON non formattato, hx-boost su link JS, soggetti tipo non propagato
- [x] Test suite automatica: 29 smoke test (httpx) + 10 browser test (Playwright)
- [x] Custom Jinja2 filter `clean_html` per strip HTML/script/style
- [x] `| tojson(indent=2)` per JSON leggibile nei textarea
- [x] `hx-boost="false"` su link con href modificato da JS
- [x] BUGS.md tracker (6 bug risolti)

### v0.8.0-dev — Espansione forma giuridica, regimi, qualifiche (2026-03-20)

- [x] Costanti centralizzate in `completezza.py`:
  - FORME_GIURIDICHE: 16 forme (da 10) — aggiunto libero_professionista, srls, spa, sapa, cooperativa_sociale, aps, odv, rete_impresa
  - REGIMI_FISCALI: 5 regimi (da 3) — aggiunto agricolo, non_profit
  - QUALIFICHE_SOGGETTO: 6 qualifiche (NUOVO) — startup_innovativa, pmi_innovativa, impresa_sociale, societa_benefit, impresa_femminile, impresa_giovanile
  - COFINANZIAMENTO_FONTI: 8 fonti (da 5) — ristrutturato con fonti reali
  - ZONE_SPECIALI_OPTIONS: 6 zone (da 4) — aggiunto ZES Unica, ZLS, isola_minore, cratere_sismico
- [x] Engine `_FORMA_GIURIDICA_MAP` espanso (25+ entry con legacy aliases) in `rules.py`
- [x] Template soggetto (create + edit): dropdown da costanti centralizzate, checkbox qualifiche
- [x] Route soggetti: async per leggere qualifiche multi-valore, salvate in profilo JSONB
- [x] 29/29 smoke test verdi post-modifica

### v0.8.1-dev — Bug Fix UI (Sezione A) (2026-03-20)

4 bug UI fixati. 29/29 smoke test verdi dopo ogni fix. Un commit per bug.

- [x] **BUG-UI-001:** Salva Profilo rompe tab — `hx-boost="false"` su form + check `HX-Target` server-side (`14357c8`)
- [x] **BUG-UI-002:** JSON raw in profilo — Alpine.js dynamic forms per partner/piano_lavoro/kpi/documenti_supporto (`57030c8`)
- [x] **BUG-UI-003:** Pipeline crash — try/except su query `pipeline_runs` + messaggi errore in UI (`ba20c7f`)
- [x] **BUG-UI-004:** Profilo perde dati — aggiunto tipo_investimento, fix costituita default, zone_speciali multi-checkbox (`d7e7fe6`)

### v0.8.1-dev — Bug Fix Logic (Sezione B) (2026-03-20)

4 bug logici fixati. 29/29 smoke test verdi dopo ogni fix. Un commit per bug.

- [x] **BUG-LOGIC-001:** Soggetto save non rivaluta — background thread `rivaluta_progetto()` per ogni progetto del soggetto (`85db886`)
- [x] **BUG-LOGIC-002:** Qualifiche decorative — `qualifica_match` rule aggiunta ai 3 scoring template (`361fe2d`)
- [x] **BUG-LOGIC-003:** Profilo save non rivaluta — background thread `rivaluta_progetto()` dopo save profilo (`fbe8012`)
- [x] **BUG-LOGIC-004:** Tab Opportunita' senza CTA — empty state con icona, testo e link "Avvia scansione" (`b05bc52`)

### v0.8.1-dev — Test funzionali Playwright (2026-03-20)

- [x] 20 test Playwright end-to-end in `tests/test_functional.py`
- [x] Copertura: navigazione (3), progetti (6), bandi (2), soggetti (3), candidature (1), pipeline (2), integrita' globale (3)
- [x] Report console + BUGS.md append automatico + screenshot

### v0.8.3-dev — Deploy & Stabilizzazione (2026-03-20)

#### Task 1: Test e2e reattivita' dati — VERIFICATO
- [x] Soggetto save → rivaluta_progetto() in background thread (soggetti.py:318-348)
- [x] Profilo save → rivaluta_progetto() in background thread (progetti.py:459-467)
- [x] Scoring save → rivaluta_progetto() in background thread (progetti.py:500-504)
- [x] qualifica_match handler registrato in configurable_scorer.py e presente in 3 template scoring
- [x] 29/29 smoke test verdi

### v0.8.2-dev — Fix generico sidebar doppia (2026-03-20)

- [x] **BUG-FIXED-015:** Middleware `HTMXLayoutMiddleware` — rileva e stripa layout da risposte HTMX partial
- [x] `hx-boost="false"` su 6 form in partials (scoring, vincoli, note, checklist, documenti)
- [x] Audit completo: 37 partial verificati, 0 estendono layout, 0 hx-get a pagine complete
- [x] Test regressione: 10 pagine verificate, 0 sidebar doppie

---

## Sicurezza

- DB porta `127.0.0.1:5432` (mai 0.0.0.0)
- `env_file: .env`, permessi 600, mai committato
- `.env.example` con placeholder
- Network internal per DB
- Container non-root (USER nobody)
- Requirements pinned
- Fact checker BLOCCA documenti con claim non verificati
- Riferimento: `/Users/lucianolamonica/CodiceCodice/SECURITY.md`
