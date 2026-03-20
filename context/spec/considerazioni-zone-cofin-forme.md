# Considerazioni: Zone Speciali, Cofinanziamento, Forme Giuridiche

**Data:** 2026-03-20
**Aree analizzate:** 3 su 7 dalla prioritizzazione

---

## 1. ZONE SPECIALI — Le 4 opzioni attuali sono incomplete

### Stato attuale nel codice

```python
# web/services/completezza.py (stimato — 4 ZONE_SPECIALI_OPTIONS)
ZONE_SPECIALI_OPTIONS = [
    ('zes', 'ZES Unica Mezzogiorno'),
    ('area_interna', 'Area interna (SNAI)'),
    ('borgo_5000', 'Borgo < 5.000 abitanti'),
    ('isola_minore', 'Isola minore'),
]
```

Campo nel profilo progetto: `zone_speciali[]` (multi-select).
Usato nello scoring: `+10 punti` se zona ZES/area interna.

### Come funzionano realmente le zone speciali nei bandi italiani

Dalla ricerca emergono **6 classificazioni territoriali** usate come criterio di ammissibilita' o premialita':

**A) ZES Unica Mezzogiorno** (dal 2024)
- Comprende le zone assistite di: Basilicata, Calabria, Campania, Molise, Puglia, Sardegna, Sicilia + parti di Abruzzo, Marche, Umbria
- Dal 2026 estesa a 2026-2028 con credito d'imposta confermato
- NON e' solo "stai al Sud" — serve essere nelle **zone assistite** della Carta degli aiuti a finalita' regionale 2022-2027
- Aliquote differenziate per regione E per dimensione impresa (piccola +20%, media +10%)
- **Nel tool:** "ZES" come opzione e' corretto, ma manca la granularita' — un'impresa in Abruzzo potrebbe essere in ZES solo in certi comuni

**B) ZLS — Zone Logistiche Semplificate**
- Diverse dalla ZES! Sono zone portuali/retroportuali del Centro-Nord
- Dal 2026 estese anche al credito d'imposta (prima solo semplificazioni)
- Esempi: Porto di Genova, Venezia, Trieste
- **Nel tool:** MANCANTE — chi opera in ZLS ha agevolazioni simili alla ZES ma non e' ZES

**C) Aree Interne (SNAI)**
- Classificazione SNAI: comuni classificati come "intermedi", "periferici", "ultra-periferici" in base alla distanza dai servizi essenziali (sanita', istruzione, mobilita')
- 60% del territorio nazionale, 52% dei comuni, 22% della popolazione
- Il ciclo 2021-2027 ha aggiornato la Mappa con 124 aree progetto (1.904 comuni)
- **Usato nei bandi come:** premialita' (+5/+10 punti), riserva di risorse, criteri di selezione con priorita'
- **Nel tool:** "Area interna" e' corretto come concetto, ma il matching dovrebbe essere sul COMUNE, non sull'auto-dichiarazione

**D) Comuni sotto soglia demografica**
- NON e' una classificazione ufficiale unica — ogni bando definisce la sua soglia:
  - Resto al Sud 2.0: comuni < 5.000 ab. (premialita')
  - Borghi PNRR M1C3: comuni < 5.000 ab. (ammissibilita')
  - Fondo Comuni Marginali: comuni < 5.000 ab. con indice di vulnerabilita' alto
  - Alcuni bandi regionali: < 3.000, < 10.000, < 15.000
- **Nel tool:** "Borgo < 5.000" e' la soglia piu' comune ma non l'unica

**E) Isole Minori**
- Progetto speciale SNAI per isole minori (CIPESS 2022, rifinanziato 2025)
- Riconosciute come svantaggio strutturale permanente dall'UE
- **Nel tool:** "Isola minore" e' corretto

**F) Cratere sismico / Aree emergenza**
- Comuni del cratere sismico (Centro Italia 2016, Ischia 2017, etc.)
- Spesso hanno premialita' o riserve dedicate nei bandi
- **Nel tool:** MANCANTE

### Proposta: nuove zone speciali allineate alla PA

```python
ZONE_SPECIALI_OPTIONS = [
    ('zes_unica',        'ZES Unica Mezzogiorno'),
    ('zls',              'Zona Logistica Semplificata (ZLS)'),
    ('area_interna',     'Area interna SNAI (intermedia/periferica/ultra-periferica)'),
    ('borgo_5000',       'Comune < 5.000 abitanti'),
    ('isola_minore',     'Isola minore'),
    ('cratere_sismico',  'Cratere sismico / area emergenza'),
]
```

### Considerazione architetturale: zona del PROGETTO o del SOGGETTO?

Attualmente `zone_speciali` e' nel profilo del **progetto**. Ma la zona e' legata alla **sede operativa del soggetto** (o alla sede dell'investimento). Due opzioni:

**Opzione A — Nel soggetto** (raccomandato)
La sede del soggetto determina automaticamente le zone: se la sede e' a Castelbuono (PA), il sistema sa che e' in ZES Unica + area interna SNAI. Se e' a Genova porto, sa che e' in ZLS.

**Opzione B — Nel progetto** (attuale)
Il progetto dichiara dove sara' realizzato l'investimento. Ha senso se il progetto e' in un luogo diverso dalla sede del soggetto (es. apro un B&B in un borgo diverso dalla mia sede legale).

**Raccomandazione:** Mantieni nel progetto (piu' flessibile) ma aggiungi un campo `comune_investimento` che, se compilato, sovrascrive la sede del soggetto per il calcolo delle zone. Il matching ZES/SNAI dovrebbe essere automatico dal codice ISTAT del comune, non dall'auto-dichiarazione.

### Impatto sullo scoring engine

Lo scorer attuale da' `+10` per ZES/area interna indistintamente. In realta':
- ZES: i bandi danno **intensita' di aiuto maggiore** (non solo premialita')
- Area interna SNAI: i bandi danno **premialita' nei criteri di selezione**
- Borgo < 5.000: **ammissibilita'** in alcuni bandi, **premialita'** in altri

Il +10 generico funziona come approssimazione, ma andrebbe differenziato.

### Priorita': MEDIA
Non bloccante per il deploy. La classificazione attuale (4 opzioni) copre i casi principali. ZLS e cratere sismico sono aggiunte utili ma non urgenti. Il matching automatico da codice ISTAT e' un'evoluzione futura.

---

## 2. COFINANZIAMENTO — Le 5 fonti attuali sono incomplete

### Stato attuale nel codice

```python
# web/services/completezza.py (stimato — 5 COFINANZIAMENTO_FONTI)
COFINANZIAMENTO_FONTI = [
    ('mezzi_propri',      'Mezzi propri / autofinanziamento'),
    ('prestito_bancario', 'Prestito bancario'),
    ('leasing',           'Leasing'),
    ('fondo_garanzia',    'Fondo di Garanzia PMI'),
    ('altro',             'Altro'),
]
```

Campo nel profilo: `cofinanziamento_pct` (percentuale) + `cofinanziamento_fonte` (singola selezione).

### Come funziona il cofinanziamento nei bandi reali

I bandi richiedono che l'impresa copra una quota del progetto (tipicamente 10%-70%). Le fonti ammesse variano per bando, ma quelle ricorrenti sono:

**A) Mezzi propri / Autofinanziamento**
- Cassa, utili reinvestiti, patrimonio netto
- Fonte piu' comune e sempre ammessa
- **Nel tool:** presente ✓

**B) Prestito bancario tradizionale**
- Mutuo chirografario o ipotecario
- Spesso richiesto che sia "deliberato" al momento della domanda
- **Nel tool:** presente ✓

**C) Fondo di Garanzia PMI (MCC)**
- NON e' una fonte di cofinanziamento — e' una GARANZIA che facilita l'accesso al credito bancario
- Copre fino all'80% del finanziamento
- Nel 2025: 183.000 operazioni, 34 miliardi di finanziamenti garantiti
- **Nel tool:** presente ma MAL CATEGORIZZATO — il Fondo di Garanzia non e' alternativo al prestito bancario, ne e' un facilitatore

**D) Leasing / Locazione finanziaria**
- Ammesso esplicitamente dalla ZES Unica e da molti bandi per beni strumentali
- Si considera il costo sostenuto dal locatore (non i canoni)
- **Nel tool:** presente ✓

**E) Equity crowdfunding**
- Riconosciuto giuridicamente come aumento di capitale
- Sblocca accesso a bandi che richiedono "cofinanziamento privato": Smart&Start, Simest, Horizon Europe
- In crescita come fonte combinata: equity crowd → credito bancario → bando pubblico
- **Nel tool:** MANCANTE

**F) Venture Capital / Business Angel**
- Investimento in equity da parte di VC, family office, angel investor
- Rilevante per startup innovative (Smart&Start, FNI)
- CDP Venture Capital SGR e' il principale veicolo VC pubblico
- **Nel tool:** MANCANTE

**G) Minibond**
- Emissione obbligazionaria per PMI (tipicamente 1-50M€)
- Usato come fonte complementare in progetti medio-grandi
- **Nel tool:** MANCANTE (marginale per il target attuale)

**H) Contributo altro bando / cumulo**
- Molti bandi permettono il cumulo: il cofinanziamento puo' venire da UN ALTRO bando
- Regole stringenti: non superare l'intensita' massima di aiuto (GBER art. 25)
- Es: ZES Unica + Transizione 5.0 cumulabili dal 2025
- **Nel tool:** MANCANTE ma IMPORTANTE — il cumulo e' una strategia chiave

**I) Fondi propri da campagna reward crowdfunding**
- Meno strutturato dell'equity, ma usato come prova di mercato
- Fondazione CRT ha un bando specifico per matching grant su crowdfunding
- **Nel tool:** MANCANTE (nicchia)

### Proposta: nuove fonti allineate alla realta'

```python
COFINANZIAMENTO_FONTI = [
    ('mezzi_propri',        'Mezzi propri / autofinanziamento'),
    ('prestito_bancario',   'Prestito bancario (mutuo, fido)'),
    ('prestito_agevolato',  'Prestito agevolato (Simest, Microcredito)'),
    ('leasing',             'Leasing / locazione finanziaria'),
    ('equity_crowdfunding', 'Equity crowdfunding'),
    ('venture_capital',     'Venture Capital / Business Angel'),
    ('altro_bando',         'Contributo da altro bando (cumulo)'),
    ('altro',               'Altro'),
]
```

### Cambiamenti strutturali necessari

1. **Multi-select** — Un progetto puo' avere PIU' fonti di cofinanziamento (es. 30% mezzi propri + 20% prestito bancario). Attualmente e' single-select.

2. **Fondo di Garanzia → tag, non fonte** — Il Fondo di Garanzia PMI non e' una fonte di denaro, e' uno strumento che facilita il prestito bancario. Va spostato come checkbox/flag del soggetto ("Ha accesso al Fondo di Garanzia PMI: Si/No") perche' influenza l'hard stop "capacita' di cofinanziamento" ma non e' esso stesso cofinanziamento.

3. **% per fonte** — Idealmente, la somma delle percentuali per fonte = `cofinanziamento_pct` totale. Ma per ora e' overkill — basta il multi-select delle fonti + la percentuale totale.

### Priorita': MEDIA-ALTA
Il multi-select e la rimozione del Fondo di Garanzia dalle fonti sono cambiamenti importanti per la correttezza del profilo. L'aggiunta di equity crowdfunding e venture capital e' rilevante per il target startup innovative.

---

## 3. FORMA GIURIDICA + REGIME FISCALE — Opzioni del dropdown soggetto

### Stato attuale nel codice

Il form soggetto (anagrafica) ha campi per `forma_giuridica` e `regime_fiscale` nel JSONB `profilo`.
I valori disponibili non sono esplicitamente elencati nel transcript come costanti Python — probabilmente sono free-text o hanno un set limitato.

Il soggetto esistente: "La Monica Luciano — P.IVA, impresa individuale, regime forfettario"

### Come i bandi classificano i beneficiari per forma giuridica

I bandi italiani usano queste macro-categorie per definire chi puo' partecipare:

**Imprese individuali:**
- Ditta individuale / Impresa individuale
- Libero professionista con P.IVA (controverso: alcuni bandi li escludono)

**Societa' di persone:**
- SNC (Societa' in Nome Collettivo)
- SAS (Societa' in Accomandita Semplice)
- SS (Societa' Semplice — solo settore agricolo)

**Societa' di capitali:**
- SRL (Societa' a Responsabilita' Limitata)
- SRLS (SRL Semplificata)
- SPA (Societa' per Azioni)
- SAPA (Societa' in Accomandita per Azioni)

**Cooperative:**
- Cooperativa sociale (tipo A — servizi, tipo B — inserimento lavorativo)
- Cooperativa di produzione/lavoro
- Cooperativa di consumo

**Enti del Terzo Settore:**
- APS (Associazione di Promozione Sociale)
- ODV (Organizzazione di Volontariato)
- Impresa sociale (qualifica, non tipo giuridico — puo' essere SRL, fondazione, cooperativa)
- Fondazione
- Associazione

**Forme speciali:**
- Startup innovativa (status, non forma — sempre societa' di capitali o cooperativa)
- PMI innovativa (status)
- Consorzio
- Rete d'impresa (con o senza soggettivita' giuridica)
- Societa' benefit (qualifica aggiuntiva)

### Proposta: dropdown forme giuridiche

```python
FORME_GIURIDICHE = [
    # Imprese individuali
    ('impresa_individuale',  'Impresa individuale / Ditta individuale'),
    ('libero_professionista', 'Libero professionista con P.IVA'),

    # Societa' di persone
    ('snc',   'SNC — Societa\' in Nome Collettivo'),
    ('sas',   'SAS — Societa\' in Accomandita Semplice'),

    # Societa' di capitali
    ('srl',   'SRL — Societa\' a Responsabilita\' Limitata'),
    ('srls',  'SRLS — SRL Semplificata'),
    ('spa',   'SPA — Societa\' per Azioni'),
    ('sapa',  'SAPA — Societa\' in Accomandita per Azioni'),

    # Cooperative
    ('cooperativa',          'Societa\' cooperativa'),
    ('cooperativa_sociale',  'Cooperativa sociale'),

    # Terzo settore
    ('associazione',  'Associazione'),
    ('fondazione',    'Fondazione'),
    ('aps',           'APS — Associazione di Promozione Sociale'),
    ('odv',           'ODV — Organizzazione di Volontariato'),

    # Reti e consorzi
    ('consorzio',      'Consorzio'),
    ('rete_impresa',   'Rete d\'impresa'),
]
```

### Status/qualifiche (flag separati, non nel dropdown)

Questi non sono forme giuridiche ma qualifiche aggiuntive che influenzano i bandi:

```python
QUALIFICHE_SOGGETTO = [
    ('startup_innovativa',  'Startup innovativa (sez. speciale CCIAA)'),
    ('pmi_innovativa',      'PMI innovativa'),
    ('impresa_sociale',     'Impresa sociale (D.Lgs. 155/2006)'),
    ('societa_benefit',     'Societa\' benefit'),
    ('impresa_femminile',   'Impresa femminile (>= 2/3 quote + organi)'),
    ('impresa_giovanile',   'Impresa giovanile (titolare/soci under 35)'),
]
```

Questi vanno come **checkbox multipli** nel form soggetto, non nel dropdown forma giuridica. Ogni qualifica sblocca/blocca bandi specifici e va nel `hard_stops.py`.

### Regimi fiscali

```python
REGIMI_FISCALI = [
    ('ordinario',     'Regime ordinario'),
    ('semplificato',  'Regime semplificato'),
    ('forfettario',   'Regime forfettario'),
    ('agricolo',      'Regime speciale agricoltura'),
    ('non_profit',    'Ente non commerciale'),
]
```

Il regime forfettario e' particolarmente rilevante: molti bandi lo escludono (es. crediti d'imposta non utilizzabili, IVA non detraibile = costo effettivo maggiore).

### Impatto sugli hard stops

La forma giuridica e' il filtro hard stop piu' impattante:
- "Solo societa' di capitali" → esclude imprese individuali, SNC, SAS
- "Solo startup innovative" → serve SRL/SPA/cooperativa + iscrizione sezione speciale
- "Solo PMI" → serve rispettare soglie dimensionali (< 250 dip, < 50M fatturato)
- "Solo imprese femminili" → serve >= 2/3 quote e organi amministrativi donna

Il `hard_stops.py` attuale controlla la forma giuridica ma con categorie generiche. Con le nuove voci piu' precise, il matching migliora significativamente.

### Priorita': ALTA
Questa e' la modifica piu' impattante delle tre. La forma giuridica determina l'ammissibilita' a praticamente ogni bando. Avere un dropdown preciso e le qualifiche come flag separati migliora sia gli hard stop che lo scoring.

---

## Riepilogo decisioni

| Area | Stato attuale | Proposta | Priorita' | Bloccante deploy? |
|------|--------------|----------|-----------|-------------------|
| Zone speciali | 4 opzioni, manca ZLS e cratere | 6 opzioni + matching da comune | MEDIA | No |
| Cofinanziamento fonti | 5 opzioni single-select, FdG mal categorizzato | 8 opzioni multi-select, FdG come flag soggetto | MEDIA-ALTA | No |
| Forma giuridica | Free-text o set limitato | 16 forme + 6 qualifiche flag + 5 regimi fiscali | ALTA | No |

### Ordine di implementazione suggerito

1. **Forma giuridica** — impatto massimo su hard stops e scoring
2. **Cofinanziamento fonti** — multi-select + rimozione FdG dalle fonti
3. **Zone speciali** — aggiunta ZLS e cratere, il resto funziona

### File da modificare

Per tutte e 3:
- `web/services/completezza.py` — costanti + check items
- `web/routes/soggetti.py` — passare opzioni al template
- `web/routes/progetti.py` — passare opzioni al template
- `web/templates/partials/soggetto_tab_anagrafica.html` — form soggetto
- `web/templates/partials/progetto_tab_profilo.html` — form profilo progetto
- `engine/eligibility/hard_stops.py` — matching piu' preciso
- `engine/eligibility/configurable_scorer.py` — scoring rules aggiornate

Per la forma giuridica:
- Migration 013 (gia' pianificata): aggiungere campi strutturati al soggetto
- Seed data: aggiornare il soggetto "La Monica Luciano" con i nuovi valori
