# Tool Bandi — CLAUDE.md

**Versione:** 0.8.0-dev
**Repo:** github.com/LaMonkSansalia/tool-bandi
**Stack:** FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CSS — single-process Python, zero build frontend
**Avvio:** `venv/bin/python -m uvicorn web.main:app --reload --port 8000`
**Test:** `venv/bin/python -m pytest tests/test_smoke.py -v`
**Sicurezza:** leggere SEMPRE `/Users/lucianolamonica/CodiceCodice/SECURITY.md` prima di operare

---

## Gerarchia Autorita'

Quando documenti divergono, vale l'ordine:

1. **`context/spec/tool-bandi-spec (1).md`** — Spec UI/UX (autorita' suprema)
2. **`context/spec/tool-bandi-mockup.jsx`** — Design reference (classi Tailwind, layout)
3. **`context/system_architecture.md`** — Architettura tecnica, schema DB, invarianti
4. **`context/project_workspace.md`** — Specifiche profilo progetto + workspace candidatura
5. **`STATUS.md`** — Changelog e stato corrente

---

## Struttura File

```
tool-bandi/
  engine/                    # INVARIATO — Python engine (eligibility, generators, scrapers, pipeline)
    eligibility/             # hard_stops.py (13 regole), configurable_scorer.py (10 handler), rules.py, gap_analyzer.py
    generators/              # content_generator, pdf_generator, docx_generator, package_builder
    parsers/                 # docling_extractor, claude_structurer, schema
    scrapers/                # 7 spider (invitalia, regione_sicilia, mimit, padigitale, inpa, comune_palermo, euroinfosicilia)
    pipeline/                # flows.py (daily_scan, rivaluta_singolo, rivaluta_progetto)
    notifications/           # Telegram alerts
    projects/manager.py      # CRUD soggetti/progetti/candidature (psycopg2)
    db/migrations/001-014    # SQL migrations (011-014 non deployate)
    db/pool.py               # ThreadedConnectionPool singleton

  web/                       # FastAPI + Jinja2 + HTMX
    main.py                  # App, Jinja2 config, static mount, lifespan
    deps.py                  # Depends: get_db, get_nav_context
    routes/                  # dashboard, soggetti, progetti, bandi, candidature, pipeline, documenti
    services/                # completezza.py (costanti + check), display.py, state_machine.py, queries.py
    templates/
      layout.html            # Base: sidebar scura, nav, HTMX/Alpine
      pages/                 # Full pages (dashboard, liste, detail, form)
      partials/              # Frammenti HTMX (tab content, table rows, modali)
    static/                  # htmx.min.js, alpine.min.js, output.css

  context/                   # Documentazione di riferimento (vedi sotto)
  tests/                     # pytest (smoke) + playwright (browser)
```

---

## Costanti Centralizzate

Tutte in `web/services/completezza.py`:

| Costante | Elementi | Usata in |
|----------|----------|----------|
| FORME_GIURIDICHE | 16 | soggetti (create + edit) |
| REGIMI_FISCALI | 5 | soggetti |
| QUALIFICHE_SOGGETTO | 6 | soggetti (checkbox) |
| SETTORI | 11 | progetti (profilo) |
| TIPI_INVESTIMENTO | 8 | progetti (profilo) |
| COFINANZIAMENTO_FONTI | 8 | progetti (profilo) |
| ZONE_SPECIALI_OPTIONS | 6 | progetti (profilo) |
| COMPLETEZZA_CHECKS | 16 (3 livelli) | progetti (sidebar + analisi) |

Categorie documenti in `web/routes/documenti.py`: CATEGORIE (17), STATI_DOCUMENTO (5).

---

## DB

PostgreSQL 16 + pgvector. Tabelle principali:

- `bandi` — bandi scraped + parsed
- `soggetti` — entita' proponenti (profilo JSONB con ammissibilita')
- `projects` — progetti (profilo JSONB con completezza)
- `project_evaluations` — valutazioni bando×progetto (score, hard_stops, gap_analysis)
- `documento_candidatura` + `versione_documento` — documenti con versioning (migration 012, non deployata)
- `candidatura` — tabella separata (migration 011, non deployata)

Schema completo: `context/system_architecture.md` sezione Database.

---

## Invarianti (MAI violare)

1. **Mai inviare nulla autonomamente.** Ogni documento passa per approvazione umana.
2. **Mai generare claim non verificate.** fact_checker.py blocca contenuti non verificati.
3. **Mai resettare stato bando a 'nuovo'** durante daily scan.
4. **Mai ri-eseguire eligibility** su bando in lavorazione/pronto/inviato.
5. **Mai committare `.env`**, `context/documents/`, `output/`.
6. **Sempre creare nuove versioni** documenti (v1, v2...) — mai sovrascrivere approvati.

---

## Convenzioni Naming

- **Codice e file** → English (`hard_stops.py`, `find_existing()`)
- **UI labels e field names** → Italian (`"Bandi disponibili"`, `"proposta_tecnica"`)
- **Documenti generati** → Interamente in italiano (documenti PA)
- **DB domain fields** → Italian (`titolo`, `ente_erogatore`, `data_scadenza`)
- **DB technical fields** → English (`created_at`, `dedup_hash`)

---

## File di Contesto

| File | Contenuto | Stato |
|------|-----------|-------|
| `STATUS.md` | Changelog completo v0.1→v0.8, ogni commit | Aggiornato |
| `COMMS.md` | Log comunicazioni PM↔Agent, decisioni | Aggiornato |
| `BUGS.md` | Bug tracker (6 risolti, 0 aperti) | Aggiornato |
| `context/system_architecture.md` | Architettura, schema DB, state machine, scoring | Autorita' tecnica |
| `context/project_workspace.md` | Spec profilo progetto + workspace candidatura | Autorita' UX |
| `context/spec/tool-bandi-spec (1).md` | Spec UI/UX completa (5 entita', stati, flussi) | Autorita' suprema |
| `context/spec/considerazioni-zone-cofin-forme.md` | Analisi zone speciali, cofinanziamento, forme | Riferimento |
| `context/_archivio/` | File superati (ui_requirements STORICO, AGENT_INSTRUCTIONS v2, COSTS) | Non leggere |

---

## Debito Tecnico

- **D10:** State machine su `project_evaluations` con vecchi stati. Migration 011 (candidatura) non deployata.
- **Migrations 012-014:** Non deployate (documenti, estensioni soggetti, hard_stops JSONB).
- **Auth:** Assente (singolo utente locale). Da implementare per staging.
- **Tailwind:** CDN in dev, standalone CLI per prod (non configurato).
