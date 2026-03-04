# Sprint 0 — Fondamenta

**Stato:** IN CORSO
**Obiettivo:** Avere l'infrastruttura locale funzionante e il profilo aziendale caricato in DB.
**Definizione di "done":** `docker compose up` parte senza errori, Streamlit mostra il profilo aziendale.

---

## Task

### 0.1 — Docker Compose
- [ ] `engine/docker-compose.yml` con servizi: `postgres`, `redis`, `prefect`, `streamlit`
- [ ] `engine/.env.example` con tutte le variabili necessarie
- [ ] Verifica: tutti i servizi si avviano, porte non in conflitto

### 0.2 — Schema Database
- [ ] `engine/db/migrations/001_init.sql` — tabelle: `bandi`, `bando_documenti`, `bando_requisiti`, `bando_documenti_generati`
- [ ] `engine/db/migrations/002_pgvector.sql` — estensione vector + tabella `company_embeddings`
- [ ] Verifica: `psql` si connette, schema applicato correttamente

### 0.3 — Company Profile Loader
- [ ] Script `engine/db/load_profile.py` che:
  - Legge `context/company_profile.json` e `context/skills_matrix.json`
  - Genera embeddings via Claude API (o OpenAI compatible)
  - Inserisce in `company_embeddings`
- [ ] Verifica: query pgvector restituisce risultati sensati

### 0.4 — Requirements e struttura Python
- [ ] `engine/requirements.txt` con tutte le dipendenze
- [ ] `engine/config.py` con settings centralizzati (legge da `.env`)
- [ ] Verifica: `pip install -r requirements.txt` senza errori

### 0.5 — Streamlit pagina profilo (stub)
- [ ] `engine/ui/app.py` con navigazione base
- [ ] `engine/ui/pages/05_profilo.py` — mostra `company_profile.json` in forma leggibile
- [ ] Verifica: Streamlit apre su `localhost:8501`, profilo visibile

---

## Dipendenze Tecniche

```
Python 3.12
PostgreSQL 16 + pgvector
Redis 7
Prefect 3.x
Streamlit 1.x
anthropic (Claude API)
psycopg2-binary
python-dotenv
```

---

## Note Tecniche

- `.env` locale contiene `ANTHROPIC_API_KEY` — mai committare
- PostgreSQL porta: 5432 (verificare no conflitti con Sansalia locale)
- Prefect UI porta: 4200
- Streamlit porta: 8501
- Redis porta: 6379

---

## Output Atteso

```
engine/
├── docker-compose.yml        ✓
├── requirements.txt          ✓
├── .env.example              ✓
├── config.py                 ✓
├── db/
│   ├── migrations/
│   │   ├── 001_init.sql      ✓
│   │   └── 002_pgvector.sql  ✓
│   └── load_profile.py       ✓
└── ui/
    ├── app.py                ✓
    └── pages/
        └── 05_profilo.py     ✓
```
