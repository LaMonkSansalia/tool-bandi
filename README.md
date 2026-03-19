# Tool Bandi

Sistema personale per ricercare, analizzare e preparare candidature a bandi pubblici italiani.

**Repo:** github.com/LaMonkSansalia/tool-bandi
**Soggetto:** La Monica Luciano — P.IVA 07104590828
**Scope:** Single-tenant, uso personale
**Principio:** Human-in-the-loop obbligatorio. Il sistema prepara, l'umano decide e invia.

---

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Web framework | FastAPI + Jinja2 (server-rendered) |
| Interattivita' | HTMX + Alpine.js (~30KB totali) |
| Stile | Tailwind CSS (CDN) |
| Database | PostgreSQL 16 + pgvector |
| Engine | Python — scrapers, parser, eligibility, generators |
| Container | Docker: web (uvicorn) + db (pgvector) |

---

## Albero del Progetto

```
tool-bandi/
├── README.md
├── STATUS.md                         ← contesto completo + changelog
│
├── context/                          ← fonte di verita'
│   ├── company_profile.json          ← dati anagrafici + vincoli eligibility
│   ├── skills_matrix.json            ← competenze + referenze
│   ├── bandi_target.json             ← tipologie bandi + portali
│   ├── system_architecture.md        ← architettura tecnica + DB schema
│   ├── ui_requirements.md            ← requisiti UI (storico)
│   ├── project_workspace.md          ← workspace + profilo progetto
│   ├── documents/                    ← documenti ufficiali
│   └── spec/                         ← spec UI/UX + mockup (da tool-bandi-ui)
│       ├── tool-bandi-spec (1).md    ← AUTORITA' per navigazione, pagine, flussi
│       ├── tool-bandi-mockup.jsx     ← riferimento design (classi Tailwind)
│       └── manuale-tool-bandi.docx
│
├── engine/                           ← Python engine (invariato)
│   ├── db/migrations/                ← SQL schema (001-012)
│   ├── scrapers/                     ← 7 spiders Scrapy
│   ├── parsers/                      ← Docling + Claude extraction
│   ├── eligibility/                  ← hard stops + scoring engine
│   ├── generators/                   ← PDF, DOCX, AI content
│   ├── pipeline/                     ← daily_scan, rivalutazione
│   ├── notifications/                ← Telegram bot
│   └── projects/manager.py           ← CRUD operations
│
├── web/                              ← FastAPI + Jinja2 + HTMX
│   ├── main.py                       ← app, Jinja2, static, lifespan
│   ├── deps.py                       ← Depends: get_db, get_nav_context
│   ├── routes/                       ← dashboard, bandi, progetti, soggetti, candidature, pipeline
│   ├── services/                     ← state_machine, completezza, display, queries
│   ├── templates/                    ← layout, pages, partials, components
│   └── static/                       ← htmx, alpine, css
│
├── tests/                            ← pytest
├── docker-compose.yml                ← 2 servizi: web + db
├── Dockerfile
└── requirements.txt
```

---

## Quick Start

```bash
docker compose up -d
# Web UI: http://localhost:8000
```

---

## Storico

- **v0.1–v0.5** (mar 2026): Engine Python — scrapers, parser, eligibility, generators, Streamlit UI
- **v0.6** (mar 2026): Multi-project + soggetti + Django UI (tool-bandi-ui, poi ritirato)
- **v0.7** (mar 2026): Rebuild FastAPI — Django sostituito, un solo repo, un solo processo

---

## Regola Fondamentale

Il sistema **non invia mai nulla autonomamente**.
Ogni documento generato richiede revisione e approvazione esplicita.
Ogni dichiarazione e' responsabilita' dell'umano che la firma.
