# Ricercatore e Applicatore di Bandi

Sistema personale per ricercare, analizzare e preparare bandi pubblici italiani.

**Soggetto:** La Monica Luciano — P.IVA 07104590828
**Scope:** Single-tenant, uso personale
**Principio:** Human-in-the-loop obbligatorio. Il sistema prepara, l'umano decide e invia.

---

## Albero del Progetto

```
Ricercatore e applicatore di bandi/
│
├── README.md                          ← questo file
│
├── context/                           ← FONTE DI VERITÀ (non modificare manualmente)
│   ├── company_profile.json           ← dati anagrafici + vincoli eligibility
│   ├── skills_matrix.json             ← competenze dimostrabili + referenze clienti
│   ├── bandi_target.json              ← tipologie bandi + portali da monitorare
│   ├── system_architecture.md         ← architettura tecnica + DB schema + roadmap
│   └── documents/                     ← documenti ufficiali (visura, dichiarazioni)
│       └── visura_LMNLCN95P22G273W_20260302.pdf
│
├── sprints/                           ← pianificazione iterazioni
│   ├── sprint_0_fondamenta.md
│   ├── sprint_1_prima_pipeline.md
│   ├── sprint_2_scrapers.md
│   ├── sprint_3_document_generator.md
│   └── sprint_4_polish.md
│
├── engine/                            ← codice Python (core del sistema)
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── .env.example
│   ├── db/
│   │   ├── README.md
│   │   └── migrations/                ← SQL schema
│   ├── scrapers/
│   │   ├── README.md
│   │   ├── settings.py
│   │   ├── pipelines.py
│   │   └── spiders/
│   ├── parsers/
│   │   └── README.md                  ← Docling + Claude extraction
│   ├── eligibility/
│   │   └── README.md                  ← hard stops + scoring engine
│   ├── generators/
│   │   └── README.md                  ← WeasyPrint + python-docx
│   ├── pipeline/
│   │   └── README.md                  ← Prefect flows
│   ├── notifications/
│   │   └── README.md                  ← Telegram bot
│   └── ui/
│       └── README.md                  ← Streamlit app
│
├── bandi_trovati/                     ← runtime: PDF e dati scaricati (gitignored)
└── output/                            ← runtime: documenti generati (gitignored)
    └── bandi/
        └── {YYYYMMDD}_{slug}/
            ├── 00_README.md
            ├── 01_checklist_invio.md
            ├── 02_proposta_tecnica.pdf
            └── ...
```

---

## Quick Start (dopo Sprint 0)

```bash
cd engine
docker compose up -d
# Prefect UI: http://localhost:4200
# Streamlit:  http://localhost:8501
```

---

## Stato Corrente

| Sprint | Stato | Descrizione |
|--------|-------|-------------|
| Sprint 0 | IN CORSO | Fondamenta: Docker + DB + struttura |
| Sprint 1 | PENDING | Prima pipeline: scraping + parsing + eligibility |
| Sprint 2 | PENDING | Scrapers multipli + scheduling |
| Sprint 3 | PENDING | Document generator |
| Sprint 4 | PENDING | Telegram bot + polish |

---

## Regola Fondamentale

Il sistema **non invia mai nulla autonomamente**.
Ogni documento generato richiede revisione e approvazione esplicita.
Ogni dichiarazione è responsabilità dell'umano che la firma.
