# Scrapers — Web Crawling

Scrapy + scrapy-playwright to monitor Italian PA grant portals.

## Structure

```
scrapers/
├── settings.py              ← Scrapy global settings
├── pipelines.py             ← Save to PostgreSQL with dedup logic
├── deduplicator.py          ← Deduplication logic (URL → hash)
├── middlewares.py           ← Rate limiting, retry, user-agent rotation
└── spiders/
    ├── invitalia.py         ← Track B / Sprint 1
    ├── regione_sicilia.py   ← Sprint 2
    ├── mimit.py             ← Sprint 2
    ├── padigitale.py        ← Sprint 2
    ├── inpa.py              ← Sprint 2
    ├── comune_palermo.py    ← Sprint 2
    ├── euroinfosicilia.py   ← Sprint 2
    └── mepa.py              ← DEFERRED (supplier accreditation required first)
```

## Running

```bash
cd engine
scrapy crawl invitalia
scrapy crawl invitalia -o output.json   # debug mode
```

## Deduplication Logic

Each bando is identified by a **two-level dedup key**:

1. **Primary:** `url_fonte` (exact URL match)
2. **Fallback:** `dedup_hash = sha256(normalize(ente) + "|" + normalize(titolo) + "|" + year)[:16]`

Normalization: lowercase, strip accents (NFD decomposition), collapse whitespace.

### Pipeline update logic (per state machine):

```python
existing = find_existing(db, url, dedup_hash)

if not existing:
    # New bando — insert and queue parsing
    INSERT bandi (stato='nuovo', first_seen_at=now(), ...)

elif existing.stato in ('lavorazione', 'pronto', 'inviato', 'archiviato', 'scartato'):
    pass  # SKIP COMPLETELY

elif existing.stato in ('nuovo', 'analisi'):
    # Silent update — no notification
    UPDATE bandi SET scadenza=..., budget=..., url_pdf=..., updated_at=now()

elif existing.stato == 'idoneo':
    # Update + conditional Telegram notification
    UPDATE bandi SET scadenza=..., budget=..., updated_at=now()
    if scadenza_changed or budget_changed:
        send_telegram_update_notification(existing)
```

### Amendment notices (avvisi di rettifica):

```python
if 'rettifica' in spider_output['titolo'].lower():
    # Attempt to find the original bando and link it
    original = find_original_bando(db, ente, keywords)
    if original:
        INSERT bandi (parent_bando_id=original.id, ...)
        if original.stato in ('idoneo', 'lavorazione', 'pronto'):
            send_telegram_rettifica_alert(original, new_bando)
```

## Adding a New Spider

1. Create `spiders/{portal_name}.py`
2. Test manually: `scrapy crawl {name}`
3. Add to `pipeline/flows.py` in active spiders list
4. Add toggle in `ui/pages/06_config.py`

## Note on MePA

**MePA (acquistinretepa.it) is DEFERRED.** Supplier accreditation on the platform is required before scraping is useful. Do not implement `mepa.py` until accreditation is confirmed.
