# Sprint 2 — Scrapers & Scheduling

**Status:** PENDING
**Objective:** All priority portals monitored automatically every morning.
**Definition of Done:** Prefect flow runs at 08:00, Telegram notification arrives with new compatible bandi.

---

## Tasks

### 2.1 — Spiders for Each Priority Portal

| Spider | Portal | Technique | Difficulty | Sprint |
|--------|--------|-----------|------------|--------|
| `invitalia.py` | invitalia.it | HTTP + BS4 | Low | Track B |
| `regione_sicilia.py` | regione.sicilia.it | HTTP + BS4 | Medium | Sprint 2 |
| `mimit.py` | mimit.gov.it | HTTP + BS4 | Medium | Sprint 2 |
| `padigitale.py` | padigitale2026.gov.it | HTTP | Low | Sprint 2 |
| `inpa.py` | inpa.gov.it | HTTP | Medium | Sprint 2 |
| `comune_palermo.py` | comune.palermo.it/albopretorio | HTTP | Medium | Sprint 2 |
| `euroinfosicilia.py` | euroinfosicilia.it | HTTP | Low | Sprint 2 |
| `mepa.py` | acquistinretepa.it | scrapy-playwright | High | **DEFERRED** |

> **MePA is DEFERRED:** Requires supplier accreditation on the platform before scraping is meaningful.
> Build this spider only after accreditation is complete.

Each spider must:
- [ ] Handle errors gracefully (HTTP errors, timeouts, structure changes)
- [ ] Implement retry logic (via Scrapy middlewares)
- [ ] Include logging at each step
- [ ] Handle amendment notices (avvisi di rettifica):
  - If document title contains "rettifica" → attempt to link `parent_bando_id` to original bando
  - If original is in stato `idoneo/lavorazione/pronto` → send Telegram warning

- [ ] Test: at least 3 bandi extracted per portal (run manually, log output)

### 2.2 — Full Prefect Flow

- [ ] `engine/pipeline/flows.py`
  ```python
  from prefect import flow, task

  @flow(name="bandi-daily-scan")
  def daily_scan():
      raw = scrape_all_portals()       # parallel — all active spiders
      deduped = deduplicate(raw)       # URL → hash dedup
      parsed = parse_documents(deduped) # Docling + Claude, parallel
      results = check_eligibility(parsed)
      notify_compatible(results)       # Telegram if score > threshold
      save_to_db(results)              # with state machine update logic

  daily_scan.serve(cron="0 8 * * *")  # every day at 08:00
  ```
- [ ] Prefect UI shows runs, logs, errors at `http://localhost:4200`
- [ ] Verify: full flow runs end-to-end without errors
- [ ] Verify: manual trigger works:
  ```bash
  python -c "from pipeline.flows import daily_scan; daily_scan()"
  ```

### 2.3 — Telegram Bot (base)

- [ ] `engine/notifications/telegram_bot.py`
  - Bot token from `.env`
  - Message on new compatible bando with score and deadline
  - Inline buttons:
    - `[📄 Details]` → Streamlit link for this bando
    - `[✅ Analyze]` → starts parsing + eligibility in background
    - `[❌ Ignore]` → marks bando as scartato
- [ ] `engine/notifications/alerts.py`
  - Alert: new bando score > threshold
  - Alert: urgency (< URGENCY_THRESHOLD_DAYS remaining, first seen)
  - Alert: bando updated (scadenza or budget changed, stato idoneo or above)
  - Alert: spider failure (sent to Telegram as monitoring)
- [ ] Verify: Telegram message arrives after pipeline run

### 2.4 — Streamlit: Configuration Page

- [ ] `engine/ui/pages/06_config.py`
  - Toggle active/inactive portals
  - Score threshold for notifications (default: 60)
  - Pipeline execution time
  - Log of last executions

---

## Expected Output

```
engine/
├── scrapers/spiders/
│   ├── invitalia.py          ✓ (Track B)
│   ├── regione_sicilia.py    ✓
│   ├── mimit.py              ✓
│   ├── padigitale.py         ✓
│   ├── inpa.py               ✓
│   ├── comune_palermo.py     ✓
│   └── euroinfosicilia.py    ✓
│   (mepa.py — DEFERRED)
├── pipeline/
│   └── flows.py              ✓
└── notifications/
    ├── telegram_bot.py       ✓
    └── alerts.py             ✓
```
