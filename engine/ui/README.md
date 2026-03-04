# UI — Streamlit App

Interfaccia utente per gestire l'intero sistema.

## Struttura

```
ui/
├── app.py                    ← entry point, navigazione (Sprint 0)
└── pages/
    ├── 01_dashboard.py       ← metriche e overview (Sprint 1)
    ├── 02_bandi.py           ← lista bandi + kanban (Sprint 1)
    ├── 03_dettaglio.py       ← scheda bando + checklist + score (Sprint 1)
    ├── 04_documenti.py       ← genera, revisiona, approva docs (Sprint 3)
    ├── 05_profilo.py         ← visualizza company_profile (Sprint 0)
    ├── 06_config.py          ← portali, soglie, schedule (Sprint 2)
    └── 07_log.py             ← log runs + errori (Sprint 4)
```

## Avvio

```bash
cd engine
streamlit run ui/app.py
# → http://localhost:8501
```

## Navigazione

```
Sidebar:
  📊 Dashboard
  📋 Bandi
  📄 Documenti
  👤 Profilo
  ⚙️  Config
  📝 Log
```

## Kanban Stati Bando

```
NUOVO → ANALISI → IDONEO → LAVORAZIONE → PRONTO → INVIATO
                    ↘ SCARTATO
```
