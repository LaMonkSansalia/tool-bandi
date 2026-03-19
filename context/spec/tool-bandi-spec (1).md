# Tool Bandi — Specifica UI/UX Completa

## 1. Overview

Applicazione web per ricercare, valutare e candidarsi a bandi pubblici italiani (finanziamenti, contributi, agevolazioni). Multi-soggetto, multi-progetto, multi-candidatura.

**Utente tipo**: consulente/imprenditore italiano che gestisce progetti propri e di clienti, cerca bandi compatibili, prepara candidature.

**Lingua UI**: italiano.
**Target device**: desktop-first (MacBook), responsive.
**Dark mode**: non richiesto.

---

## 2. Modello Dati — 3 Entità + 2 Derivate

### 2.1 SOGGETTO (chi si candida)

Entità giuridica che presenta la domanda. Determina i **vincoli di ammissibilità** (hard stop).
Può essere reale o simulazione (per testare "cosa cambia se apro SRL?").

**Campi:**
- `id`, `nome` (es: "La Monica Luciano")
- `tipo`: "reale" | "simulazione"
- `simulazione_di`: FK → soggetto reale (se tipo = simulazione)
- `forma_giuridica`: enum (impresa individuale, SRL, SRL unipersonale, SPA, APS, cooperativa, associazione, consorzio)
- `regime_fiscale`: enum (forfettario, ordinario, semplificato)
- `partita_iva`: string
- `codice_ateco`: string (es: "62.20.10")
- `numero_dipendenti`: int
- `fatturato_max`: decimal
- `sede_regione`: string
- `sede_comune`: string
- `zona_zes`: boolean
- `zona_mezzogiorno`: boolean (auto-derivato da regione)
- `under_35`: boolean
- `anno_costituzione`: int | null
- `attestazione_soa`: boolean
- `completezza`: int (0-100, calcolato)
- `created_at`, `updated_at`

**Relazioni derivate (calcolate, non FK):**
- `hard_stops`: lista di vincoli attivi con conteggio bandi bloccati
- `vantaggi`: lista di bonus attivi con impatto scoring
- `progetti`: lista progetti associati (via progetti.soggetto_id)

### 2.2 PROGETTO (per cosa ci si candida)

L'idea/iniziativa per cui si cerca finanziamento. Determina il **punteggio di compatibilità** (scoring).
Ha un soggetto di default ma è flessibile (nella candidatura si può scegliere un soggetto diverso).

**Campi:**
- `id`, `nome` (es: "Paese Delle Stelle")
- `soggetto_id`: FK → soggetto (default)
- `descrizione_breve`: string (max 140 car.)
- `descrizione_estesa`: text (target min 500 parole)
- `settore`: enum (turismo, ICT, cultura, agricoltura, manifattura, sociale, energia, altro)
- `keywords`: string[] (per scoring)
- `comuni_target`: string[]
- `zone_speciali`: string[] (ZES, area interna, borgo < 5000 ab., etc.)
- `costituita`: boolean — se false, mostrare avviso
- `budget_min`: decimal
- `budget_max`: decimal
- `cofinanziamento_percentuale`: int (0-100)
- `cofinanziamento_fonte`: string
- `partner`: jsonb — [{nome, tipo: pubblico/privato, ruolo, lettera_intento: bool}]
- `piano_lavoro`: jsonb — [{fase, inizio, fine, descrizione}]
- `kpi`: jsonb — [{nome, valore, unità}]
- `punti_forza`: jsonb — {innovatività, impatto_sociale, sostenibilità, referenze}
- `scoring_rules`: jsonb — regole che determinano il punteggio (editabili)
- `documenti`: file[] — PDF di supporto
- `completezza`: int (0-100, calcolato da checklist)
- `created_at`, `updated_at`

**Checklist completezza (12 item):**
1. Descrizione breve (presente e ≥ 50 car.)
2. Settore (selezionato)
3. Keywords (almeno 3)
4. Comuni target (almeno 1)
5. Costituita (valorizzato)
6. Descrizione estesa (≥ 500 parole)
7. Budget (min e max valorizzati)
8. Cofinanziamento (% e fonte)
9. Partner previsti (almeno 1)
10. Piano di lavoro (almeno 2 fasi)
11. KPI (almeno 2)
12. Punti di forza (almeno 2 sezioni compilate)

### 2.3 BANDO (opportunità di finanziamento)

Scrapato automaticamente dai portali governativi, analizzato con AI.
Entità indipendente, non legata a soggetto o progetto.

**Campi:**
- `id`, `titolo`
- `ente`: string (es: "Invitalia", "Regione Sicilia", "MIMIT")
- `portale`: string (fonte scraping)
- `data_pubblicazione`: date
- `data_scadenza`: date
- `giorni_rimasti`: int (calcolato)
- `budget_totale`: decimal
- `budget_label`: string (es: "€1.5M")
- `tipo_finanziamento`: enum (fondo_perduto, prestito_agevolato, credito_imposta, voucher, mix)
- `percentuale_finanziamento`: string (es: "70%", "80% + 20% prestito")
- `stato_bando`: enum (aperto, chiuso, in_valutazione)
- `url_fonte`: string
- `testo_estratto`: text (dal PDF)
- `criteri_valutazione`: jsonb
- `requisiti_ammissibilita`: jsonb
- `metadata_estrazione`: jsonb — {data_analisi, modello_ai, confidence}
- `created_at`, `updated_at`

### 2.4 VALUTAZIONE (bando × progetto — automatica)

Generata automaticamente dal sistema quando un bando viene scansionato per un progetto.
Contiene score, idoneità, gap analysis.

**Campi:**
- `id`
- `bando_id`: FK → bando
- `progetto_id`: FK → progetto
- `soggetto_id`: FK → soggetto (derivato da progetto.soggetto_id al momento della valutazione)
- `score`: int (0-100) | null
- `idoneo`: boolean
- `hard_stops`: jsonb — [{label, motivo, fonte: "soggetto"|"progetto"}]
- `score_breakdown`: jsonb — [{criterio, punti, max, matched: bool}]
- `gap_analysis`: jsonb — [{label, gravità: critico|medio|risolvibile, fonte: "soggetto"|"progetto", azione_suggerita}]
- `pro`: jsonb — [{label, punti}]
- `contro`: jsonb — [{label, tipo: "gap"|"yellow"|"hard_stop"}]
- `yellow_flags`: jsonb — [{label, dettaglio}]
- `created_at`

**NOTA**: La valutazione è READ-ONLY. Non si modifica manualmente. Si rigenera quando cambiano progetto, soggetto o scoring rules.

### 2.5 CANDIDATURA (bando + progetto + soggetto — operativa)

Workspace operativo creato dall'utente quando decide di candidarsi. Entità autonoma.
Il soggetto si sceglie alla creazione ed è fisso (per testare altro soggetto → nuova candidatura).

**Campi:**
- `id`
- `bando_id`: FK → bando
- `progetto_id`: FK → progetto
- `soggetto_id`: FK → soggetto (scelto alla creazione, può differire dal default del progetto)
- `valutazione_id`: FK → valutazione (snapshot al momento creazione)
- `stato`: enum (vedi §3.1)
- `checklist`: jsonb — [{label, completato: bool, nota: string, auto_generated: bool}]
- `documenti`: jsonb — [{nome, tipo, versione, stato: bozza|approvato|da_firmare, file_path, created_at}]
- `note`: jsonb — [{testo, timestamp, tipo: nota|decisione}]
- `data_invio`: date | null
- `protocollo_invio`: string | null
- `esito`: enum (null, finanziata, respinta, lista_attesa) | null
- `progresso`: int (0-100, calcolato da checklist)
- `created_at`, `updated_at`

---

## 3. Stati e Badge

### 3.1 Stati candidatura
| Stato | Badge colore | Descrizione |
|-------|-------------|-------------|
| bozza | grigio | Appena creata, non ancora lavorata |
| lavorazione | blu | Utente sta preparando attivamente |
| sospesa | giallo | Parcheggiata temporaneamente |
| pronta | viola | Documenti pronti, in attesa invio |
| inviata | oro | Inviata, in attesa esito |
| abbandonata | rosso chiaro | Utente ha deciso di non procedere |

### 3.2 Tipo finanziamento
| Tipo | Badge colore | Label |
|------|-------------|-------|
| fondo_perduto | verde | Fondo perduto |
| prestito_agevolato | giallo | Prestito agevolato |
| credito_imposta | blu | Credito d'imposta |
| voucher | azzurro/cyan | Voucher |
| mix | verde/giallo split | Mix (FP + prestito) |

### 3.3 Score
| Range | Colore | Note |
|-------|--------|------|
| ≥ 60 | verde | Match forte |
| 40-59 | arancione | Match parziale |
| < 40 | rosso | Match debole |
| null | grigio, mostra "—" | Mai mostrare "0" per non-valutato |

### 3.4 Urgenza scadenza
| Giorni rimasti | Indicatore |
|---------------|------------|
| ≤ 7 | 🔴 rosso, badge "URGENTE" |
| 8-14 | 🟠 arancione |
| 15-30 | 🟡 giallo |
| > 30 | nessun indicatore speciale |

---

## 4. Navigazione

### 4.1 Sidebar (sempre visibile)

```
🔍 Tool Bandi          ← logo/titolo app
─────────────────────
📊 Dashboard
👤 Soggetti
🌟 Progetti
📋 Bandi
📁 Candidature
⚙️ Pipeline
```

**Nessun project switcher nella sidebar.** Il contesto progetto/soggetto si sceglie nelle singole pagine dove serve (es: selettore progetto in cima alla lista bandi).

### 4.2 Breadcrumb e navigazione contestuale

Ogni pagina dettaglio ha:
- Freccia ← per tornare alla lista
- Link contestuali verso entità correlate (es: dal workspace candidatura → link a progetto e bando)

---

## 5. Pagine — Specifiche Dettagliate

### 5.1 Dashboard `/`

**Scopo**: Vista trasversale — "cosa succede ora, dove mettere l'attenzione".

**Layout:**

**Riga 1 — 4 stat card:**
| Candidature attive | Scadono in 14gg | Nuovi bandi (ultima scansione) | Ultima scansione (data + esito) |

**Riga 2 — Candidature urgenti (componente principale):**
- Tabella: candidature con scadenza ≤ 30gg, ordinate per giorni rimasti ASC
- Colonne: Bando (link), Progetto (link), Soggetto, Stato (badge), Score (badge), Giorni rimasti (badge urgenza)
- Ogni riga cliccabile → workspace candidatura
- Empty state: "Nessuna scadenza imminente. Buone notizie! 🎉"

**Riga 3 — 2 colonne:**

Colonna SX:
- **Candidature per stato**: conteggi con badge colorati, cliccabili (filtrano lista candidature)
  - Bozza: N | Lavorazione: N | Sospesa: N | Pronta: N | Inviata: N
- **Nuovi bandi**: ultimi N bandi trovati (titolo, ente, scadenza). Link "Vedi tutti →"

Colonna DX:
- **Progetti incompleti**: lista progetti con completezza < 100%, barra progresso, link diretto
- **Hard stop più impattanti** (trasversale tutti i soggetti):
  - "SRL obbligatoria → 34 bandi bloccati (La Monica P.IVA)"
  - "Fatturato min → 18 bandi bloccati (La Monica P.IVA)"
  - Ordinati per bandi bloccati DESC

**Riga 4 — Timeline attività:**
- Lista cronologica ultime 15-20 attività
- Formato: `[data] [icona tipo] Descrizione — Entità correlata`
- Tipi: scansione completata, candidatura creata, stato cambiato, progetto modificato, documento generato

---

### 5.2 Soggetti `/soggetti/`

**Scopo**: Gestione entità giuridiche (reali + simulazioni).

#### 5.2.1 Lista soggetti

**2 tab in alto:** Reali | Simulazioni

**Tab Reali:**
- Tabella sortabile
- Colonne: Nome, Forma giuridica, Regime, P.IVA, Progetti (count, cliccabile), Hard stop (count, badge rosso), Bandi bloccati (totale), Completezza (barra), Ultimo agg.
- Azioni per riga: [Modifica] [Duplica come simulazione]
- Azione globale: [+ Nuovo soggetto]
- Ricerca rapida per nome

**Tab Simulazioni:**
- Stessa tabella ma con colonna aggiuntiva: "Basato su" (link al soggetto reale)
- Badge "Simulazione" su ogni riga
- Azione per riga: [Modifica] [Elimina] [Promuovi a reale]

#### 5.2.2 Dettaglio soggetto `/soggetti/{id}/`

**Header:**
```
[← Soggetti]  NOME SOGGETTO              [Salva] [Duplica come simulazione]
Forma: impresa individuale · Regime: forfettario
Badge: [Simulazione] se tipo = simulazione, con link "Basato su: X"
```

**3 Tab:**

**Tab 1 — "Anagrafica":**
- Form editabile con tutti i campi del soggetto
- Indicatore completezza in alto a destra
- Campi raggruppati:
  - Identità: nome, forma giuridica (dropdown), regime fiscale (dropdown), P.IVA
  - Attività: codice ATECO, numero dipendenti, fatturato max, anno costituzione
  - Sede: regione (dropdown), comune, zona ZES (toggle), zona Mezzogiorno (auto-calcolato, read-only)
  - Requisiti speciali: under 35 (toggle), attestazione SOA (toggle)

**Tab 2 — "Vincoli & Vantaggi":**

Sezione Hard Stop:
- Lista vincoli attivi, ognuno con:
  - ❌ Icona + label (es: "Forma giuridica: impresa individuale")
  - → "N bandi bloccati richiedono [requisito]"
  - → "Azione suggerita: [testo]"
- Ordinati per bandi bloccati DESC
- Se 0 hard stop: messaggio positivo "Nessun vincolo bloccante attivo ✅"

Sezione Vantaggi:
- Lista vantaggi attivi, ognuno con:
  - ✅ Icona + label (es: "Under 35")
  - Dettaglio impatto (es: "Bonus giovani imprenditori — priorità in N bandi")
- Se 0 vantaggi: messaggio "Nessun vantaggio specifico rilevato"

**Tab 3 — "Progetti":**
- Lista progetti associati a questo soggetto (via progetti.soggetto_id)
- Colonne: Nome progetto (link), Settore, Completezza (barra), Candidature attive (count), Ultimo agg.
- Azione: [+ Nuovo progetto per questo soggetto]
- Se 0 progetti: "Nessun progetto associato. [Crea il primo progetto →]"

---

### 5.3 Progetti `/progetti/`

**Scopo**: Gestione progetti/iniziative.

#### 5.3.1 Lista progetti

**Raggruppati per soggetto:**
```
👤 La Monica Luciano (P.IVA) — 2 progetti
├── 🌟 La Monica ICT · ICT · ██░░ 45% · 3 candidature · Score medio: 68
└── 🌟 Paese Delle Stelle · Turismo · ████░ 65% · 1 candidatura · Score medio: 52

👤 [Simulazione] La Monica SRL — 0 progetti
└── Nessun progetto. [Crea progetto →]

👤 Cliente X — 1 progetto
└── 🌟 Progetto Alfa · Manifattura · ███░░ 55% · 0 candidature
```

- Ogni riga progetto cliccabile → dettaglio
- Azione globale: [+ Nuovo progetto]
- Ricerca rapida per nome progetto
- Filtro per soggetto (dropdown)
- Possibilità di collassare/espandere gruppi soggetto

#### 5.3.2 Dettaglio progetto `/progetti/{id}/`

**Header fisso:**
```
[← Progetti]  🌟 NOME PROGETTO                    [Salva] [Avvia scansione ▶]
Soggetto: Nome Soggetto (link) · Settore · Completezza ████░░ 65%
⚠️ "Non ancora costituita" se costituita = false
```

**4 Tab principali:**

**Tab 1 — "Opportunità" (DEFAULT — aperto quando arrivi)**

Stat strip:
| Bandi compatibili | Nuovi questa settimana | Score medio | Prossima scadenza |

Lista bandi match (da valutazioni per questo progetto):
- Colonne: Titolo (link → dettaglio bando con contesto progetto), Ente, Score (badge), Idoneità (✅ o 🔒 + motivo), Budget, Scadenza (+Ngg con badge urgenza), Tipo FP (badge)
- Filtri rapidi: Solo idonei (toggle), Score minimo (slider), Scadenza entro N gg
- Azione per riga: [Crea candidatura] — apre modale scelta soggetto
- Ordinamento default: Score DESC, poi Scadenza ASC
- Empty state: "Nessun bando compatibile trovato. [Avvia scansione ▶] per cercare"

**Riga bando con hard stop (esempio):**
```
🔒 FESR Sicilia — Turismo    Reg. Sicilia    —    🔒 SRL obbligatoria    €500k    42gg    FP 80%
```
L'icona 🔒 e il motivo devono essere immediatamente visibili, non in tooltip.

**Tab 2 — "Candidature"**

Lista candidature attive per questo progetto:
- Colonne: Bando (link → workspace), Soggetto usato, Score (badge), Stato (badge), Scadenza (+Ngg), Progresso (barra)
- Filtri: per stato
- Azione: link diretto al workspace
- Empty state: "Nessuna candidatura attiva. Vai alla tab Opportunità per iniziare."

**Tab 3 — "Profilo"**

Diviso in sezioni base (sempre visibili, stacked) e sezioni avanzate (accordion collapsibile).

Sidebar DX (o strip in alto): checklist completezza live
- 12 item con ✅ / ⚠️ / ✗
- Cliccando un item → scroll alla sezione corrispondente

**Sezioni base (stacked, sempre visibili):**

1. **Identità**
   - Nome progetto (text input)
   - Descrizione breve (textarea, max 140 car., contatore caratteri)
   - Settore (dropdown)
   - Keywords (tag input, aggiunta/rimozione)
   - Comuni target (multi-select o tag input)
   - Zone speciali (multi-select: ZES, area interna, borgo < 5000, etc.)
   - Costituita (toggle sì/no) — se no, warning visibile

2. **Aspetti economici**
   - Budget min (input numerico con €)
   - Budget max (input numerico con €)
   - Cofinanziamento % (slider o input)
   - Fonte cofinanziamento (text input)

3. **Soggetto associato**
   - Dropdown cambio soggetto (con conferma "Vuoi cambiare soggetto default?")
   - Summary read-only del soggetto:
     - Nome, forma giuridica, regime, ATECO, dipendenti
     - Hard stop attivi (lista con badge ❌)
     - Vantaggi attivi (lista con badge ✅)
   - Link: [Vai al soggetto →]

**Sezioni avanzate (accordion, collapsibili):**

4. **Descrizione estesa**
   - Rich text editor o textarea grande
   - Contatore parole live (target: min 500)
   - Warning se < 500 parole

5. **Partner previsti**
   - Lista dinamica con [+ Aggiungi partner]
   - Per ogni partner: nome (text), tipo (dropdown: pubblico/privato), ruolo (text), lettera intento (toggle)
   - [Rimuovi] per ogni item

6. **Piano di lavoro**
   - Lista fasi con [+ Aggiungi fase]
   - Per ogni fase: nome fase (text), data inizio (date picker), data fine (date picker), descrizione (textarea)
   - Visualizzazione timeline opzionale

7. **KPI**
   - Lista con [+ Aggiungi KPI]
   - Per ogni KPI: nome (text), valore target (number), unità (text)

8. **Punti di forza**
   - 4 textarea: Innovatività, Impatto sociale, Sostenibilità, Referenze/esperienza
   - Ognuna con indicatore se compilata

**Sotto-tab dentro Tab 3:**
- "Documenti progetto": upload/gestione file PDF di supporto
- "Scoring rules": editor JSON/YAML delle regole di scoring + [Salva] + checkbox "Ri-valuta tutti i bandi"

**Tab 4 — "Analisi"**

**Sotto-sezione 1 — Gap analysis aggregata:**
- Dati: tutti i gap da tutte le valutazioni di questo progetto
- Lista ordinata per "bandi impattati" DESC:
  ```
  Forma giuridica: SRL richiesta ─── 34 bandi [Critico] ← SOGGETTO
  Cofinanziamento ≥ 30% ──────────── 22 bandi [Medio]   ← PROGETTO
  Fatturato minimo 50-100k ───────── 18 bandi [Critico]  ← SOGGETTO
  Sede operativa nel comune ──────── 14 bandi [Risolvibile] ← PROGETTO
  ```
- Ogni gap ha badge fonte: "SOGGETTO" (arancio) o "PROGETTO" (blu)
- Ogni gap ha badge gravità: Critico (rosso), Medio (arancione), Risolvibile (verde)

**Sotto-sezione 2 — Statistiche:**
- Bandi scansionati totali
- % idonei
- Score medio
- Distribuzione score (mini chart: quanti ≥60, 40-59, <40)

**Sotto-sezione 3 — Timeline/Diario:**
- Cronologia attività relative a questo progetto
- Formato: [data] [azione] [dettaglio]

**Sotto-sezione 4 — Note strategiche:**
- Lista note/decisioni con [+ Aggiungi nota]
- Per ogni nota: testo, data, tipo (nota/decisione/reminder)
- Es: "Costituire SRL per sbloccare 34 bandi — valutare entro Q2 2026"

---

### 5.4 Bandi `/bandi/`

**Scopo**: Lista globale bandi, sfogliabile liberamente o con contesto progetto.

#### 5.4.1 Lista bandi

**Selettore progetto prominente in cima:**
```
┌────────────────────────────────────────────────────────────┐
│ 📋 Bandi                                                   │
│ Valuta per: [Seleziona progetto ▾]  Soggetto: auto (read) │
│ Quando selezionato: score e idoneità visibili per progetto │
└────────────────────────────────────────────────────────────┘
```

Se arrivo dalla tab "Opportunità" di un progetto → il selettore è pre-compilato.
Se arrivo dalla sidebar → il selettore è vuoto (sfoglio libero).

**Colonne tabella (sempre visibili):**
| Titolo | Ente | Score* | Idoneità* | Budget | Scadenza (+Ngg) | Tipo FP | Portale |

*Score e Idoneità:
- Con progetto selezionato: valori dalla valutazione (badge colorato, ✅/🔒)
- Senza progetto: "—" (grigio)

**Filtri (sidebar sinistra o top bar):**
- Solo aperti: toggle, default ON
- Tipo finanziamento: multi-select (FP, prestito, credito imposta, voucher, mix)
- Scadenza entro: dropdown (7gg, 14gg, 30gg, 60gg, 90gg, tutti)
- Score minimo: slider 0-100 (attivo solo con progetto selezionato)
- Portale: multi-select
- Ricerca testo: search box

**Ordinamento default:**
- Con progetto: Score DESC, poi Scadenza ASC
- Senza progetto: Scadenza ASC (prossimi prima)

**Azioni:**
- Ogni riga cliccabile → dettaglio bando (con contesto progetto se selezionato)
- Bulk: [Archivia scaduti]

**Empty state (con filtro "solo aperti"):**
"Nessun bando attivo trovato. [Avvia scansione ▶] [Vedi storico: disattiva filtro 'solo aperti']"

#### 5.4.2 Dettaglio bando `/bandi/{id}/`

**Header fisso:**
```
[← Bandi]  TITOLO BANDO                          [Crea candidatura ▶]
ENTE · Scade 30/04/2026 (42gg) 🔴 se ≤14gg
Contesto: [Progetto: Nome ▾] → Soggetto: Nome (auto)
```

Il selettore progetto è nel header — puoi cambiare contesto senza tornare alla lista.
[Crea candidatura ▶] → modale con scelta soggetto (pre-selezionato dal contesto, ma cambiabile).

**Decision strip (sotto header, sempre visibile):**

Con progetto selezionato (6 colonne):
| Idoneità | Score | Scadenza | Tipo FP | Budget | Vincolo soggetto |
|----------|-------|----------|---------|--------|------------------|
| ✅ Idoneo | 72/100 (verde) | 42gg | FP 70% | €1.5M | — |

Con hard stop:
| ❌ Hard stop | —/100 (grigio) | 42gg | FP 80% | €500k | 🔒 SRL obbligatoria ← La Monica P.IVA |

Senza progetto (4 colonne):
| Scadenza | Tipo FP | Budget | Portale |
| 42gg | FP 80% | €500k | invitalia.it |

**3 Tab:**

**Tab 1 — "Decisione rapida" (visibile SOLO se progetto selezionato)**

Due colonne:
```
✅ PRO                                    ❌ CONTRO
• Regione Sicilia compatibile (+15)       • Cofinanziamento 30% richiesto
• ATECO 62.20 prioritario (+10)           • Business plan triennale mancante
• Under 35 (+8)                           ⚠️ Certificazione ISO non obblig. ma premiante
```

Gap da coprire:
```
⚠️ Cofinanziamento 30% — Verificare partnership [← PROGETTO]
⚠️ Piano di lavoro — Completare nel profilo progetto [← PROGETTO]
❌ Forma giuridica — Serve SRL [← SOGGETTO]
```

CTA grande: [Crea candidatura per "Nome Progetto" →]
Testo sotto: "Soggetto: Nome. [Cambia soggetto]"

**Tab 2 — "Dettaglio bando" (DEFAULT se nessun progetto selezionato)**
- Sezione "Informazioni":
  - Portale, URL fonte (link esterno)
  - Date: pubblicazione, scadenza
  - Budget totale, tipo finanziamento, percentuale
  - Ente erogante
- Sezione "Requisiti ammissibilità" (dal PDF analizzato):
  - Lista requisiti estratti
- Sezione "Criteri valutazione" (dal PDF):
  - Lista criteri con pesi se disponibili

**Tab 3 — "Testo & PDF"**
- Raw text estratto dal PDF (in area scrollabile monospace)
- [Scarica PDF originale] button
- Metadata estrazione: data analisi, modello AI usato, confidence

---

### 5.5 Candidature `/candidature/`

**Scopo**: Vista trasversale tutte le candidature, il "cruscotto operativo".

#### 5.5.1 Lista candidature

**Tabella con filtri:**

Colonne: Bando (link → workspace), Progetto (link), Soggetto, Score (badge), Stato (badge), Scadenza (+Ngg, badge urgenza), Progresso (barra %), Ultimo agg.

**Filtri:**
- Stato: multi-select (bozza, lavorazione, sospesa, pronta, inviata, abbandonata)
- Progetto: dropdown
- Soggetto: dropdown
- Scadenza entro: dropdown (7gg, 14gg, 30gg, tutti)
- Ricerca testo

**Ordinamento default:** Scadenza ASC (più urgenti prima), poi Stato (lavorazione > bozza > pronta > sospesa)

**Azioni per riga:**
- Click → workspace candidatura
- Azioni rapide: [Cambia stato ▾]

**Empty state:** "Nessuna candidatura attiva. Vai su un progetto o un bando per crearne una."

#### 5.5.2 Workspace candidatura `/candidature/{id}/`

**Header fisso:**
```
[← Candidature]
📁 TITOLO BANDO
ENTE · Scade 30/04/2026 (42gg) · Stato: [badge lavorazione]
🌟 Progetto: Nome Progetto (link) · 👤 Soggetto: Nome Soggetto (link)
Score: 72/100 [badge verde] · Tipo: Fondo perduto 70%
Progresso: ████████░░ 6/10 step

[Cambia stato ▾] [← Scheda bando] [← Progetto]
```

Azioni nel [Cambia stato ▾]:
- bozza → "Avvia lavorazione" (→ lavorazione)
- lavorazione → "Segna pronta" (→ pronta) | "Sospendi" (→ sospesa) | "Abbandona" (→ abbandonata)
- sospesa → "Riprendi" (→ lavorazione) | "Abbandona"
- pronta → "Segna inviata" (→ modale: data invio + protocollo → inviata) | "Torna in lavorazione"
- inviata → "Registra esito" (→ modale: finanziata/respinta/lista attesa)
- abbandonata → "Ripristina" (→ bozza)

**4 Tab (in ordine di priorità d'uso):**

**Tab 1 — "Valutazione" (read-only, contesto)**
- Decision strip compatta: Score, Idoneità, Tipo FP, Budget, Scadenza
- Due colonne: PRO / CONTRO
- Gap da coprire (lista con badge fonte e gravità)
- Tutto read-only
- Link in basso: "Vedi valutazione completa → Scheda bando"

**Tab 2 — "Documenti"**

Il tab Documenti gestisce due flussi: documenti generati dall'AI e documenti caricati manualmente.

**Struttura pagina:**

1. **Header sezione:**
   - Progresso documenti: "4/7 documenti pronti" + barra progresso
   - [▶ Genera documenti AI] button prominente
   - [+ Carica documento] button secondario
   - [Scarica pacchetto ZIP] (attivo solo se ≥1 documento approvato)

2. **Lista documenti richiesti:**
   La lista viene pre-popolata dall'analisi del bando (il sistema estrae dal PDF i documenti richiesti).
   L'utente può aggiungere documenti extra manualmente.

   Per ogni documento nella lista:
   ```
   ┌─────────────────────────────────────────────────────────────────┐
   │ 📄 Proposta tecnica              [Generato AI]   v2   ✅ Approvato │
   │    Ultima modifica: 18/03 10:30                                  │
   │    [Modifica] [Anteprima] [Scarica PDF] [Rigenera] [Cronologia]  │
   ├─────────────────────────────────────────────────────────────────┤
   │ 📄 Visura camerale               [Upload]         v1   ⬜ Mancante│
   │    Richiesto dal bando                                           │
   │    [Carica file ↑]                                               │
   ├─────────────────────────────────────────────────────────────────┤
   │ 📄 Dichiarazione sostitutiva     [Generato AI]   v1   📝 Bozza  │
   │    Generato il 17/03 — da revisionare                           │
   │    [Modifica] [Anteprima] [Approva] [Rigenera]                   │
   └─────────────────────────────────────────────────────────────────┘
   ```

   Colonne/info per ogni documento:
   - **Nome** documento
   - **Origine**: badge "Generato AI" (blu) | "Upload" (grigio) | "Richiesto" (arancione, non ancora presente)
   - **Versione**: v1, v2, v3... (ogni modifica/rigenerazione crea nuova versione)
   - **Stato**: badge con colore
     - ⬜ Mancante (grigio) — documento richiesto ma non ancora presente
     - 📝 Bozza (giallo) — generato/caricato, da revisionare
     - 👁️ In revisione (blu) — l'utente sta lavorando
     - ✅ Approvato (verde) — pronto per l'invio
     - ✍️ Da firmare (viola) — approvato ma richiede firma
   - **Azioni** (variano per stato e origine):
     - Generato AI: [Modifica] [Anteprima] [Scarica PDF] [Approva] [Rigenera] [Cronologia versioni]
     - Upload: [Sostituisci] [Anteprima] [Scarica] [Approva] [Rimuovi]
     - Mancante: [Genera AI] (se generabile) | [Carica file ↑]

3. **Modale/pannello "Modifica documento" (editor inline):**
   Quando l'utente clicca [Modifica] su un documento generato AI:
   - Si apre un editor a schermo intero o pannello laterale largo
   - **Lato sinistro**: editor Markdown/testo con toolbar (bold, italic, heading, liste)
   - **Lato destro**: anteprima live del documento formattato
   - In alto: nome documento, versione corrente, stato
   - Azioni: [Salva bozza] [Approva e chiudi] [Annulla] [Rigenera con AI]
   - Il salvataggio crea una nuova versione (v1 → v2)
   - "Rigenera con AI" permette di dare istruzioni aggiuntive: textarea "Istruzioni per la rigenerazione" (es: "Enfatizza di più l'aspetto innovativo", "Aggiungi sezione su sostenibilità")

4. **Modale "Genera documenti AI":**
   Quando l'utente clicca [▶ Genera documenti AI]:
   ```
   Genera documenti per questa candidatura

   Il sistema genererà i seguenti documenti usando i dati del progetto,
   soggetto e criteri del bando:

   ☑️ Proposta tecnica (v2 esistente — verrà creata v3)
   ☑️ Dichiarazione sostitutiva (v1 esistente — verrà creata v2)
   ☑️ CV impresa
   ☑️ Piano finanziario / budget
   ☐ Lettera di intento partner (richiede upload manuale)
   ☐ Visura camerale (richiede upload manuale)

   I documenti non generabili automaticamente sono evidenziati
   e richiedono upload manuale.

   [Annulla] [Genera selezionati →]
   ```
   - I documenti generabili sono pre-selezionati
   - I non-generabili sono disabilitati con nota
   - Se un documento esiste già, la generazione crea una nuova versione
   - Operazione asincrona: mostra progresso ("Generando proposta tecnica... 2/4")

5. **Pannello "Cronologia versioni":**
   Per ogni documento, cliccando [Cronologia]:
   - Lista versioni: v3 (corrente), v2, v1
   - Per ogni versione: data, autore (AI/utente), stato al momento, [Visualizza] [Ripristina]
   - Possibilità di ripristinare una versione precedente (crea nuova versione dal contenuto vecchio)

**Empty state:**
"Nessun documento presente. Il sistema ha identificato N documenti richiesti per questo bando.
[▶ Genera documenti AI] per creare le bozze automatiche, oppure [+ Carica documento] per aggiungere manualmente."

**Schema dati documenti:**
```
documento_candidatura = {
  id: uuid,
  candidatura_id: FK → candidatura,
  nome: string,                    -- "Proposta tecnica"
  categoria: enum,                 -- proposta_tecnica | dichiarazione | cv_impresa | budget |
                                   -- preventivo | visura | lettera_intento | formulario | altro
  origine: enum,                   -- generato_ai | upload_manuale | richiesto_bando
  generabile_ai: boolean,          -- true se il sistema può generarlo
  stato: enum,                     -- mancante | bozza | in_revisione | approvato | da_firmare
  versione_corrente: int,
  contenuto_markdown: text | null, -- contenuto editabile (per doc generati AI)
  file_path: string | null,        -- path file (per upload o PDF esportato)
  formato_output: enum,            -- markdown | pdf | docx
  prompt_generazione: text | null, -- prompt usato per generare (per rigenerazione)
  istruzioni_utente: text | null,  -- istruzioni aggiuntive dell'utente per rigenerazione
  created_at, updated_at
}

versione_documento = {
  id: uuid,
  documento_id: FK → documento_candidatura,
  versione: int,
  contenuto_markdown: text | null,
  file_path: string | null,
  autore: enum,                    -- ai | utente
  nota: string | null,             -- "Rigenerato con focus su innovazione"
  created_at
}
```

**Tab 3 — "Checklist"**
- Lista items (auto-generati da gap analysis + manuali):
  - [checkbox] Label — [campo nota inline]
  - Badge: "auto" se generato dal sistema, nessun badge se manuale
- Progress bar in cima (N/totale completati)
- [+ Aggiungi requisito manuale]
- Ordinamento: incompleti prima, poi completati

**Tab 4 — "Note & Invio"**
- **Sezione Note:**
  - Lista cronologica (newest first)
  - Per ogni nota: testo, timestamp, tipo badge (nota/decisione)
  - [textarea + Salva nota] in cima
- **Sezione Invio (visibile solo se stato = pronta o inviata):**
  - Se pronta: form con data invio (date picker), protocollo (text), note invio (textarea), [Conferma invio →]
  - Se inviata: dati invio read-only + sezione esito
- **Storico stati:**
  - Lista cambi stato con timestamp
  - Es: "19/03 15:30 — bozza → lavorazione", "20/03 10:00 — lavorazione → pronta"

---

### 5.6 Pipeline `/pipeline/`

**Scopo**: Gestione scansioni bandi (backend tecnico). Minimale.

**Layout:**

**Sezione 1 — Stato attuale:**
```
Ultima scansione: 19/03/2026 14:30 · ✅ Completata · Durata: 4m 32s · 12 bandi trovati
[▶ Avvia nuova scansione]
```

Se scansione in corso:
```
🔄 Scansione in corso... Avviata: 19/03 14:30 · Durata finora: 2m 15s
[barra progresso se disponibile]
```

**Sezione 2 — Storico (tabella):**
- Ultime 10-20 scansioni
- Colonne: Data/ora, Stato (✅ success / ❌ failed / 🔄 running), Durata, Bandi trovati, Bandi nuovi, Errori
- Click su riga → espande dettagli (log errori se failed, lista bandi trovati se success)

---

## 6. Modale "Crea candidatura"

Triggered da: [Crea candidatura] su bando (da lista o dettaglio) o su bando match dentro progetto.

**Contenuto modale:**

```
Crea candidatura

Bando: [titolo bando] (read-only, pre-compilato)
Progetto: [dropdown — pre-selezionato se contesto] (obbligatorio)
Soggetto: [dropdown — pre-selezionato da progetto.soggetto_id] (modificabile)

⚠️ Se soggetto diverso dal default: "Attenzione: soggetto diverso dal default del progetto"
🔒 Se soggetto ha hard stop per questo bando: "Questo soggetto ha vincoli bloccanti per questo bando: [lista]. Vuoi procedere comunque?"

[Annulla] [Crea candidatura →]
```

Alla creazione: stato = bozza, checklist auto-generata da gap_analysis, redirect al workspace.

---

## 7. Flussi Utente Principali

### 7.1 Preparazione
1. Dashboard → Soggetti → [+ Nuovo soggetto] → compila anagrafica
2. Progetti → [+ Nuovo progetto] → seleziona soggetto → compila profilo
3. Progetto → Tab Profilo → compilazione sezioni base → avanzate

### 7.2 Discovery (da progetto)
1. Progetti → apri progetto → Tab "Opportunità" (default)
2. Vedi bandi compatibili con score e idoneità
3. Click su bando → Dettaglio bando (con contesto progetto pre-selezionato)
4. Tab "Decisione rapida" → valuta pro/contro/gap
5. [Crea candidatura] → modale → workspace

### 7.3 Discovery (sfoglio libero)
1. Bandi (sidebar) → lista globale senza progetto
2. Sfoglia per tipo, scadenza, budget
3. Trova bando interessante → seleziona progetto nel selettore in cima
4. Score e idoneità appaiono → valuta
5. Click → Dettaglio bando → Tab "Decisione rapida"
6. [Crea candidatura] → modale → workspace

### 7.4 Candidatura
1. Workspace candidatura → Tab "Valutazione" (capire il match)
2. Tab "Checklist" → vedere cosa manca
3. Tab "Documenti" → [Genera documenti] → revisiona → approva
4. [Cambia stato → Pronta]
5. Tab "Note & Invio" → compila dati invio → [Conferma invio]

### 7.5 Monitoraggio
1. Dashboard → vedi urgenze, scadenze, stati
2. Candidature (sidebar) → lista trasversale filtrata per stato/scadenza
3. Click su candidatura → workspace

### 7.6 Simulazione soggetto
1. Soggetti → trova soggetto reale → [Duplica come simulazione]
2. Modifica forma giuridica (es: P.IVA → SRL)
3. Salva → i hard stop si ricalcolano
4. Vai su Progetto → Tab Profilo → cambia soggetto default alla simulazione
5. Tab Opportunità → vedi nuovi bandi sbloccati
6. Oppure: Crea candidatura con soggetto simulato su bando prima bloccato

### 7.7 Gestione clienti
1. Soggetti → [+ Nuovo soggetto] per ogni cliente
2. Progetti → [+ Nuovo progetto] → associa al soggetto cliente
3. Stessi flussi di discovery e candidatura, ma per soggetti diversi
4. Dashboard → vista trasversale di tutti i clienti

---

## 8. Regole UI Trasversali

### 8.1 Badge e colori
- Usare badge colorati coerenti per stati, score, tipo FP (vedi §3)
- Mai mostrare "0" per score non valutato → mostrare "—"
- Hard stop sempre con ❌ rosso + motivo visibile (non in tooltip)
- Vantaggi sempre con ✅ verde

### 8.2 Azioni contestuali
- Le azioni principali (CTA) sono sempre nel header o in posizione prominente
- Le azioni distruttive (elimina, abbandona) richiedono conferma modale
- Le azioni di cambio stato sono in un dropdown [Cambia stato ▾]

### 8.3 Empty state
- Ogni lista/tabella ha un empty state con messaggio utile + CTA per la prossima azione
- Mai lasciare una vista vuota senza indicazione

### 8.4 Link tra entità
- Ogni menzione di progetto, soggetto, bando, candidatura è un link cliccabile
- La navigazione contestuale (es: dal workspace al bando) preserva il contesto

### 8.5 Responsive
- Desktop-first, ma le tabelle devono avere scroll orizzontale su schermi piccoli
- Sidebar collassabile su mobile
- Form devono funzionare su tablet

### 8.6 Feedback
- Salvataggio: toast di conferma
- Errori: inline sui campi + toast per errori generali
- Loading: skeleton su tabelle, spinner su azioni

---

## 9. Palette Colori Suggerita

```
Primary:        #2563EB (blu)
Primary hover:  #1D4ED8
Background:     #F8FAFC (grigio chiarissimo)
Surface:        #FFFFFF
Text primary:   #0F172A (quasi nero)
Text secondary: #64748B (grigio)
Border:         #E2E8F0

Score verde:    #16A34A (bg: #DCFCE7)
Score arancio:  #EA580C (bg: #FFF7ED)
Score rosso:    #DC2626 (bg: #FEF2F2)

Stato bozza:    #94A3B8 (grigio, bg: #F1F5F9)
Stato lavoraz.: #2563EB (blu, bg: #EFF6FF)
Stato sospesa:  #EAB308 (giallo, bg: #FEFCE8)
Stato pronta:   #7C3AED (viola, bg: #F5F3FF)
Stato inviata:  #D97706 (oro, bg: #FFFBEB)
Stato abband.:  #F87171 (rosso chiaro, bg: #FEF2F2)

FP verde:       #16A34A
Prestito giallo:#EAB308
Credito blu:    #2563EB
Voucher cyan:   #06B6D4
Mix:            gradient verde→giallo

Hard stop:      #DC2626 (rosso)
Vantaggio:      #16A34A (verde)
Warning:        #F59E0B (ambra)
```

---

## 10. Note per l'Implementazione

- Il backend Python esiste già e gestisce scraping, analisi PDF, valutazione
- La UI è un frontend separato che consuma API REST
- Le valutazioni sono generate dal backend, la UI le mostra read-only
- La generazione documenti è un'operazione asincrona (polling o websocket per stato)
- Le scoring rules sono editabili dall'utente e triggerano ri-valutazione
- La scansione pipeline è asincrona con stato polling
