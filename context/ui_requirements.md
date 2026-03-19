# UI Requirements — tool-bandi-ui

**Version:** 1.0.0
**Date:** 2026-03-19
**Scope:** Nuova interfaccia web per tool-bandi (sostituisce Streamlit)
**Status:** Pianificazione completata — stack tecnologico da scegliere (US-001 Sprint 0)

---

## Motivazione

Il layer Streamlit causa:
- Full-page rerun ad ogni click
- Nessun modale nativo
- Azioni sempre in fondo alla pagina (UX critica)
- Session state fragile, nessun URL per pagina specifica
- Nessuna separazione chiara fra scheda bando e workspace candidatura

Il Python engine (scrapers, parser, eligibility, document generator) rimane **invariato**.
Cambia solo il layer UI. La nuova app legge lo stesso DB PostgreSQL.

---

## Architettura Fondamentale

### Separazione responsabilità

| UI fa | Python engine fa |
|-------|-----------------|
| Visualizza bandi con filtri reattivi | Scrapa portali, analizza PDF |
| Gestisce stato candidatura (state machine) | Calcola score + hard stops |
| Workspace per candidatura specifica | Genera documenti (Claude + WeasyPrint) |
| Profilo progetto come fonte di verità | Mantiene dati nel DB |
| Trigger scansione / ri-valutazione | Esegue pipeline Prefect |

### Principio chiave: Soggetti ≠ Progetti

**SOGGETTO** = chi fa la domanda → determina **hard stops** (P.IVA, regime fiscale, dipendenti).
**PROGETTO/INIZIATIVA** = per cosa si fa la domanda → determina **scoring** (keywords, settore, template).
**VALUTAZIONE** = bando × progetto × soggetto (combinazione esplicita).

Stessa bando può essere valutata per PDS con P.IVA vs PDS con futura SRL: hard stops diversi, score uguale.

### DB Ownership

**Tabelle Python-owned (UI: read + write limitato):**
- `bandi` — read-only dalla UI
- `project_evaluations` — UI scrive: `stato`, `motivo_scarto`, `data_invio`, `protocollo_ricevuto`, `workspace_checklist`, `workspace_notes`, `workspace_completezza`
- `projects` — UI scrive: `nome`, `slug`, `profilo` JSONB, `scoring_rules` JSONB
- `soggetti` — read-only dalla UI (write via migration Python)
- `bando_documenti_generati` — UI scrive: `stato` documento
- `pipeline_runs` — read-only

**Tabelle UI-owned (migrations create dall'app):**
- `users` — autenticazione
- `project_decisions` — decisioni strategiche per progetto

---

## Stack Tecnologico (⚠️ DECISIONE APERTA — US-001)

### Opzione A — FastAPI + HTMX + Alpine.js `[CONSIGLIATA dall'analisi]`
Stack: Python puro · Jinja2 templates · Tailwind CSS
- **Pro:** Nessun bridge Python, stesso ecosistema engine, deploy 1 Docker service
- **Contro:** ~40% UI da costruire vs Filament. State machine e modali custom.
- **Stima:** 6-8 settimane

### Opzione B — Laravel 13 + Filament v4
Stack: PHP · Livewire v4 · Tailwind CSS
- **Pro:** UI admin più ricca. State machine, modali, filtri tabella first-class.
- **Contro:** PHP = secondo linguaggio. `shell_exec()` bridge per trigger Python.
- **Stima:** 5-6 settimane UI + 2-3 bridge

### Opzione C — Django 5.2 LTS + Unfold
Stack: Python · Django ORM · Tailwind CSS
- **Pro:** Python puro, LTS stabile, admin pattern maturi, `django-fsm-2`.
- **Contro:** Meno flessibile di FastAPI per UX custom.
- **Stima:** 5-6 settimane

### Opzione D — Next.js 16 + FastAPI
Stack: TypeScript + Python · App Router · shadcn/ui
- **Pro:** UI moderna. FastAPI backend diretto.
- **Contro:** Overkill per single-tenant. Due stack da mantenere.
- **Stima:** 6 settimane

---

## Routing — 6 pagine

```
/                           ← Dashboard
/bandi                      ← Lista bandi (filtrata per progetto corrente)
/bandi/{id}                 ← Scheda bando (read-only + eligibility)
/candidature/{pe_id}        ← Workspace candidatura (write)
/progetti/{id}              ← Profilo progetto (write, 4 tab)
/pipeline                   ← Log scansioni + trigger manuale
```

**Regola:** ViewBando `/bandi/{id}` = scheda informativa. Workspace `/candidature/{pe_id}` = spazio operativo. Sono **pagine separate**, non tab della stessa pagina.

---

## State Machine (7 stati)

Stati in `project_evaluations.stato`.

```
nuovo → idoneo → lavorazione → pronto → inviato
          ↓           ↓
        scartato    scartato
           ↓
        archiviato (da qualsiasi stato scaduto)
```

### Azioni per stato (ViewBando — header)

| Stato | CTA primaria | Azioni secondarie |
|-------|-------------|-------------------|
| `nuovo` | — | Ri-valuta |
| `idoneo` | Avvia lavorazione ▶ (success) | Scarta ▾ (danger) · Ri-valuta |
| `lavorazione` | Segna pronto (success) | Torna a Idoneo · Scarta ▾ |
| `pronto` | Segna inviato (modale: data+protocollo) | Torna a Lavorazione |
| `inviato` | — (read-only) | Archivia |
| `scartato` | Ripristina (→ idoneo) | Archivia |
| `archiviato` | Ripristina (→ idoneo) | — |

### Regole azioni
- **Scarta**: richiede conferma + campo `motivo_scarto` opzionale
- **Segna inviato**: modale con `data_invio` (required) + `protocollo_ricevuto`
- **Ri-valuta**: trigger `rivaluta_singolo(pe_id)` in background + toast
- **Azioni sempre in header** — mai in fondo alla pagina (fix critico vs Streamlit)

---

## Lista Bandi — Requisiti Query

```sql
SELECT pe.*, b.*
FROM project_evaluations pe
JOIN bandi b ON pe.bando_id = b.id
WHERE pe.project_id = :current_project_id
  AND pe.stato != 'archiviato'        -- default
  AND b.data_scadenza >= NOW()        -- "solo aperti" default attivo

ORDER BY pe.score DESC NULLS LAST
```

### Colonne (ordine definitivo)

1. **Titolo** — searchable, wrap
2. **Ente**
3. **Score** — colorato: verde ≥60 / arancio 40-59 / rosso <40 / `—` se null (mai `0`)
4. **Budget** — `COALESCE(importo_max, budget_totale)` — `—` se null
5. **Scadenza** — data + "Ngg rimasti" come description
6. **Tipo finanziamento** — badge colorato
7. **Stato** — badge con colore da enum

### Filtri

| Filtro | Default |
|--------|---------|
| Solo aperti (toggle visibile) | ✅ ON |
| Nascondi archiviati | ✅ ON |
| Stato (multi-select) | tutti |
| Tipo finanziamento | tutti |
| Score minimo | 0 |
| Scadenza entro N gg (7/14/30) | — |
| Portale | tutti |
| Ricerca testo (titolo + ente) | — |

### Empty state (quando filtro "Solo aperti" ON, 0 risultati)

```
Nessun bando attivo al momento per [Progetto].
💡 Ultimo bando compatibile scaduto il [data] ([N]gg fa).
   Avvia una scansione per cercare nuovi bandi.

[▶ Avvia scansione]   [📂 Vedi storico bandi]
```

"Vedi storico bandi" rimuove il filtro "solo aperti" senza ricaricare pagina.

### Bulk actions

- "Archivia scaduti selezionati"
- "Ri-valuta selezionati" → trigger `rivaluta_singolo` per ciascuno

---

## ViewBando (/bandi/{id})

```
[← Lista]  TITOLO BANDO              [Avvia lavorazione ▶]  [Scarta ▾]
           ENTE · scade DATA (Ngg)  🔴 Ngg se ≤ 14gg
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Decision strip: Idoneità | Score/100 | Scadenza | Tipo | Budget | Hard stop
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tab: [Decisione 60s] [Dettaglio] [Valutazione] [Testo & Metadati]
```

Se stato = lavorazione/pronto: **banner** `📁 Workspace aperto → [apri]` con link a `/candidature/{pe_id}`.

### Tab 4 — state-dependent

| Stato | Nome tab | Contenuto |
|-------|----------|-----------|
| `nuovo`/`idoneo`/`scartato` | Testo & Metadati | criteri_valutazione · raw_text (accordion) · metadata JSON |
| `lavorazione`/`pronto` | Documenti & Invio | checklist documenti · [Genera mancanti] · form invio |
| `inviato` | Esito & Archivio | data invio · protocollo · esito · note esito |

### Tab "Decisione 60s" — struttura

```
✅ PRO (da score_breakdown dove matched=True)   ❌ CONTRO (gap_analysis + yellow_flags)

Gap da coprire prima di candidarsi:
  [lista gap con azione suggerita per ognuno]
```

**Nessuna API call** — derivato meccanicamente da JSONB esistenti.

---

## Storico / Archivio

**Solo bandi toccati** = stato ≠ `nuovo`. Chi ha stato `nuovo` non è mai stato aperto/valutato e **non appare nello storico**. I bandi mai aperti vengono auto-archiviati o nascosti dopo scadenza.

Lo storico mostra solo bandi su cui è stata fatta un'azione esplicita (idoneo, scartato, lavorazione, pronto, inviato).

Bandi archiviati: visualizzati con opacity ridotta. Accessibili tramite:
1. "Vedi storico" nell'empty state
2. Toggle "Mostra archiviati" nella lista
3. Dashboard widget "Scaduti recentemente"

---

## Dashboard — Widget Queries

```sql
-- Idonei in attesa
SELECT COUNT(*) FROM project_evaluations WHERE project_id = :pid AND stato = 'idoneo';

-- Scadono in 14gg
SELECT COUNT(*) FROM project_evaluations pe JOIN bandi b ON pe.bando_id = b.id
WHERE pe.project_id = :pid AND pe.stato IN ('idoneo', 'lavorazione')
  AND b.data_scadenza BETWEEN NOW() AND NOW() + INTERVAL '14 days';

-- In lavorazione
SELECT COUNT(*) FROM project_evaluations WHERE project_id = :pid AND stato = 'lavorazione';

-- Ultima scansione
SELECT started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 1;

-- Scadenze imminenti (widget tabella)
SELECT pe.score, pe.stato, b.titolo, b.data_scadenza, b.ente_erogatore,
       (b.data_scadenza - NOW()::date) as giorni_rimasti
FROM project_evaluations pe JOIN bandi b ON pe.bando_id = b.id
WHERE pe.project_id = :pid AND pe.stato IN ('idoneo', 'lavorazione')
  AND b.data_scadenza <= NOW() + INTERVAL '30 days'
ORDER BY b.data_scadenza ASC;
```

---

## Sessione / Progetto Corrente

- `current_project_id` (int) mantenuto in sessione
- Default: project_id = 1 (La Monica Luciano)
- Ogni query su `project_evaluations` filtrata per `project_id = current_project_id`
- Topbar: dropdown per switcher progetto
- Cambio progetto: `current_project_id` aggiornato, si rimane sulla stessa sezione

---

## Trigger Python

L'UI avvia processi Python in background:

1. **Scansione portali:** `engine/pipeline/flows.py --scan`
2. **Ri-valuta singolo:** `rivaluta_singolo(pe_id)` da `flows.py`
3. **Ri-valuta progetto:** `rivaluta_progetto(project_id)` da `flows.py`
4. **Genera documenti:** `build_package(project_evaluation_id)` da `package_builder.py`

**Stack Python-native (Opzione A/C):** import diretto, nessun bridge.
**Stack non-Python (Opzione B/D):** shell exec con timeout/log, oppure HTTP call a Prefect API.

---

## Soggetti UI — Opzioni di implementazione

**Decisione 2026-03-19:** mostrare i dati del soggetto (forma giuridica, regime fiscale, ATECO, hard stops attivi, vantaggi) nell'interfaccia.

### Opzione A — Pagina dedicata `/soggetti/{id}/` `[PREFERITA — sprint futuro]`

Pagina separata con form per editare il profilo soggetto (P.IVA, regime, dipendenti, ecc.).

**Routing:**
```
/soggetti/{id}/          ← Profilo soggetto (read + write)
/soggetti/{id}/hard-stops/   ← Hard stops attivi/verificati
```

**Pro:** separazione netta soggetto/progetto, coerente con l'architettura dati.
**Quando:** Sprint 3 o 4, dopo il workspace candidatura.
**Note:** Inserire nel piano di progetto, coordinare con migration Python per aggiungere eventuale form di creazione soggetto.

### Opzione B — Sezione nel ProgettoDetail `[IMPLEMENTATA — sprint 1]`

Sezione read-only nel tab "Profilo & Completezza" di `/progetti/{id}/` che mostra i dati del soggetto associato (`projects.soggetto_id → soggetti`).

**Contenuto sezione (read-only dalla UI):**
```
SOGGETTO APPLICANTE
  Nominativo: La Monica Luciano
  Forma giuridica: impresa individuale
  Regime fiscale: forfettario
  Dipendenti: 0
  ATECO: 62.20.10

Hard stops attivi:
  ❌ SRL obbligatoria richiesta
  ❌ Fatturato minimo 50k
  ❌ SOA obbligatoria

Vantaggi attivi:
  ✅ ZES Sicilia
  ✅ Under 35 (Agevolazioni)
  ✅ ATECO digitale 62.20
```

**Note:** solo display, nessun form di modifica — il soggetto è managed dall'engine Python.

---

## Autenticazione

Single user. Email/password. Session-based. Nessun OAuth.
Utente: `luciano@toolbandi.local`

---

## Verifiche End-to-End (Sprint 5 QA)

1. Login → lista bandi: filtro "Solo aperti" attivo di default
2. 0 risultati → empty state con CTA "Vedi storico"
3. "Vedi storico" → rimuove filtro senza full reload
4. Project switcher → switch PDS → lista mostra evaluations project_id=2
5. Click bando idoneo → CTA "Avvia lavorazione" visibile in header (no scroll)
6. "Avvia lavorazione" → modale → conferma → stato lavorazione → tab4 = "Documenti & Invio"
7. "Scarta" → modale con motivo → aggiornato → toast
8. Bando scadenza ≤ 14gg → badge rosso visibile in ViewBando
9. "Avvia scansione" → Python background (`ps aux | grep python` verifica)
10. Dashboard → stat cards aggiornate → ScadenzeImminenti mostra idonei/lavorazione
11. Navigazione "Progetti" → ViewProject → Gap Analysis Aggregata
12. "Ri-valuta tutti" → Python rivaluta_progetto → toast avviato
