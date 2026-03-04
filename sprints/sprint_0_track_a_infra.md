# Sprint 0 / Track A — Infrastructure

**Status:** IN PROGRESS
**Objective:** Local infrastructure running with correct database schema.
**Definition of Done:** `docker compose up` succeeds without errors, all DB tables created with correct schema.

> **Note:** This sprint was renamed from "Sprint 0 — Fondamenta" after the brainstorming session.
> The original task 0.3 (pgvector profile loader) has been moved to **Track C** (Sprint 1),
> as it depends on the schema being in place first and can run in parallel with Track B.

---

## Tasks

### A1 — Docker Compose
- [ ] `engine/docker-compose.yml` with services: `postgres`, `redis`, `prefect`, `streamlit`
- [ ] `engine/.env.example` with all required variables
- [ ] Verify: all services start, no port conflicts

**Ports:**
- PostgreSQL: 5432
- Redis: 6379
- Prefect UI: 4200
- Streamlit: 8501

**No conflicts with Sansalia docker** (verified: Sansalia uses internal Redis, no exposed PostgreSQL, nothing on 4200/8501).

### A2 — Database Schema
- [ ] `engine/db/migrations/001_init.sql` — tables: `bandi`, `bando_documenti`, `bando_requisiti`, `bando_documenti_generati`
- [ ] `engine/db/migrations/002_pgvector.sql` — vector extension + `company_embeddings` table

**CRITICAL — 001_init.sql MUST include these fields (added in brainstorming):**

```sql
-- On table bandi:
dedup_hash            TEXT UNIQUE,           -- sha256(normalize(ente)|normalize(titolo)|year)[:16]
parent_bando_id       INT REFERENCES bandi(id),  -- for rettifica (amendment) notices
first_seen_at         TIMESTAMPTZ DEFAULT NOW(), -- when spider first discovered this bando
data_invio            TIMESTAMPTZ,           -- when user confirmed manual submission
protocollo_ricevuto   TEXT,                  -- protocol number received post-submission

-- stato CHECK must include 'archiviato':
stato TEXT DEFAULT 'nuovo'
      CHECK (stato IN ('nuovo','analisi','idoneo','scartato',
                       'lavorazione','pronto','inviato','archiviato')),

-- On table bando_documenti_generati:
versione INT DEFAULT 1,  -- increments on each regeneration (v1, v2, v3...)
```

- [ ] Verify: `psql` connects, schema applied correctly
- [ ] Verify: all 8 stato values accepted by CHECK constraint
- [ ] Verify: UNIQUE constraint on `dedup_hash` works (insert duplicate → error)

### A3 — Python Requirements and Config
- [ ] `engine/requirements.txt` with all dependencies:
  ```
  scrapy>=2.11
  scrapy-playwright
  docling
  anthropic
  dspy-ai
  psycopg2-binary
  redis
  prefect>=3.0
  streamlit
  pandas
  python-telegram-bot
  weasyprint
  jinja2
  python-docx
  pgvector
  python-dotenv
  pydantic
  ```
- [ ] `engine/config.py` with centralized settings (reads from `.env`):
  ```python
  SCORE_NOTIFICATION_THRESHOLD = 60   # min score to send Telegram notification
  URGENCY_THRESHOLD_DAYS = 14         # days remaining to trigger urgent notification
  ARCHIVE_AFTER_DAYS = 3              # days after deadline to auto-archive
  DATABASE_URL = ...
  REDIS_URL = ...
  ANTHROPIC_API_KEY = ...
  TELEGRAM_BOT_TOKEN = ...
  TELEGRAM_CHAT_ID = ...
  ```
- [ ] Verify: `pip install -r requirements.txt` without errors

---

## Dependencies

- Track B can start in parallel immediately (no dependency on Track A for core logic)
- Track C depends on A2 (schema must exist before pgvector loader or Scrapy pipelines)

---

## Expected Output

```
engine/
├── docker-compose.yml        ✓
├── requirements.txt          ✓
├── .env.example              ✓
├── config.py                 ✓
└── db/
    └── migrations/
        ├── 001_init.sql      ✓  (with ALL new fields)
        └── 002_pgvector.sql  ✓
```
