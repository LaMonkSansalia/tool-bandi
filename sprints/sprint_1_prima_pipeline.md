# Sprint 1 — Prima Pipeline

**Stato:** PENDING (inizia dopo Sprint 0 completato)
**Obiettivo:** Un bando reale entra nel sistema, viene analizzato e compare in Streamlit con score e checklist.
**Definizione di "done":** Prendere un PDF di bando Invitalia, farlo girare nella pipeline, vedere il risultato in Streamlit.

---

## Task

### 1.1 — Spider Invitalia (primo target)
- [ ] `engine/scrapers/spiders/invitalia.py`
  - Crawla la pagina bandi di Invitalia
  - Estrae: titolo, URL, data scadenza, link PDF
  - Scarica i PDF in `bandi_trovati/{data}_{slug}/`
- [ ] `engine/scrapers/pipelines.py` — salva raw data su PostgreSQL (tabella `bandi`)
- [ ] Verifica: `scrapy crawl invitalia` scarica almeno 3 bandi

### 1.2 — Parser Docling + Claude
- [ ] `engine/parsers/docling_extractor.py`
  - Input: path PDF
  - Output: testo markdown strutturato via Docling
- [ ] `engine/parsers/claude_structurer.py`
  - Input: markdown testo bando
  - Output: JSON strutturato con tutti i campi `bandi` + lista `bando_requisiti`
  - Usa DSPy per prompt strutturato e deterministico
- [ ] Verifica: su 3 PDF test, estrae correttamente scadenza, budget, requisiti

### 1.3 — Eligibility Engine (hard stops)
- [ ] `engine/eligibility/hard_stops.py`
  - Legge regole da `context/company_profile.json`
  - Applica filtri in cascata
  - Restituisce: `escluso` con motivo O `passa` con lista yellow flags
- [ ] `engine/eligibility/scorer.py`
  - Calcola score 0-100 sui bandi che passano i hard stops
  - Applica bonus per Sicilia, under35, ATECO, ZES, nuova impresa
- [ ] `engine/eligibility/gap_analyzer.py`
  - Identifica requisiti non soddisfatti ma non escludenti
  - Segnala se il gap è colmabile (es. certificazione ottenibile)
- [ ] Verifica: su 5 bandi diversi, hard stops funzionano correttamente

### 1.4 — Streamlit: Lista Bandi
- [ ] `engine/ui/pages/02_bandi.py`
  - Tabella bandi con colonne: titolo, ente, scadenza, score, stato, semaforo
  - Filtri: stato, score minimo, scadenza, ente
  - Click su riga → dettaglio bando
- [ ] `engine/ui/pages/03_dettaglio_bando.py`
  - Scheda completa del bando
  - Checklist requisiti con semafori (verde/giallo/rosso)
  - Score breakdown (perché questo punteggio)
  - Gap analysis
  - Bottone "Avanza a Lavorazione"
- [ ] Verifica: Streamlit mostra i bandi Invitalia con score e checklist

### 1.5 — Streamlit: Dashboard
- [ ] `engine/ui/pages/01_dashboard.py`
  - Numero bandi trovati oggi/settimana
  - Scadenze entro 7 giorni
  - Bandi in lavorazione
  - Score medio
- [ ] Verifica: dashboard si aggiorna quando arrivano nuovi bandi

---

## Dipendenze Tecniche

```
scrapy>=2.11
scrapy-playwright
docling
anthropic
dspy-ai
psycopg2-binary
streamlit
pandas
```

---

## Struttura Output

```
engine/
├── scrapers/
│   ├── settings.py
│   ├── pipelines.py
│   └── spiders/
│       └── invitalia.py      ✓
├── parsers/
│   ├── docling_extractor.py  ✓
│   └── claude_structurer.py  ✓
├── eligibility/
│   ├── hard_stops.py         ✓
│   ├── scorer.py             ✓
│   └── gap_analyzer.py       ✓
└── ui/
    ├── app.py
    └── pages/
        ├── 01_dashboard.py   ✓
        ├── 02_bandi.py       ✓
        └── 03_dettaglio.py   ✓
```

---

## Rischi

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| Invitalia cambia struttura HTML | Media | Spider con selettori robusti + fallback |
| Docling non gestisce PDF scansionati | Alta | Fallback: Claude multimodal diretta |
| Claude restituisce JSON malformato | Media | DSPy + schema Pydantic per validazione |
