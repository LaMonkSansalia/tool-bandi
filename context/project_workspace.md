# Project Workspace & Profilo Progetto — Specifiche

**Version:** 1.0.0
**Date:** 2026-03-19
**Scope:** Workspace candidatura + Profilo progetto come fonte di verità

---

## Due Livelli di "Costruzione del Bando"

### 1. Profilo Progetto (fonte di verità — per-progetto)
Dati **fissi** del progetto che alimentano Claude per generare documenti.
Salvato in `projects.profilo` JSONB.
**Non cambia da bando a bando.**

Contenuto: descrizione estesa, obiettivi, target, partner previsti, budget investimento,
punti di forza, referenze simili, keywords e scoring rules proprie.

### 2. Workspace Candidatura (per-bando × per-progetto)
Dati **specifici** di QUESTO bando × QUESTO progetto.
Salvato in `project_evaluations` (campi `workspace_*`).
**Separato per ogni candidatura.**

Contenuto: note strategiche specifiche al bando, checklist requisiti, documenti generati,
gap da risolvere, stato avanzamento.

---

## Profilo Progetto — Pagina `/progetti/{id}`

### Struttura Pagina

```
[← Progetti]  🌟 NOME PROGETTO    [Modifica]  [Aggiorna scoring]  [Ri-valuta tutti ▶]
  Soggetto: SOGGETTO · settore · ⚠️ "Non ancora costituita" se profilo.costituita = false

  Completezza profilo  ████████░░  65%

Tab: [Profilo & Completezza] [Gap Analysis Aggregata] [Scoring Rules] [Decisioni Strutturali]
```

**Banner "non ancora costituita":** appare nel ProgettoDetail quando `profilo.costituita = false`.
NON appare nella lista bandi (troppo invasivo).

---

### Tab Profilo & Completezza — Form 7 Sezioni

#### Sezione 1: Identità
- Descrizione breve (max 140 car — usata in notifiche Telegram)
- Settore principale (dropdown)
- Keywords scoring (tag list)
- Comuni target (tag list)
- Zone speciali (auto-rilevate: ZES, area_interna, borgo_<5000)
- Costituita (toggle + avviso se false)

#### Sezione 2: Descrizione
- Descrizione estesa (rich text, **min 500 parole**)
- Contatore: N / 500 parole ⚠️ (alimenta proposta tecnica Claude)

#### Sezione 3: Aspetti Economici
- Budget investimento previsto: Da €____ A €____
- Capacità cofinanziamento: ____% · Fonte [dropdown: autofinanziam./partner privato/comune/EU]

#### Sezione 4: Partner Previsti
- Lista dinamica: `[{nome, tipo: pubblico/privato/assoc, ruolo, lettera_intento: sì/no}]`
- [+ Aggiungi partner]

#### Sezione 5: Piano di Lavoro / Fasi
- Lista fasi: `[{fase, inizio (YYYY-MM), fine (YYYY-MM), descrizione}]`
- [+ Aggiungi fase]

#### Sezione 6: KPI e Risultati Attesi
- Lista KPI: `[{nome, valore, unita}]`
- [+ Aggiungi KPI]
- **Nota:** questi KPI vengono mappati automaticamente con i criteri_valutazione dei bandi dal `content_generator.py`

#### Sezione 7: Punti di Forza
- Innovatività: [textarea]
- Impatto sociale/economico: [textarea]
- Sostenibilità del progetto: [textarea]
- Referenze e benchmark (progetti simili altrove): [textarea]

#### Sezione 8: Documenti di Supporto
- Piano di fattibilità: [upload PDF] ← allegato a proposta tecnica
- Studio di mercato: [upload PDF]
- Planimetrie / rendering: [upload PDF]
- Altro: [upload PDF] [+ aggiungi]

---

### Schema JSONB `projects.profilo`

```json
{
  "descrizione_breve": "...",
  "descrizione_estesa": "...",
  "settore": "turismo_astronomia",
  "keywords": ["turismo", "astronomia", "borghi", "aree_interne"],
  "comuni_target": ["Geraci Siculo"],
  "zone_speciali": ["ZES", "area_interna", "borgo_meno_5000"],
  "costituita": false,
  "budget_min": 100000,
  "budget_max": 500000,
  "cofinanziamento_pct": 30,
  "cofinanziamento_fonte": "partner_privato",
  "partner": [
    {
      "nome": "Comune di Geraci Siculo",
      "tipo": "pubblico",
      "ruolo": "ospitante",
      "lettera_intento": false
    }
  ],
  "piano_lavoro": [
    {"fase": "Progettazione", "inizio": "2026-09", "fine": "2026-12", "descrizione": "..."},
    {"fase": "Realizzazione", "inizio": "2027-01", "fine": "2027-06", "descrizione": "..."}
  ],
  "kpi": [
    {"nome": "Visitatori annui", "valore": 200, "unita": "persone/anno"},
    {"nome": "Posti lavoro creati", "valore": 5, "unita": "FTE"}
  ],
  "punti_di_forza": {
    "innovativita": "...",
    "impatto_sociale": "...",
    "sostenibilita": "...",
    "referenze_simili": "..."
  },
  "documenti_supporto": [
    {"tipo": "piano_fattibilita", "filename": "piano_fattibilita.pdf", "path": "..."}
  ],
  "avvio_previsto": "2026-09-01",
  "durata_mesi": 24
}
```

---

### Checklist Completezza (12 item, aggiornata real-time)

```
✅ Descrizione breve
✅ Settore + keywords (min 3)
✅ Comuni target (min 1)
⚠️  Descrizione estesa (147/500 parole)
✅ Budget previsto
✅ Capacità cofinanziamento
✅ Almeno 1 partner
⚠️  Lettere d'intento (0/1)
✗  Piano di lavoro (min 2 fasi)
✗  KPI definiti (min 2)
✗  Almeno 1 documento di supporto
✗  Referenze simili

SOGGETTO APPLICANTE (read-only da tabella soggetti):
  Forma giuridica: impresa individuale
  Regime: forfettario
  Dipendenti: 0
  Hard stops attivi: SRL obbligatoria · fatturato min · SOA
  Vantaggi attivi: ZES Sicilia · Under 35 · ATECO 62.20
```

---

### Tab Gap Analysis Aggregata

Aggrega `gap_analysis` JSONB da tutte le valutazioni storiche del progetto (stato ≠ `nuovo`).

```sql
SELECT
    gap->>'tipo' as tipo,
    gap->>'categoria' as categoria,
    gap->>'suggerimento' as suggerimento,
    COUNT(*) as bandi_impattati
FROM project_evaluations pe,
     jsonb_array_elements(pe.gap_analysis) as gap
WHERE pe.project_id = :project_id
  AND pe.stato != 'nuovo'
  AND pe.gap_analysis IS NOT NULL
GROUP BY tipo, categoria, suggerimento
ORDER BY bandi_impattati DESC;
```

**Visualizzazione:**
```
Aggregato da N valutazioni storiche (solo bandi toccati, stato ≠ nuovo):

  1. Forma giuridica: SRL o APS richiesta ────── 34 bandi  [Critico]
     → Se costituisci SRL sblocchi 34 bandi
  2. Cofinanziamento privato ≥ 30% ──────────── 22 bandi  [Medio]
  3. Fatturato minimo 50-100k ────────────────── 18 bandi  [Critico]
  4. Sede operativa nel comune beneficiario ───── 14 bandi  [Risolvibile]
```

### Tab Scoring Rules

- Editor JSONB `scoring_rules` (textarea JSON con validazione)
- [Salva] → aggiorna `projects.scoring_rules`
- [Ri-valuta tutti ▶] → trigger `rivaluta_progetto(project_id)` + toast "Ri-valutazione avviata"

### Tab Decisioni Strutturali

Log decisioni strategiche del progetto (tabella `project_decisions`).
Suggerimenti auto generati dal gap analysis aggregato.
Form aggiunta nuova decisione.

---

## Workspace Candidatura — Pagina `/candidature/{pe_id}`

Creato quando l'utente clicca "Avvia lavorazione" da ViewBando.
Redirect automatico a `/candidature/{pe_id}` dopo conferma.

### Struttura Pagina

```
[← Lista Bandi]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁  TITOLO BANDO
    ENTE · STATO badge · Scade DATA (Ngg)
    🌟 PROGETTO · Soggetto: SOGGETTO

    Progresso  ████░░░░░░  N/total step completati

    [Segna pronto →]  [Genera documenti ▶]  [Scarta ▾]  [← Scheda bando]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tab: [Overview] [Requisiti & Checklist] [Documenti] [Note & Decisioni]
```

---

### Tab Overview

```
Decision strip mini: Score | Budget | Scadenza | Tipo FP

Gap da risolvere (da gap_analysis JSONB):
  ⚠️ Cofinanziamento 30% richiesto — [aggiungi nota]
  ⚠️ Forma giuridica APS/SRL — [aggiungi nota]
  ❌ Piano progettuale 2026-2028 — [aggiungi nota]

Profilo progetto [PROGETTO] — completezza: 65%  ⚠️
  Budget previsto: non inserito
  Partner: non inseriti
  [Vai al profilo progetto →]
```

---

### Tab Requisiti & Checklist

Inizializzata da `bando_requisiti` (tipo `auto`) quando si avvia lavorazione.
Salvata in `project_evaluations.workspace_checklist` JSONB.

```
Checklist candidatura:

  [✅] Soggetto italiano
  [✅] Settore turismo/cultura
  [⚠️] Forma giuridica: APS o SRL  → Note: [_____________]
  [⚠️] Cofinanziamento 30%         → Note: [_____________]
  [❌] Piano progettuale 2026-2028 → Note: [_____________]
  [  ] Visura camerale allegata    → Note: [_____________]
  [  ] Firma digitale disponibile  → Note: [_____________]

  [+ Aggiungi requisito manuale]

  Completamento: 2/8 ████░░░░░░
```

**Schema `workspace_checklist` JSONB:**
```json
[
  {"id": "uuid", "label": "Soggetto italiano", "completato": true, "nota": "", "tipo": "auto"},
  {"id": "uuid", "label": "Forma giuridica APS o SRL", "completato": false, "nota": "...", "tipo": "auto"},
  {"id": "uuid", "label": "Firma digitale", "completato": false, "nota": "", "tipo": "manuale"}
]
```

`workspace_completezza` (INT 0-100) aggiornato in DB ad ogni cambio checkbox.

---

### Tab Documenti

```
[▶ Genera documenti]  ← triggera Python: content_generator → fact_checker → pdf_generator → package_builder

Lista documenti:
  📄 02_proposta_tecnica_v2.pdf  [BOZZA]  18 mar  [Anteprima ▾] [Scarica] [Approva]
  📄 03_dichiarazione_v1.pdf     [BOZZA]  18 mar  [Anteprima ▾] [Scarica] [Approva]
  📄 05_cv_impresa_v1.pdf        [AUTO]   18 mar  [Anteprima ▾] [Scarica]

  Anteprima inline: [iframe PDF o base64 viewer]

  [Scarica tutto ZIP]
```

**Versionamento:** rigenerazione crea `_v2`, versione precedente resta accessibile.
**Aggiornamento live:** polling ogni 3s (o websocket) mentre generazione in corso.

**Workflow approvazione:**
- [Approva] per ogni documento → `bando_documenti_generati.stato = 'approved'`
- Quando tutti approvati → [Segna pronto →] abilitato

**Invio (quando stato = pronto):**
```
Data invio: ___________  Protocollo: ___________  [Segna come inviato]
```

**Tipi documento generati:**
- `02_proposta_tecnica_v{N}.pdf` — DA FIRMARE
- `03_dichiarazione_v{N}.pdf` — DA FIRMARE
- `04_allegato_a_v{N}.pdf` — DA FIRMARE (se richiesto)
- `05_cv_impresa_v{N}.pdf` — informativo
- `06_visura_camerale.pdf` — da context/documents/

**Stati documento:** `draft` → `approved` → `to-sign` (fisicamente)

---

### Tab Note & Decisioni

```
Note cronologiche (da workspace_notes JSONB):
  [18 mar 12:34] "Cofinanziamento: valutare partnership con Comune Geraci Siculo"
  [textarea → Salva nota]

Decisioni specifiche per questa candidatura:
  (diverse da Decisioni Strutturali del progetto)
  [+ Aggiungi decisione specifica]
```

**Schema `workspace_notes` JSONB:**
```json
[
  {"testo": "...", "created_at": "2026-03-18T12:34:00Z"}
]
```

---

## Generazione Documenti — Flusso

1. UI triggera `build_package(project_evaluation_id)` in background
2. Python legge: `projects.profilo` (dati progetto) + `soggetti.profilo` (anagrafica soggetto) + `bandi` (requisiti, criteri)
3. Pipeline: `content_generator.py` (Claude API) → `fact_checker.py` → `pdf_generator.py`
4. Output in `output/bandi/{YYYYMMDD}_{slug}/`
5. Referenze file salvate in `bando_documenti_generati`
6. Campi "TO FILL MANUALLY" → placeholder visibile nel documento
7. KPI da `projects.profilo.kpi` mappati sui `criteri_valutazione` del bando

---

## DB Extensions Necessarie (migration Python US-002/003)

```sql
-- Campi workspace su project_evaluations
ALTER TABLE project_evaluations ADD COLUMN IF NOT EXISTS
    workspace_checklist   JSONB,
    workspace_notes       JSONB,
    workspace_completezza INT DEFAULT 0;

-- FK soggetto
ALTER TABLE project_evaluations ADD COLUMN IF NOT EXISTS
    soggetto_id INT REFERENCES soggetti(id);

ALTER TABLE projects ADD COLUMN IF NOT EXISTS
    soggetto_id INT REFERENCES soggetti(id);

-- Tabella decisioni strutturali (UI-owned)
CREATE TABLE IF NOT EXISTS project_decisions (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    descrizione         TEXT NOT NULL,
    tipo                TEXT,
    impatto_bandi_count INT DEFAULT 0,
    scadenza            DATE,
    stato               TEXT DEFAULT 'pianificata',
    note                TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```
