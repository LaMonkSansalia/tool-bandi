# DB — Database Layer

PostgreSQL 16 + pgvector schema management.

## Structure

```
db/
├── migrations/
│   ├── 001_init.sql         ← main tables (Track A / Sprint 0)
│   └── 002_pgvector.sql     ← vector extension + company_embeddings (Track A)
├── load_profile.py          ← load company_profile into pgvector (Track C)
├── backup.py                ← daily dump (Sprint 4)
└── cleanup.py               ← archive expired bandi (Sprint 4)
```

## Connection

```bash
psql postgresql://bandi:bandi@localhost:5432/bandi_db
```

## Apply Migrations

```bash
psql $DATABASE_URL -f migrations/001_init.sql
psql $DATABASE_URL -f migrations/002_pgvector.sql
```

## Key Fields Added in v0.3 (brainstorming decisions)

All of these MUST be in `001_init.sql`:

| Field | Table | Purpose |
|-------|-------|---------|
| `dedup_hash TEXT UNIQUE` | `bandi` | SHA256-based dedup key |
| `parent_bando_id INT REFERENCES bandi(id)` | `bandi` | Links amendment notices to original |
| `first_seen_at TIMESTAMPTZ` | `bandi` | When spider first discovered this bando |
| `data_invio TIMESTAMPTZ` | `bandi` | When user confirmed manual submission |
| `protocollo_ricevuto TEXT` | `bandi` | Protocol number received after submission |
| `archiviato` in stato CHECK | `bandi` | Auto-archive state for expired bandi |
| `versione INT DEFAULT 1` | `bando_documenti_generati` | Document version tracking |
