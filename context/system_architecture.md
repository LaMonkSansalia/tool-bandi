# System Architecture — Bandi Researcher

**Version:** 0.4.0 — Multi-Project Architecture
**Date:** 2026-03-03
**Scope:** Multi-project (La Monica Luciano + Paese Delle Stelle + future projects)
**Deployment:** Local (Docker Compose)

---

## Guiding Principles

1. **Human-in-the-loop is mandatory.** The system handles 90% of the cognitive work. The human reviews, decides, authorizes. No declaration is ever submitted autonomously. Ever.
2. **Bandi are objective, evaluations are subjective.** Bandi exist independently of who evaluates them. Each project has its own profile, scoring rules, and evaluation states.

---

## Active Projects

| ID | Slug | Nome | Scoring Template | Sede |
|----|------|------|-----------------|------|
| 1 | `lamonica` | La Monica Luciano | ICT / Freelancer | Palermo |
| 2 | `pds` | Paese Delle Stelle | Turismo / Cultura | Roccapalumba |

---

## Tech Stack

```
ENGINE (Python 3.14)
  Scraping:        Scrapy + scrapy-playwright
  Document AI:     Docling (IBM, open source)
  LLM:             Claude API — claude-sonnet-4-6
  LLM Orch:        DSPy  (structured, deterministic prompting)
  Pipeline:        Prefect  (scheduling, retry, logging, built-in UI)
  Notifications:   python-telegram-bot
  Doc Output:      WeasyPrint + Jinja2 (PDF)  +  python-docx (DOCX)

UI/ADMIN
  Streamlit        (speed over beauty — internal tool)

INFRASTRUCTURE
  Database:        PostgreSQL 16 + pgvector
  Cache/Queue:     Redis 7
  Container:       Docker Compose
  Deployment:      Local → VPS (future)
```

---

## Multi-Project Architecture

```
                    ┌─────────────┐
                    │   SPIDERS   │  Objective data
                    │  (7 portals)│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    BANDI    │  Shared table — titolo, ente,
                    │   (table)   │  scadenza, importo, portale
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │                         │
       ┌──────▼──────┐          ┌──────▼──────┐
       │  PROJECT 1  │          │  PROJECT 2  │
       │  La Monica  │          │    PDS      │
       │  ICT rules  │          │ Turismo rules│
       │  score: 75  │          │  score: 45  │  ← same bando,
       │  idoneo     │          │  idoneo     │    different scores
       └─────────────┘          └─────────────┘
       project_evaluations      project_evaluations
```

---

## 3-Layer Architecture

```
LAYER 1 — INTELLIGENCE
  "What exists? Who are we? What can we do?"

  BANDO INGESTION              PROJECT PROFILES (DB)
  Scrapy spiders               projects.profilo JSONB
  → Docling parser             projects.scoring_rules JSONB
  → Claude extract             projects.skills JSONB
  → bandi table (shared)       + embeddings pgvector

LAYER 2 — REASONING (per project)
  "Is it worth it? Can we do it?"

  ELIGIBILITY ENGINE (configurable per project)
  1. Hard stops        → immediate exclusion
  2. Configurable score→ JSONB rules, 0-100
  3. Gap analysis      → what's missing?
  → Results in project_evaluations table

LAYER 3 — EXECUTION
  "Generate, organize, prepare for submission"

  DOC GENERATOR    FORM FILLER    PREP PACK
  Claude draft     Allegato A/B   ZIP folder
  WeasyPrint PDF   PA form fields Checklist
  python-docx      Registry data  README

  ↓ STREAMLIT UI (project selector + kanban + docs) ↓
  ↓ [HUMAN REVIEW] → [MANUAL SIGNATURE] → [SUBMISSION] ↓
```

---

## State Machine — Complete Reference

States live in `project_evaluations.stato`, not in `bandi.stato` (deprecated).

### States

| State | Meaning |
|-------|---------|
| `nuovo` | Just inserted by spider, evaluation pending |
| `analisi` | Parsing in progress |
| `idoneo` | Passes hard stops, score >= 40, awaiting user decision |
| `scartato` | Hard stop triggered OR score < 40 OR user rejected |
| `lavorazione` | User started document preparation |
| `pronto` | Documents generated and approved, ready for submission |
| `inviato` | User confirmed manual submission |
| `archiviato` | Expired without submission |

### Frozen States (evaluation not re-run)
```
{lavorazione, pronto, inviato, archiviato}
```

### Automatic Transitions (system-driven)

```
nuovo      → idoneo      : auto, if score >= 40 AND no hard stop
nuovo      → scartato    : auto, if hard stop OR score < 40
idoneo     → archiviato  : auto, if data_scadenza < today - 3 days
```

### Manual Transitions (user via Streamlit or Telegram)

```
idoneo      → lavorazione : user clicks "Start"
idoneo      → scartato    : user clicks "Ignore"
lavorazione → pronto      : user approves documents
pronto      → inviato     : user confirms submission
```

### Daily Scan Flow

```python
# 1. Spiders scrape all portals → raw items
# 2. Parse each item (Docling + Claude structurer)
# 3. Save to bandi table (objective data, stato='nuovo')
# 4. evaluate_for_all_projects:
#    For each active project:
#      For each bando:
#        - Skip if evaluation is frozen
#        - hard_stops(bando, profile) → scartato if excluded
#        - configurable_scorer(bando, profile, rules) → score
#        - Upsert project_evaluations
#        - Notify Telegram if new idoneo + score > 60
# 5. Progressive deadline alerts per project (30/14/7/3/1 days)
# 6. Weekly cleanup (Sundays)
```

### Score Thresholds

```python
SCORE_NOTIFICATION_THRESHOLD = 60  # configurable per project

if score >= 60:  # notify via Telegram
if 40 <= score < 60:  # idoneo, no notification (borderline)
if score < 40:  # scartato
```

---

## Database Schema (PostgreSQL)

### Table: `projects` (NEW in v0.4.0)
```sql
CREATE TABLE projects (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    nome            TEXT NOT NULL,
    descrizione     TEXT,
    profilo         JSONB NOT NULL,           -- company_profile structure
    skills          JSONB,                    -- skills_matrix structure
    scoring_rules   JSONB NOT NULL,           -- configurable scoring rules
    telegram_chat_id TEXT,                    -- project-specific chat or NULL
    telegram_prefix  TEXT,                    -- '[PDS]' in shared chat
    attivo          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Table: `project_evaluations` (NEW in v0.4.0)
```sql
CREATE TABLE project_evaluations (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    bando_id            INT NOT NULL REFERENCES bandi(id) ON DELETE CASCADE,
    score               INT,
    stato               TEXT DEFAULT 'nuovo' CHECK (stato IN
        ('nuovo','analisi','idoneo','scartato','lavorazione','pronto','inviato','archiviato')),
    motivo_scarto       TEXT,
    hard_stop_reason    TEXT,
    score_breakdown     JSONB,
    gap_analysis        JSONB,
    yellow_flags        JSONB,
    data_invio          TIMESTAMPTZ,
    protocollo_ricevuto TEXT,
    evaluated_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, bando_id)
);
```

### Table: `bandi` (objective data)
```sql
CREATE TABLE bandi (
    id                    SERIAL PRIMARY KEY,
    uuid                  UUID UNIQUE DEFAULT gen_random_uuid(),
    titolo                TEXT NOT NULL,
    ente_erogatore        TEXT,
    url_fonte             TEXT,
    portale               TEXT,
    data_pubblicazione    DATE,
    data_scadenza         DATE,
    budget_totale         NUMERIC(15,2),
    importo_max           NUMERIC(15,2),
    tipo_finanziamento    TEXT,
    aliquota_fondo_perduto NUMERIC(5,2),
    tipo_beneficiario     TEXT[],
    regioni_ammesse       TEXT[],
    fatturato_minimo      NUMERIC(15,2),
    dipendenti_minimi     INT,
    anzianita_minima_anni INT,
    soa_richiesta         BOOLEAN DEFAULT FALSE,
    certificazioni_richieste TEXT[],
    settori_ateco         TEXT[],
    -- DEPRECATED: use project_evaluations instead
    score                 INT,
    stato                 TEXT DEFAULT 'nuovo',
    motivo_scarto         TEXT,
    data_invio            TIMESTAMPTZ,
    protocollo_ricevuto   TEXT,
    --
    dedup_hash            TEXT UNIQUE,
    parent_bando_id       INT REFERENCES bandi(id),
    first_seen_at         TIMESTAMPTZ DEFAULT NOW(),
    raw_text              TEXT,
    metadata              JSONB,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### Supporting Tables
```sql
CREATE TABLE bando_documenti (...);        -- downloaded PDF/docs
CREATE TABLE bando_requisiti (...);        -- parsed requirements (+ project_id)
CREATE TABLE bando_documenti_generati (...); -- generated docs (+ project_id)
CREATE TABLE company_embeddings (...);     -- pgvector (+ project_id)
```

---

## Configurable Scoring Engine

Each project has `scoring_rules` JSONB with a list of rules. Each rule has:
- `name`: identifier
- `type`: handler type (see below)
- `points`: max points for this rule
- `config`: type-specific configuration

### Handler Types

| Type | Description |
|------|-------------|
| `region_match` | Bando regioni_ammesse includes project region |
| `ateco_match` | Bando settori_ateco includes project ATECO |
| `keyword_in_title` | Keywords found in bando titolo/text |
| `keyword_and_profile` | Keywords + profile boolean field is True |
| `importo_min` | importo_max exceeds configured minimum |
| `beneficiary_match` | tipo_beneficiario includes accepted types |
| `no_certifications_required` | No certifications required |
| `profile_age_check` | Owner under 36 + keywords match |
| `company_age` | Company younger than N years + keywords |

### Scoring Templates

Three built-in templates available in UI:
- **ICT / Freelancer** — ATECO ICT priority, PNRR digitalizzazione, under 36, ZES
- **Turismo / Cultura** — turismo, borghi, patrimonio culturale, astronomia, aree interne
- **E-commerce / PMI** — digitalizzazione PMI, voucher digitale, innovazione

---

## Scraping Module

### Scrapy Structure
```
scrapers/
├── settings.py
├── pipelines.py          # Save to PostgreSQL with dedup
├── deduplicator.py       # URL → hash dedup logic
├── middlewares.py        # Rate limiting, retry
└── spiders/
    ├── invitalia.py
    ├── regione_sicilia.py
    ├── mimit.py
    ├── padigitale.py
    ├── inpa.py
    ├── comune_palermo.py
    ├── euroinfosicilia.py
    └── mepa.py           ← DEFERRED
```

---

## Prefect Pipeline — Main Flow

```python
@flow(name="bandi-daily-scan")
def daily_scan():
    # 1. Scrape all portals (parallel spiders)
    # 2. Aggregate raw items
    # 3. Parse each item (Docling + Claude structurer)
    # 4. Save objective data to DB
    # 5. evaluate_for_all_projects (hard_stops + configurable_scorer)
    # 6. Telegram notifications for new idonei per project
    # 7. Progressive deadline alerts per project (30/14/7/3/1d)
    # 8. Weekly cleanup (Sundays)
    # 9. Scan summary notification

daily_scan.serve(cron="0 8 * * *")  # every day at 08:00
```

---

## Streamlit UI — Pages

```
app.py (entry point + project selector in sidebar)
pages/
├── 01_dashboard.py        ← metrics per project, charts, upcoming deadlines
├── 02_bandi.py            ← filterable table, urgency badges, CSV export
├── 03_dettaglio.py        ← full bando card + score breakdown + actions
├── 04_documenti.py        ← generate, review, approve documents
├── 05_profilo.py          ← view project profile + scoring rules
├── 06_config.py           ← active portals, thresholds, spider stats
├── 07_log.py              ← pipeline run logs + errors
└── 08_progetti.py         ← project management + onboarding wizard
```

---

## Telegram Notifications

All messages include project prefix (e.g., `[PDS]`) when using shared chat.
Project-specific `telegram_chat_id` supported for dedicated channels.

### Message Types
- New compatible bando (score > threshold) — with inline keyboard
- Urgent deadline (< URGENCY_THRESHOLD_DAYS)
- Bando updated (scadenza/importo changed)
- Rettifica (amendment) detected
- Spider failure
- Progressive deadline alerts (30/14/7/3/1 days)
- Daily scan summary

---

## File Structure

```
bandi_researcher/
├── AGENT_INSTRUCTIONS.md
├── COMMS.md
├── context/
│   ├── company_profile.json     ← Italian, legacy (now in DB)
│   ├── skills_matrix.json       ← Italian, legacy (now in DB)
│   ├── bandi_target.json
│   └── system_architecture.md   ← THIS FILE
├── engine/
│   ├── docker-compose.yml
│   ├── config.py
│   ├── db/
│   │   ├── migrations/
│   │   │   ├── 001_init.sql
│   │   │   ├── 002_pgvector.sql
│   │   │   ├── 003_fixes.sql
│   │   │   ├── 005_multi_project.sql    ← NEW
│   │   │   └── 005_seed_projects.py     ← NEW
│   │   ├── load_profile.py
│   │   ├── backup.py
│   │   └── cleanup.py
│   ├── projects/                         ← NEW
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── scrapers/
│   │   ├── settings.py
│   │   ├── pipelines.py
│   │   ├── deduplicator.py
│   │   ├── middlewares.py
│   │   └── spiders/ (7 active + 1 deferred)
│   ├── parsers/
│   │   ├── docling_extractor.py
│   │   ├── claude_structurer.py
│   │   └── schema.py
│   ├── eligibility/
│   │   ├── rules.py                      ← multi-project profiles
│   │   ├── hard_stops.py                 ← generalized
│   │   ├── scorer.py                     ← legacy (project #1)
│   │   ├── configurable_scorer.py        ← NEW
│   │   └── gap_analyzer.py              ← generalized
│   ├── pipeline/
│   │   ├── flows.py                      ← multi-project eval
│   │   └── monitor.py
│   ├── generators/
│   │   ├── templates/
│   │   ├── content_generator.py
│   │   ├── fact_checker.py
│   │   ├── pdf_generator.py
│   │   ├── docx_generator.py
│   │   └── package_builder.py
│   ├── notifications/
│   │   ├── telegram_bot.py
│   │   └── alerts.py                     ← project context
│   └── ui/
│       ├── app.py                        ← project selector
│       └── pages/
│           ├── 01_dashboard.py
│           ├── 02_bandi.py
│           ├── 03_dettaglio.py
│           ├── 04_documenti.py
│           ├── 05_profilo.py
│           ├── 06_config.py
│           ├── 07_log.py
│           └── 08_progetti.py            ← NEW
├── output/
└── bandi_trovati/
```

---

## Key Invariants

1. **Never submit anything autonomously.** Every document goes through human approval.
2. **Never generate unverified claims.** fact_checker.py must block unverified content.
3. **Never re-evaluate frozen evaluations** (lavorazione/pronto/inviato/archiviato).
4. **Always create new document versions** (v1, v2...) — never overwrite.
5. **MePA spider is DEFERRED** — do not implement until accreditation confirmed.
6. **Bandi are objective** — never write per-project data to the bandi table.

---

## Migrations Applied

| Migration | Description | Date |
|-----------|-------------|------|
| 001_init.sql | Core tables (bandi, documenti, requisiti, generati) | 2026-03-02 |
| 002_pgvector.sql | company_embeddings with vector extension | 2026-03-02 |
| 003_fixes.sql | Column additions (score, tipo_finanziamento, etc.) | 2026-03-02 |
| 005_multi_project.sql | projects + project_evaluations tables | 2026-03-03 |
| 005_seed_projects.py | Migrated 125 bandi to project #1 (lamonica) | 2026-03-03 |
