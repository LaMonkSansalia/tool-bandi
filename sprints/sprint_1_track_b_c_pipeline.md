# Sprint 1 / Track B + C — First Pipeline

**Status:** PENDING (Track B starts in parallel with Track A; Track C starts after A+B complete)
**Objective:** A real bando PDF enters the pipeline and appears in Streamlit with score and checklist.
**Definition of Done:** Take a real Invitalia PDF, run it through the pipeline, see the result in Streamlit with score and traffic-light checklist.

---

## Track B — Core Logic (testable standalone, no DB required)

> Track B can be developed **in parallel with Track A**. All components are pure Python logic
> testable with mock HTTP responses and local PDF files — no running database needed.

### B1 — Spider: Invitalia
- [ ] `engine/scrapers/spiders/invitalia.py`
  - Crawls Invitalia bandi page
  - Extracts: titolo, url, data_scadenza, pdf_urls
  - Downloads PDFs to `bandi_trovati/{date}_{slug}/`
  - Outputs normalized dict: `{titolo, ente_erogatore, url, data_scadenza, pdf_urls, testo_html}`
- [ ] `engine/scrapers/settings.py` — Scrapy settings (rate limiting, user-agent, etc.)
- [ ] `engine/scrapers/middlewares.py` — retry, rate limiting
- [ ] Tests: `pytest tests/test_invitalia_spider.py` with mock HTTP (no live requests)
- [ ] Verify: `scrapy crawl invitalia` downloads at least 3 bandi

**Dependency:** none (standalone)

### B2 — Parser: Docling + Claude
- [ ] `engine/parsers/docling_extractor.py`
  - Input: PDF file path
  - Output: structured markdown text via Docling
  - Fallback: Claude multimodal if PDF is scanned (no text layer)
- [ ] `engine/parsers/claude_structurer.py`
  - Input: markdown text
  - Output: validated JSON matching all `bandi` table fields + list of `bando_requisiti`
  - Uses DSPy for structured, deterministic prompting
  - Model: `claude-sonnet-4-6`
- [ ] `engine/parsers/schema.py`
  - Pydantic models for output validation
  - If Claude returns malformed JSON: log error, retry once, then raise
- [ ] Tests: run on 3 local PDF files, verify field extraction accuracy
- [ ] Verify: deadline, budget, and requirements correctly extracted from 3 test PDFs

**Dependency:** none (only needs a local PDF file)

### B3 — Eligibility Engine
- [ ] `engine/eligibility/rules.py`
  - Loads hard stop rules and bonus score rules from `context/company_profile.json`
- [ ] `engine/eligibility/hard_stops.py`
  - Input: parsed bando dict
  - Output: `{"excluded": True, "reason": "..."}` OR `{"excluded": False, "yellow_flags": [...]}`
  - Applies rules in cascade: first match that excludes → stop, return reason
- [ ] `engine/eligibility/scorer.py`
  - Input: parsed bando dict (only if not excluded)
  - Output: `{"score": 0-100, "breakdown": {...}}`
  - Applies bonus points (Sicilia +15, under35 +10, ATECO 62.20 +20, ZES +10, new company +10)
  - Score borderline logic:
    - score > 60 → notify Telegram
    - 40 ≤ score ≤ 60 → save as idoneo, NO notification
    - score < 40 → save as scartato
- [ ] `engine/eligibility/gap_analyzer.py`
  - Input: parsed bando dict + eligibility result
  - Output: list of gaps with `{tipo, descrizione, bloccante, recuperabile, suggerimento}`
- [ ] Tests: run on 5 sample bandi dicts, verify hard stops trigger correctly
- [ ] Verify: hard stops correctly reject bandi requiring >85k turnover, >0 employees, SOA, etc.

**Dependency:** none (pure Python logic, no DB)

---

## Track C — Integration (start after Track A + Track B complete)

### C1 — pgvector Profile Loader
- [ ] `engine/db/load_profile.py`
  - Reads `context/company_profile.json` and `context/skills_matrix.json`
  - Generates embeddings via Claude API (`text-embedding-3-small` or Claude embeddings)
  - Inserts into `company_embeddings` table
  - Idempotent: running twice does not create duplicates
- [ ] Verify: pgvector similarity query returns sensible results

**Dependency:** A2 (needs `company_embeddings` table with pgvector extension)

### C2 — Scrapy → PostgreSQL Pipeline with Dedup
- [ ] `engine/scrapers/deduplicator.py`
  ```python
  import hashlib, unicodedata

  def normalize(text: str) -> str:
      text = unicodedata.normalize('NFD', text)
      text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
      return ' '.join(text.lower().split())

  def compute_dedup_hash(ente: str, titolo: str, anno: int) -> str:
      key = f"{normalize(ente)}|{normalize(titolo)}|{anno}"
      return hashlib.sha256(key.encode()).hexdigest()[:16]

  def find_existing(db, url: str, dedup_hash: str):
      """URL check first, hash as fallback."""
      if url:
          result = db.fetch_one("SELECT * FROM bandi WHERE url_fonte = %s", [url])
          if result: return result
      return db.fetch_one("SELECT * FROM bandi WHERE dedup_hash = %s", [dedup_hash])
  ```
- [ ] `engine/scrapers/pipelines.py`
  - On new bando: compute dedup_hash, check existing, insert OR update per state machine rules:
    ```
    stato IN (lavorazione, pronto, inviato, archiviato, scartato) → SKIP
    stato IN (nuovo, analisi) → silent UPDATE (scadenza, budget, url_pdf)
    stato == idoneo → UPDATE + Telegram if scadenza or budget changed
    not found → INSERT as stato='nuovo'
    ```
  - After insert: trigger async parsing (Docling + Claude) → update stato to 'analisi'
  - After parsing: trigger eligibility → update stato to 'idoneo' or 'scartato'
- [ ] Verify: running spider twice on same portal → no duplicate bandi in DB

**Dependency:** A2 (needs `bandi` table with `dedup_hash` field)

### C3 — Streamlit UI
- [ ] `engine/ui/app.py` — entry point, sidebar navigation
- [ ] `engine/ui/pages/05_profilo.py` — displays company_profile.json in readable format
- [ ] `engine/ui/pages/01_dashboard.py`
  - Metrics: bandi found today/this week
  - Upcoming deadlines (7 days)
  - Bandi in lavorazione
  - Average score
- [ ] `engine/ui/pages/02_bandi.py`
  - Table with columns: titolo, ente, scadenza, score, stato, traffic-light icon
  - Filters: stato, min score, scadenza, ente
  - Click row → detail page
- [ ] `engine/ui/pages/03_dettaglio.py`
  - Full bando card
  - Requirements checklist with traffic lights (verde/giallo/rosso)
  - Score breakdown (why this score)
  - Gap analysis display
  - Button "Move to Lavorazione"
  - Button "Ignore (Scarta)"
- [ ] Verify: Streamlit shows bandi from DB with scores and checklists

**Dependency:** A3 (config.py), C2 (bandi must be in DB)

---

## Risk Table

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Invitalia changes HTML structure | Medium | Robust selectors + fallback to link scraping |
| Docling fails on scanned PDFs | High | Fallback: Claude multimodal API directly |
| Claude returns malformed JSON | Medium | DSPy + Pydantic schema validation, retry once |
| dedup_hash collision | Very low | SHA256 truncated to 16 chars on ~1000 bandi = negligible |

---

## Expected Output

```
engine/
├── scrapers/
│   ├── settings.py           ✓  (Track B)
│   ├── middlewares.py        ✓  (Track B)
│   ├── deduplicator.py       ✓  (Track C)
│   ├── pipelines.py          ✓  (Track C — with dedup logic)
│   └── spiders/
│       └── invitalia.py      ✓  (Track B)
├── parsers/
│   ├── docling_extractor.py  ✓  (Track B)
│   ├── claude_structurer.py  ✓  (Track B)
│   └── schema.py             ✓  (Track B)
├── eligibility/
│   ├── rules.py              ✓  (Track B)
│   ├── hard_stops.py         ✓  (Track B)
│   ├── scorer.py             ✓  (Track B)
│   └── gap_analyzer.py       ✓  (Track B)
├── db/
│   └── load_profile.py       ✓  (Track C)
└── ui/
    ├── app.py                ✓  (Track C)
    └── pages/
        ├── 01_dashboard.py   ✓  (Track C)
        ├── 02_bandi.py       ✓  (Track C)
        ├── 03_dettaglio.py   ✓  (Track C)
        └── 05_profilo.py     ✓  (Track C)
```
