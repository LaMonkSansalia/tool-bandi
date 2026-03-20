# COMMS.md — PM ↔ Agent Communication Log

> **MANDATORY READ:** Read this file at the start of every work session and before starting any task.

---

## Roles

| Agent | Role | Tool |
|-------|------|------|
| **Gandalf** | PM — monitors progress, resolves blockers, communicates with Luciano | Claude Code |
| **Mimmo** | Implementer (retired for now — qwen3:14b too slow with Claude Code interface) | OpenCode |

---

## Current Status — 2026-03-20 (v0.8.3-dev)

**Phase:** v0.8.3-dev — Deploy & stabilizzazione
**Stato:** 15 bug risolti totali, 0 aperti. 29/29 smoke test.

[COMPLETATO] 2026-03-20 — Task 3: Preparazione deploy:
  - deploy.sh creato (idempotente: pull, build, migrate 001-010, start, smoke test)
  - web/auth.py: SimpleAuthMiddleware — cookie-session, disabilitato in dev (env vuote)
  - Decisione: auth disabilitata in dev (AUTH_USER/AUTH_PASS vuoti), attiva solo in staging/prod
  - 29/29 smoke test verdi
  - Prossimi passi: Task 4 (deploy su staging — sostituzione container Django)

[COMPLETATO] 2026-03-20 — Task 2: Prerequisiti deploy:
  - Dockerfile fixato: usa requirements.txt consolidato (non split)
  - docker-compose.yml: env_file .env, migrations volume mount aggiunto
  - .env.example creato a root con tutte le variabili
  - Nota: tool-bandi-ui (Django) era gia' deployato su parco-giuochi — infrastruttura (npm_default, SSL, proxy NPM) gia' configurata
  - Prossimi passi: Task 3 (deploy.sh, auth, aggiornamento container)

[COMPLETATO] 2026-03-20 — Task 1: Test e2e reattivita' dati:
  - Verificato: soggetto save → rivaluta_progetto() in background thread (soggetti.py:318-348)
  - Verificato: profilo save → rivaluta_progetto() in background thread (progetti.py:459-467)
  - Verificato: scoring save → rivaluta_progetto() in background thread (progetti.py:500-504)
  - Verificato: qualifica_match handler registrato in configurable_scorer.py:126-159
  - Verificato: qualifica_match rule presente in tutti e 3 i template scoring (ICT, Turismo, E-commerce)
  - 29/29 smoke test verdi
  - Prossimi passi: Task 2 (prerequisiti deploy)

[COMPLETATO] 2026-03-20 — Fix generico sidebar doppia:
  - Decisione: middleware `HTMXLayoutMiddleware` come fix generico — rileva e stripa layout da risposte partial
  - Decisione: `hx-boost="false"` su TUTTI i form nei partial tab (6 form fixati)
  - Decisione: NON usare Jinja2 template guard (block duplicato non permesso) — middleware e' piu' robusto
  - Prossimi passi: deploy staging, test manuale end-to-end, D10 (migrazione state machine)

[COMPLETATO] 2026-03-20 — Bug Fix Completo:
  - Sezione A (UI): 4/4 fixati (BUG-UI-001→004, commit 14357c8→d7e7fe6)
  - Sezione B (Logic): 4/4 fixati (BUG-LOGIC-001→004, commit 85db886→b05bc52)
  - Sezione C (Test Playwright): 20 test creati in tests/test_functional.py
  - Decisione: hx-boost="false" su form e' pattern standard per evitare conflitti redirect 303
  - Decisione: Alpine.js x-data/x-for per campi array dinamici (partner, piano_lavoro, kpi)
  - Decisione: rivaluta_progetto() in background thread dopo save soggetto E profilo
  - Decisione: CLAUDE.md aggiornato con comandi utente (/salva, /stato, /test, /prossimo)

## Current Status — 2026-03-19 (precedente)

**Phase:** tool-bandi-ui — COMPLETATO (Sprint 0-3 + 5 + QA)
**Stato:** Sistema operativo. Sprint 4 (generazione documenti) deferred.

[DONE Sprint 5 QA] 2026-03-19 — QA Finale US-052:
  - 27/27 test passati (12 check end-to-end)
  - Fix: parsing difensivo JSONB in workspace + bando_detail views (_as_list helper)
  - Fix: template `{% firstof gap.tipo gap.categoria gap %}` sostituisce `default:gap.categoria` per evitare VariableDoesNotExist come argomento di filter
  - Test: tests_qa.py copre Check01-Check12 (login, filtri, project switcher, state machine, urgente, pipeline, dashboard, gap analysis, scoring)

[DONE Sprint 5 UI] 2026-03-19 — Dashboard + Pipeline:
  - US-050: Dashboard — 4 stat cards (Idonei, Scadono 14gg, In lavorazione, Ultima scansione) + tabella ScadenzeImminenti (idonei/lavorazione <30gg) con display metadata
  - US-051: Pipeline page — tabella last 20 pipeline_runs + trigger manuale (POST /pipeline/trigger/) + background thread
  - Template: templates/core/dashboard.html, templates/pipeline/pipeline.html

[DONE Sprint 3 UI] 2026-03-19 — ProgettoDetail /progetti/<pk>/ completo:
  - US-030: 7 sezioni (Identità, Descrizione, Economico, Partner, Piano lavoro, KPI, Punti di forza) + checklist completezza 12 item
  - US-031: Gap Analysis Aggregata — query JSONB su project_evaluations, top 20 gap raggruppati per tipo
  - US-032: Editor Scoring Rules JSONB + checkbox "Ri-valuta tutti" con background thread
  - Test: 7/7 assertions passate

[DONE Sprint 2 UI] 2026-03-19 — Candidature complete:
  - US-020: Avvia Lavorazione — modale conferma + state_action endpoint + init workspace_checklist da gap_analysis
  - US-021: Workspace /candidature/<pe_id>/ — 4 tab (Overview, Checklist, Documenti placeholder, Note), progress bar, checklist toggle via fetch API
  - US-023: State machine completa — tutte le transizioni: avvia_lavorazione, segna_pronto, segna_inviato (modale), torna_idoneo, torna_lavorazione, scarta (modale + motivo), archivia, ripristina
  - Test: 9/9 state machine assertions passate

[DONE Sprint 1 UI] 2026-03-19 — Lista Bandi completa: /bandi/ + /bandi/<pk>/ + filtri + empty state + bulk actions. 8/8 test 200.

[DONE Sprint 0 UI] 2026-03-19 — Django 5.2 LTS + Unfold setup completo:
  - DB migrations 008 (soggetti), 009 (workspace fields + project_decisions) applicate
  - Migration 010: 1 soggetto seedato (lamonica_piva), 250 evaluations migrated
  - tool-bandi-ui/ Django project creato, venv, requirements.txt, settings.py, urls.py
  - Auth funzionante (luciano@toolbandi.local), DB connection verified (125 bandi)
  - CurrentProjectMiddleware + context processor current_project
  - Unfold SITE_DROPDOWN dinamico (project switcher callable)
  - URL patterns placeholder: /, /bandi/, /bandi/<pk>/, /candidature/<pk>/, /progetti/<pk>/, /pipeline/
  - flows.py: rivaluta_singolo + rivaluta_progetto + CLI --rivaluta / --scan
  - package_builder.py: build_package_for_pe(pe_id) wrapper
  - rules.py + manager.py: get_profile_for_soggetto / get_soggetto_profile

---

## Current Status — 2026-03-03 (aggiornato fine giornata)

**Phase:** Sprint 0-6 **COMPLETE** | Sprint 6 UX refactoring DONE
**Overall:** ~99% (~67 source files, 7 DB tables, 2 projects attivi)
**Next:** End-to-end test (scrape → score → Telegram), visual QA Streamlit UI

---

## Task Progress Log

### Track A (Infrastructure) ✅
- [x] A1 — engine/docker-compose.yml — DONE 2026-03-02 — Gandalf
- [x] A2 — engine/db/migrations/001_init.sql — DONE 2026-03-02 — Gandalf
- [x] A2 — engine/db/migrations/002_pgvector.sql — DONE 2026-03-02 — Gandalf
- [x] A3 — engine/requirements.txt — DONE 2026-03-02 — Gandalf
- [x] A3 — engine/config.py — DONE 2026-03-02 — Gandalf
- [x] A3 — engine/.env.example — DONE 2026-03-02 — Gandalf
- [x] EXTRA — setup.sh — DONE 2026-03-02 — Gandalf

### Track B (Core Logic) ✅
- [x] B1 — engine/scrapers/spiders/invitalia.py — DONE 2026-03-02 — Gandalf
- [x] B1 — engine/scrapers/settings.py + middlewares.py — DONE 2026-03-02 — Gandalf
- [x] B2 — engine/parsers/docling_extractor.py — DONE 2026-03-02 — Gandalf
- [x] B2 — engine/parsers/claude_structurer.py — DONE 2026-03-02 — Gandalf
- [x] B2 — engine/parsers/schema.py — DONE 2026-03-02 — Gandalf
- [x] B3 — engine/eligibility/rules.py — DONE 2026-03-02 — Gandalf
- [x] B3 — engine/eligibility/hard_stops.py — DONE 2026-03-02 — Gandalf
- [x] B3 — engine/eligibility/scorer.py — DONE 2026-03-02 — Gandalf
- [x] B3 — engine/eligibility/gap_analyzer.py — DONE 2026-03-02 — Gandalf

### Track C (Integration) ✅
- [x] C1 — engine/db/load_profile.py — DONE 2026-03-02 — Gandalf
- [x] C2 — engine/scrapers/deduplicator.py — DONE 2026-03-02 — Gandalf
- [x] C2 — engine/scrapers/pipelines.py — DONE 2026-03-02 — Gandalf
- [x] C3 — engine/ui/app.py — DONE 2026-03-02 — Gandalf
- [x] C3 — engine/ui/pages/01_dashboard.py — DONE 2026-03-02 — Gandalf
- [x] C3 — engine/ui/pages/02_bandi.py — DONE 2026-03-02 — Gandalf
- [x] C3 — engine/ui/pages/03_dettaglio.py — DONE 2026-03-02 — Gandalf
- [x] C3 — engine/ui/pages/05_profilo.py — DONE 2026-03-02 — Gandalf

### Sprint 2 — Scrapers & Scheduling ✅
- [x] regione_sicilia.py spider — DONE 2026-03-02 — Gandalf
- [x] mimit.py spider — DONE 2026-03-02 — Gandalf
- [x] padigitale.py spider — DONE 2026-03-02 — Gandalf
- [x] inpa.py spider — DONE 2026-03-02 — Gandalf
- [x] comune_palermo.py spider — DONE 2026-03-02 — Gandalf
- [x] euroinfosicilia.py spider — DONE 2026-03-02 — Gandalf
- [x] engine/pipeline/flows.py (Prefect) — DONE 2026-03-02 — Gandalf
- [x] engine/notifications/telegram_bot.py — DONE 2026-03-02 — Gandalf
- [x] engine/notifications/alerts.py — DONE 2026-03-02 — Gandalf
- [x] engine/ui/pages/06_config.py — DONE 2026-03-02 — Gandalf

### Sprint 3 — Document Generator ✅
- [x] engine/generators/templates/html/base.css — DONE 2026-03-02 — Gandalf
- [x] engine/generators/templates/html/proposta_tecnica.html — DONE 2026-03-02 — Gandalf
- [x] engine/generators/templates/html/dichiarazione_sostitutiva.html — DONE 2026-03-02 — Gandalf
- [x] engine/generators/templates/html/cv_impresa.html — DONE 2026-03-02 — Gandalf
- [x] engine/generators/templates/html/allegato_a.html — DONE 2026-03-02 — Gandalf
- [x] engine/generators/pdf_generator.py — DONE 2026-03-02 — Gandalf
- [x] engine/generators/docx_generator.py — DONE 2026-03-02 — Gandalf
- [x] engine/generators/content_generator.py — DONE 2026-03-02 — Gandalf
- [x] engine/generators/fact_checker.py — DONE 2026-03-02 — Gandalf
- [x] engine/generators/package_builder.py — DONE 2026-03-02 — Gandalf
- [x] engine/ui/pages/04_documenti.py — DONE 2026-03-02 — Gandalf

### Sprint 4 — Polish ✅
- [x] engine/ui/pages/01_dashboard.py — Plotly charts (bar, histogram, Gantt, pie) — DONE 2026-03-02
- [x] engine/ui/pages/02_bandi.py — search, CSV export, urgency badge, portale selectbox — DONE 2026-03-02
- [x] engine/notifications/telegram_bot.py — /scadenze, /status, /help, Genera Docs btn — DONE 2026-03-02
- [x] engine/notifications/alerts.py — progressive deadline alerts (30/14/7/3/1d) — DONE 2026-03-02
- [x] engine/pipeline/monitor.py — RunMonitor context manager, DB + JSONL fallback — DONE 2026-03-02
- [x] engine/ui/pages/07_log.py — log viewer, spider health, trend charts — DONE 2026-03-02
- [x] engine/db/backup.py — pg_dump, 30-day daily / 90-day weekly retention — DONE 2026-03-02
- [x] engine/db/cleanup.py — archive expired, purge old scartati, vacuum — DONE 2026-03-02
- [x] engine/pipeline/flows.py — integrated RunMonitor + progressive alerts + cleanup (Sundays) — DONE 2026-03-02

### Sprint 5 — Multi-Project Architecture (2026-03-03)
- [x] Fase 1: DB migration 005_multi_project.sql — projects + project_evaluations tables — DONE
- [x] Fase 1: Seed script 005_seed_projects.py — migrated 125 bandi to project #1 (lamonica) — DONE
- [x] Fase 2: engine/projects/manager.py — CRUD + evaluation upsert — DONE
- [x] Fase 2: engine/eligibility/configurable_scorer.py — data-driven scoring engine — DONE
- [x] Fase 2: engine/eligibility/rules.py — multi-project profile cache, generalized CompanyProfile — DONE
- [x] Fase 2: engine/eligibility/hard_stops.py — generalized forma_giuridica + regione — DONE
- [x] Fase 2: engine/eligibility/gap_analyzer.py — generalized references — DONE
- [x] Fase 4: engine/ui/app.py — project selector in sidebar — DONE
- [x] Fase 4: engine/ui/pages/01_dashboard.py — JOIN project_evaluations — DONE
- [x] Fase 4: engine/ui/pages/02_bandi.py — JOIN project_evaluations — DONE
- [x] Fase 4: engine/ui/pages/03_dettaglio.py — project-specific evaluation — DONE
- [x] Fase 4: engine/ui/pages/05_profilo.py — load from DB — DONE
- [x] Fase 4: engine/ui/pages/08_progetti.py — onboarding wizard + scoring templates — DONE
- [x] Fase 3: engine/notifications/alerts.py — project context (chat_id, prefix) — DONE
- [x] Fase 3: engine/pipeline/flows.py — multi-project evaluation loop — DONE
- [x] Fase 5: Onboarding PDS come progetto #2 — DONE (P.IVA La Monica, sede Roccapalumba, scoring Turismo/Cultura)
- [x] Fase 5: Valutazione retroattiva 125 bandi per PDS — DONE (91 idonei, 34 scartati)
- [x] Context files aggiornati (system_architecture, AGENT_INSTRUCTIONS, bandi_target) — DONE

### Sprint 5 — UI Enhancements / Financing (2026-03-03 — Gandalf)
- [x] engine/db/migrations/004_finanziamento.sql — `tipo_finanziamento` + `aliquota_fondo_perduto` — DONE
- [x] engine/scrapers/spiders/invitalia.py — `_extract_finanziamento()` regex (Italian keywords) — DONE
- [x] engine/scrapers/pipelines.py — INSERT include new financing fields — DONE
- [x] engine/ui/pages/02_bandi.py — `💰 Importo` + `Finanziamento` badge columns — DONE
- [x] engine/ui/pages/03_dettaglio.py — "🧭 Sintesi" section + financing in scheda rapida — DONE
- [x] engine/ui/pages/03_dettaglio.py — "🔄 Aggiorna scheda" expander (requests + regex + DB update) — DONE

### Migration 006 — Extended bandi fields (2026-03-03)
- [x] engine/db/migrations/006_bandi_extended.sql — criteri_valutazione, documenti_da_allegare, parsing_confidence, parsing_notes + GIN indexes — DONE

### Sprint 6 — UX Refactoring (2026-03-03 — Gandalf)
- [x] engine/ui/app.py — refactored to `st.navigation()` API, eliminates duplicate sidebar nav — DONE
- [x] engine/ui/components/sidebar.py — NEW: `render_sidebar()` con project selector + stats + scan button — DONE
- [x] engine/ui/components/__init__.py — NEW: empty init for package — DONE
- [x] pages/01_dashboard.py — rimosso `st.set_page_config` + `render_project_selector`, usa session_state — DONE
- [x] pages/02_bandi.py — rimosso `st.set_page_config` + `render_project_selector`, usa session_state — DONE
- [x] pages/03_dettaglio.py — rimosso `st.set_page_config` + `render_project_selector`, usa session_state — DONE
- [x] pages/04_documenti.py — rimosso `st.set_page_config` + `render_project_selector`, bug fix project filter — DONE
- [x] pages/05_profilo.py — rimosso `st.set_page_config` + `render_project_selector`, usa session_state — DONE
- [x] pages/06_config.py — rimosso `st.set_page_config`, rimosso scan button duplicato — DONE
- [x] pages/07_log.py — rimosso `st.set_page_config` — DONE
- [x] pages/08_progetti.py — rimosso `st.set_page_config` — DONE

**Total files: ~67 source | Overall: ~99% complete**

---

## Blockers
*(none)*

## Questions for Gandalf
*(none)*

---

## Decisions Log

### 2026-03-03 (Sprint 6 UX refactoring — Gandalf)
- UX ripensata su feedback utente: nav duplicata, project selector invisibile, scan button nascosto
- Migrato a `st.navigation()` API (Streamlit 1.54.0) — elimina nav auto-generata da `pages/`
- Landing page = Lista Bandi (bandi-first, non dashboard)
- Sidebar unificata: titolo → project selector + stats → scan button → nav gruppi (Bandi, Panoramica, Impostazioni)
- `render_sidebar()` chiamata solo da app.py, appare su tutte le pagine
- Rimosso `st.set_page_config()` da tutte le 8 pagine (centralizzato in app.py)
- Rimosso `render_project_selector()` — pid da `st.session_state.get("current_project_id", 1)`
- Bug fix `04_documenti.py`: aggiunto filtro project_id (prima mostrava documenti globali)
- Scan button spostato da config page a sidebar (primary, full width, visibile ovunque)
- Approccio: refactoring chirurgico, zero pagine riscritte

### 2026-03-03 (sessione UI financing — Gandalf)
- Migration 004: `tipo_finanziamento` + `aliquota_fondo_perduto` aggiunti a tabella bandi
- invitalia spider: `_extract_finanziamento()` con regex italiani (fondo perduto, prestito, voucher, mix, conto capitale)
- UI lista bandi: colonne `💰 Importo` + `Finanziamento` badge colorati
- UI dettaglio: sezione "🧭 Sintesi — Partecipo o no?" rule-based (no API); scheda rapida con tipo finanziamento
- UI dettaglio: expander "🔄 Aggiorna scheda" — ri-scarica URL con requests, aggiorna DB COALESCE (non sovrascrive dati validi)
- MEMORY.md aggiornato con stato corrente

### 2026-03-03 (Sprint 5 multi-project — agente parallelo)
- Multi-project architecture implemented: bandi are objective, evaluations are per-project
- Configurable scorer: JSONB rules per project, 9 handler types
- 3 scoring templates built-in: ICT/Freelancer, Turismo/Cultura, E-commerce/PMI
- flows.py: parse_and_score simplified to parsing-only; evaluate_for_all_projects does per-project scoring
- save_to_db: writes stato='nuovo' (objective), per-project stato in project_evaluations
- bandi.score and bandi.stato columns deprecated (kept for backward compat)
- Progressive alerts now iterate over all active projects
- Notifications include project prefix + project-specific chat_id
- PDS onboarded as project #2: stessa P.IVA La Monica, sede Roccapalumba, scoring Turismo/Cultura
- Valutazione retroattiva PDS: 91 idonei su 125 (top: 65/100 turismo esperienziale FESR)
- Context files aggiornati: system_architecture v0.4.0, AGENT_INSTRUCTIONS v2.0.0, bandi_target v2.0.0

### 2026-03-02
- Mimmo (qwen3:14b + Claude Code) retired — too slow, can't use Write tool reliably
- All Sprint 0+1 work done by Gandalf
- Ollama may still be useful for bulk spider generation (7 similar files) in future
- Sprint 2 complete: 6 spiders + Prefect flow + Telegram bot + alerts + config UI
- Luciano asked: how will the tool work once done? (see COMMS.md notes on usage workflow)
- Sprint 3 complete: document generator (DSPy+Claude, WeasyPrint PDF, python-docx, fact_checker)
- Sprint 4 complete: Plotly charts, progressive alerts, monitoring, backup/cleanup all wired up
- Weekly cleanup runs automatically every Sunday inside daily_scan()
- Bug fixed: `score_compatibilita` → `score` in dashboard and bandi pages
