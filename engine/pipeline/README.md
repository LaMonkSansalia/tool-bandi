# Pipeline — Prefect Flows

Orchestrazione dell'intero flusso: scraping → parsing → eligibility → notifiche.

## Struttura

```
pipeline/
├── flows.py         ← flow principale daily_scan (Sprint 2)
└── monitor.py       ← logging, alert errori spider (Sprint 4)
```

## Flow Principale

```python
@flow(name="bandi-daily-scan")
def daily_scan():
    raw     = scrape_all_portals()      # parallelo, tutti gli spider attivi
    deduped = deduplicate(raw)          # evita reinserimento
    parsed  = parse_documents(deduped) # Docling + Claude, parallelo
    results = check_eligibility(parsed) # hard stops + scoring
    notify_compatible(results)          # Telegram se score > soglia
    save_to_db(results)

daily_scan.serve(cron="0 8 * * *")     # ogni giorno alle 08:00
```

## UI Prefect

```
http://localhost:4200
```

Visualizza: runs, logs, errori, durata, schedule.

## Trigger Manuale

```bash
cd engine
python -c "from pipeline.flows import daily_scan; daily_scan()"
```
