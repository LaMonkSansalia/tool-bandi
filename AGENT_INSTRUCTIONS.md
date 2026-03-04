# AGENT_INSTRUCTIONS.md
# Bandi Researcher — Implementation Guide for Autonomous Agent

**Version:** 2.0.0
**Date:** 2026-03-03
**Project root:** `/Users/lucianolamonica/CodiceCodice/Agenti_progetti/bandi_researcher/`
**Language:** All code and new files in English. Context JSON files remain in Italian — do NOT translate them.

---

## 1. Project Overview

Multi-project system to automate research, analysis, and preparation of Italian public grants (bandi).
Bandi are objective data (shared). Evaluations (score, stato, hard stops) are per-project.

### Active Projects

| ID | Slug | Nome | Focus | Sede |
|----|------|------|-------|------|
| 1 | `lamonica` | La Monica Luciano | ICT / Freelancer | Palermo |
| 2 | `pds` | Paese Delle Stelle | Turismo / Cultura | Roccapalumba |

Both projects use the same P.IVA (07104590828) — impresa individuale, regime forfettario.

**Core principle: Human-in-the-loop is mandatory.** The system prepares everything; nothing is ever submitted autonomously.

### Hard Stops (automatic exclusion, shared across projects)
| Field | Condition | Reason |
|-------|-----------|--------|
| `fatturato_minimo` | > 85,000€ | Flat-rate cap |
| `dipendenti_minimi` | > 0 | 0 employees |
| `soa_richiesta` | == true | No SOA certification |
| `tipo_beneficiario` | excludes profile forma_giuridica | Legal form mismatch |
| `regioni_ammesse` | excludes profile region | Geographic |

### Scoring is configurable per project
Each project has JSONB `scoring_rules` with handler types (region_match, keyword_in_title, ateco_match, etc.)
See `context/system_architecture.md` for full handler type reference.

---

## 2. Tech Stack

| Component | Technology |
|-----------|-----------|
| Scraping | Scrapy + scrapy-playwright |
| Document AI | Docling (IBM, open source) |
| LLM | Claude API — `claude-sonnet-4-6` |
| LLM Orchestration | DSPy (structured, deterministic prompting) |
| Pipeline/Scheduling | Prefect 3.x |
| Database | PostgreSQL 16 + pgvector |
| Cache/Queue | Redis 7 |
| Notifications | python-telegram-bot |
| Doc Output | WeasyPrint + Jinja2 (PDF), python-docx (DOCX) |
| UI | Streamlit |
| Container | Docker Compose |

---

## 3. Implementation Strategy: Parallel Tracks

**DO NOT implement sequentially.** The three tracks below can run in parallel:

```
TRACK A — Infrastructure (no code logic, just setup)
  A1. docker-compose.yml
  A2. DB migrations SQL (with ALL updated fields)
  A3. requirements.txt + config.py
  DoD: `docker compose up` succeeds, schema applied

TRACK B — Core Logic (testable WITHOUT Docker/DB)
  B1. engine/scrapers/spiders/invitalia.py  (mock HTTP in tests)
  B2. engine/parsers/docling_extractor.py + claude_structurer.py
  B3. engine/eligibility/hard_stops.py + scorer.py + gap_analyzer.py
  DoD: B1→B2→B3 pipeline runs in-memory on a real PDF, correct JSON output

TRACK C — Integration (requires A + B complete)
  C1. engine/db/load_profile.py  (pgvector)
  C2. engine/scrapers/pipelines.py → PostgreSQL with dedup logic
  C3. engine/ui/app.py + Streamlit pages
  DoD: end-to-end working, Streamlit shows bandi with scores
```

**Start A and B simultaneously. Start C only when A and B are both stable.**

---

## 4. State Machine — Complete Reference

### States
| State | Meaning |
|-------|---------|
| `nuovo` | Just inserted by spider, parsing queued |
| `analisi` | Docling + Claude processing (async) |
| `idoneo` | Passes hard stops, score > threshold, awaiting user decision |
| `scartato` | Hard stop triggered OR user manually rejected |
| `lavorazione` | User started document preparation |
| `pronto` | Documents generated, approved, ready for manual submission |
| `inviato` | User confirmed submission |
| `archiviato` | Expired without submission (auto, after deadline + 3 days) |

### Daily Scan Update Logic (Multi-Project)

```python
# 1-3. Scrape + parse (objective data)
# 4. save_to_db: insert bandi with stato='nuovo' (or 'archiviato' if expired)
# 5. evaluate_for_all_projects:
#    For each active project:
#      For each bando:
#        - Skip if evaluation is in frozen state
#        - Run hard_stops(bando, profile)
#        - Run configurable_scorer(bando, profile, scoring_rules)
#        - Upsert project_evaluations
#        - Notify Telegram if new idoneo + score > 60
# 6. Progressive deadline alerts per project
```

### Score Thresholds

```python
SCORE_NOTIFICATION_THRESHOLD = 60  # configurable per project

score >= 60: idoneo + Telegram notification
40 <= score < 60: idoneo, no notification (borderline)
score < 40: scartato
```

---

## 5. Database Schema

See `context/system_architecture.md` for complete schema reference.

Key tables:
- `projects` — project profiles, scoring rules, telegram config
- `project_evaluations` — per-project score/stato for each bando (UNIQUE project_id + bando_id)
- `bandi` — objective bando data (shared across projects)
- `bando_documenti_generati` — generated documents (+ project_id)
- `bando_requisiti` — parsed requirements (+ project_id)
- `company_embeddings` — pgvector embeddings (+ project_id)

Migrations: 001_init, 002_pgvector, 003_fixes, 005_multi_project

---

## 6. Deduplication Logic

```python
import hashlib
import unicodedata

def normalize(text: str) -> str:
    """Lowercase, remove accents, collapse whitespace."""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return ' '.join(text.lower().split())

def compute_dedup_hash(ente: str, titolo: str, anno: int) -> str:
    key = f"{normalize(ente)}|{normalize(titolo)}|{anno}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def find_existing_bando(db, url: str, dedup_hash: str):
    """URL check first, hash as fallback."""
    if url:
        result = db.query("SELECT * FROM bandi WHERE url_fonte = %s", [url])
        if result:
            return result
    return db.query("SELECT * FROM bandi WHERE dedup_hash = %s", [dedup_hash])
```

---

## 7. Document Versioning

When regenerating a document, **do NOT overwrite** — create a new version:

```python
def save_generated_doc(db, bando_id: int, tipo: str, file_path: str):
    # Get current max version for this bando + tipo
    max_ver = db.query(
        "SELECT MAX(versione) FROM bando_documenti_generati WHERE bando_id=%s AND tipo=%s",
        [bando_id, tipo]
    )
    new_version = (max_ver or 0) + 1
    # File naming: 02_proposta_tecnica_v1.pdf, _v2.pdf, etc.
    # Streamlit shows version list with date + approved/draft badge
```

---

## 8. Document Generator — Anti-Hallucination Rule

**CRITICAL:** Every claim in generated documents must be traceable to `company_profile.json` or `skills_matrix.json`.

```python
# fact_checker.py must block output if any claim is unverified
claim_record = {
    "claim": "Developed 3 e-commerce projects in the last 3 years",
    "source": "skills_matrix.json → referenze_progetti[namamandorle, phimostop, sansalia]",
    "verified": True,
    "verified_at": "2026-03-02"
}
# If verified == False → BLOCK output, flag for human review
```

**Fields with missing data** (e.g., economic amounts in referenze): generate with `"⚠️ TO FILL MANUALLY"` placeholder. Streamlit highlights these fields before document approval.

---

## 9. Telegram Notifications

### New compatible bando (score > threshold)
```
🎯 NEW COMPATIBLE GRANT

📋 {titolo}
🏛️ {ente_erogatore}
💰 Up to {importo_max}€
📅 Deadline: {data_scadenza}

✅ Score: {score}/100
⚠️ {n_yellow_flags} yellow flag(s)

[📄 Details] [✅ Analyze] [❌ Ignore]
```

### Urgent — expiring soon (< 14 days, first seen)
```
🔴 URGENT — GRANT EXPIRING IN {N} DAYS

📋 {titolo}
🏛️ {ente}  |  Score: {score}/100
📅 Deadline: {data_scadenza}

[📄 Details]
```

### Bando updated (stato: idoneo/lavorazione/pronto)
```
⚠️ Grant updated: {titolo}
Deadline: {old_scadenza} → {new_scadenza}  [if changed]
Budget: {old_budget} → {new_budget}        [if changed]

[📄 Details]
```

### Spider failure
```
⚠️ SPIDER FAILED

🕷️ Spider: {spider_name}
❌ Error: {message}
🕐 {timestamp}

[🔍 Prefect Logs]
```

---

## 10. Output Package Structure

```
output/bandi/{YYYYMMDD}_{slug}/
├── 00_README.md              ← instructions + portal URL + submission deadline
├── 01_checklist_invio.md     ← step-by-step manual submission todo
├── 02_proposta_tecnica_v1.pdf   ← TO SIGN (versioned)
├── 03_dichiarazione_sostitutiva_v1.pdf  ← TO SIGN
├── 04_allegato_a_v1.pdf      ← TO SIGN (if required by bando)
├── 05_cv_impresa_v1.pdf      ← informational
├── 06_visura_camerale.pdf    ← copy from context/documents/
└── submission_info.json      ← {portal_url, deadline, data_invio: null, protocollo: null}
```

### submission_info.json (template)
```json
{
  "bando_id": 42,
  "portal_url": "https://...",
  "deadline": "2026-04-30",
  "submission_type": "online_form",
  "checklist_fields": ["upload proposta tecnica", "upload dichiarazione", "firma digitale"],
  "data_invio": null,
  "protocollo_ricevuto": null,
  "notes": ""
}
```

---

## 11. Portals to Monitor

| Spider | Portal | Priority | Notes |
|--------|--------|----------|-------|
| `invitalia.py` | invitalia.it | HIGH — Sprint 1 | HTTP + BeautifulSoup |
| `regione_sicilia.py` | regione.sicilia.it | HIGH — Sprint 2 | HTTP + BeautifulSoup |
| `mimit.py` | mimit.gov.it | HIGH — Sprint 2 | HTTP |
| `padigitale.py` | padigitale2026.gov.it | HIGH — Sprint 2 | HTTP |
| `inpa.py` | inpa.gov.it | MEDIUM — Sprint 2 | HTTP; form-based portal |
| `comune_palermo.py` | comune.palermo.it | MEDIUM — Sprint 2 | HTTP |
| `euroinfosicilia.py` | euroinfosicilia.it | LOW — Sprint 2 | HTTP |
| `mepa.py` | acquistinretepa.it | DEFERRED | Requires accreditation first |

**Note on form-based portals (InPA, etc.):** System generates same PDF documents + the checklist explains field-by-field where to upload them on the web form.

**MePA status:** DEFERRED — accreditation as supplier required first. Build spider only after accreditation is complete.

---

## 12. Infrastructure Notes

- **Ports used:**
  - PostgreSQL: 5432
  - Redis: 6379
  - Prefect UI: 4200
  - Streamlit: 8501
- **No conflicts with Sansalia docker** (Sansalia uses internal Redis, no exposed PostgreSQL, no services on 4200/8501)
- Python version: 3.12
- All secrets in `.env` (never commit)
- `.gitignore` must include: `.env`, `output/`, `context/documents/`, `data/`

---

## 13. File Structure

See `context/system_architecture.md` for complete file tree with annotations.

---

## 14. Implementation Status

All sprints 0-5 are **COMPLETE** (~97%).

| Sprint | Status | Key Deliverables |
|--------|--------|-----------------|
| 0-1 | DONE | Infrastructure + core logic + integration |
| 2 | DONE | 7 spiders + Prefect + Telegram + alerts |
| 3 | DONE | Document generator + templates + fact checker |
| 4 | DONE | Plotly charts + progressive alerts + monitoring |
| 5 | DONE | Multi-project architecture + PDS onboarding |

### Remaining
- End-to-end live scraping test
- MePA integration (deferred — accreditation required)

---

## 15. Key Invariants (NEVER violate these)

1. **Never submit anything autonomously.** Every document goes through human approval.
2. **Never generate unverified claims.** fact_checker.py must block all unverified content.
3. **Never reset bando stato to 'nuovo'** during daily scan updates.
4. **Never re-run eligibility** on a bando that's already in lavorazione/pronto/inviato.
5. **Never commit `.env`** or files in `context/documents/` or `output/`.
6. **Always create new document versions** (v1, v2...) — never overwrite approved documents.
7. **MePA spider is DEFERRED** — do not implement until accreditation is confirmed.

---

## 16. Italian Context — Naming & UI Conventions

**This is a critical section. Read before writing any UI code or user-facing strings.**

### Why this matters
The system operates entirely in the Italian public procurement ecosystem. The users of the UI (even if there's only one: Luciano), the documents produced, and the domain terminology are all Italian. Code files and technical components are in English, but anything visible to the user or part of domain logic must respect Italian conventions.

### Rules

**Code and file names → English**
```
hard_stops.py ✓        # Python module
scorer.py ✓            # Python module
find_existing() ✓      # function name
SCORE_NOTIFICATION_THRESHOLD ✓  # config constant
```

**UI labels, field names, document titles → Italian (as per PA standard)**
```python
# Streamlit labels:
st.header("Bandi disponibili")          # ✓ Italian
st.header("Available grants")           # ✗ wrong

# Document types:
"proposta_tecnica"                      # ✓ Italian domain term
"technical_proposal"                    # ✗ wrong for document naming

# State labels in UI:
"Idoneo" / "In lavorazione" / "Pronto" # ✓ Italian
"Eligible" / "In progress" / "Ready"   # ✗ wrong
```

**Database field names → Italian for domain terms**
```sql
-- These are PA domain terms — keep Italian:
titolo, ente_erogatore, data_scadenza, fatturato_minimo
dipendenti_minimi, soa_richiesta, regime_forfettario

-- These are technical fields — English is fine:
dedup_hash, first_seen_at, created_at, updated_at
```

**Telegram messages → Italian**
All Telegram bot messages are in Italian (they go to an Italian user about Italian grants):
```
"🎯 NUOVO BANDO COMPATIBILE"     ✓
"🎯 NEW COMPATIBLE GRANT"        ✗
```

**Log messages and code comments → English is fine**
Internal logs, Python docstrings, code comments → English is acceptable.

### Key Italian Terms to Use Consistently

| English | Italian (use this) |
|---------|-------------------|
| Grant / Tender | Bando |
| Submitting entity | Soggetto proponente / Ente |
| Deadline | Scadenza |
| Technical proposal | Proposta tecnica |
| Self-declaration | Dichiarazione sostitutiva |
| Eligibility | Idoneità / Eligibilità |
| Score | Punteggio / Score (both acceptable in UI) |
| Attachment | Allegato |
| Portal | Portale |
| Work package | Lavorazione |
| Submission | Invio |
| Protocol number | Numero di protocollo |
| Amendment notice | Avviso di rettifica |
| Hard stop | Hard stop (technical term, keep English in code) |
| Traffic light | Semaforo |

### Document Template Language
All generated documents (proposta tecnica, dichiarazione sostitutiva, etc.) must be **entirely in Italian** — they are official Italian public administration documents.
