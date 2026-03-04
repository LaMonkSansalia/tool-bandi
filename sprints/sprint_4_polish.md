# Sprint 4 — Polish & Full Automation

**Status:** PENDING
**Objective:** System runs reliably without manual intervention — Telegram notification → click → documents ready.
**Definition of Done:** Morning notification arrives → click in Telegram → Streamlit shows documents ready for signature.

---

## Tasks

### 4.1 — Full Interactive Telegram Bot

- [ ] Inline button callbacks:
  - `[📄 Details]` → direct link to bando Streamlit page
  - `[✅ Analyze]` → trigger parsing + eligibility in background
  - `[❌ Ignore]` → mark bando as scartato, no further notifications
  - `[📂 Generate Docs]` → start document generator
- [ ] Bot commands:
  - `/bandi` — list active bandi with scores
  - `/scadenze` — bandi with deadline in next 7 days
  - `/status` — status of last pipeline run
  - `/help` — command list
- [ ] Verify: all commands respond correctly within 5 seconds

### 4.2 — Progressive Deadline Alerts

- [ ] Progressive alerts for bandi in stato `idoneo` or `lavorazione` only:
  - 30 days before deadline
  - 14 days before deadline
  - 7 days before deadline
  - 3 days before deadline
  - 1 day before deadline
- [ ] Alert includes document completion percentage
- [ ] Verify: alerts arrive on schedule (test with a bando set to expire in 2 days)

### 4.3 — Streamlit UI Polish

- [ ] `engine/ui/pages/01_dashboard.py` — metrics with charts (Plotly):
  - Bandi found per week (bar chart)
  - Score distribution (histogram)
  - Deadline timeline (simple Gantt)
- [ ] Kanban view (`02_bandi.py`):
  - Drag & drop between columns (or button-based for simplicity)
  - Color coding by deadline urgency (red < 7d, orange < 14d, green > 14d)
- [ ] Full-text search across bandi
- [ ] CSV export for bandi list

### 4.4 — Monitoring & Logging

- [ ] `engine/pipeline/monitor.py`
  - Log every run: portals scanned, bandi found, errors
  - Telegram alert if spider fails (portal changed structure)
  - Prefect UI shows full run history
- [ ] `engine/ui/pages/07_log.py`
  - Last execution logs
  - Spider errors with detail
  - Statistics: bandi per portal, weekly trend

### 4.5 — Backup & Maintenance

- [ ] `engine/db/backup.py` — daily PostgreSQL dump
- [ ] `engine/db/cleanup.py` — archive bandi expired > 30 days ago
- [ ] `engine/db/migrations/` — migration versioning system
- [ ] Documentation: how to update a spider when portal changes structure

---

## Complete User Flow (Sprint 4 Done)

```
[08:00] Prefect triggers daily_scan automatically
    ↓
[08:05] Spiders scan all active portals in parallel
    ↓
[08:10] Docling + Claude analyze new PDFs
    ↓
[08:15] Eligibility engine filters and scores
    ↓
[08:16] Telegram:
         "🎯 3 new compatible grants"
         [📄 Voucher Digitalizzazione — score 82]
         [📄 Bando ICT Sicilia — score 71]
         [📄 Smart&Start — score 65]
    ↓
[User clicks "Analyze" on Voucher Digitalizzazione]
    ↓
[Streamlit: requirements checklist — 8 green, 1 yellow]
    ↓
[User clicks "Generate Documents"]
    ↓
[Claude generates customized technical proposal]
[Fact-checker verifies every claim]
[WeasyPrint generates PDF v1]
    ↓
[User reviews and approves in Streamlit]
    ↓
[Download ZIP package]
    ↓
[User signs digitally with smart card — MANUALLY]
    ↓
[User uploads to portal — MANUALLY]
    ↓
[User marks as "Inviato" in Streamlit, enters protocollo_ricevuto]
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| New relevant bandi found/week | > 10 |
| False negatives (missed bandi) | < 5% |
| False positives (wrong eligibility) | < 15% |
| Time from bando found to docs ready | < 30 minutes |
| Fact-checked claims in proposal | 100% |
| Pipeline uptime | > 95% |
