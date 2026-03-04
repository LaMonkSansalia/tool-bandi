# Eligibility — Motore di Verifica

Determina se un bando è accessibile, con quale score e quali gap.

## Pipeline

```
Bando (JSON strutturato)
       ↓
hard_stops.py     → ESCLUSO (con motivo) | PASSA
       ↓ solo se PASSA
scorer.py         → score 0-100
       ↓
gap_analyzer.py   → lista gap (bloccanti | recuperabili | informativi)
       ↓
PostgreSQL: aggiorna bandi.score + bando_requisiti.semaforo
```

## Struttura

```
eligibility/
├── hard_stops.py        ← filtri escludenti (Sprint 1)
├── scorer.py            ← calcolo score 0-100 (Sprint 1)
├── gap_analyzer.py      ← analisi gap e recuperabilità (Sprint 1)
└── rules.py             ← regole caricate da company_profile.json
```

## Regole Hard Stop (da company_profile.json)

| Campo | Condizione Esclusione | Motivo |
|-------|----------------------|--------|
| `fatturato_minimo` | > 85.000€ | Regime forfettario cap |
| `dipendenti_minimi` | > 0 | 0 dipendenti |
| `soa_richiesta` | == true | Nessuna attestazione SOA |
| `tipo_beneficiario` | non include impresa_individuale | Forma giuridica |
| `regioni_ammesse` | non include Sicilia/Sud/tutte | Geografico |
| `anzianita_minima_anni` | > 3 | Attività dal 2023 |

## Bonus Score

| Condizione | Punti |
|-----------|-------|
| Regione Sicilia ammessa | +15 |
| Under 36 | +10 |
| ATECO 62.20/62.01/62.02 ammesso | +20 |
| Zona ZES | +10 |
| Nuova impresa (< 5 anni) | +10 |
| Nessuna certificazione richiesta | +5 |

## Semafori Requisiti

- **Verde**: soddisfatto con evidenza documentale
- **Giallo**: borderline o verificabile solo a runtime
- **Rosso**: non soddisfatto (ma non escludente — es. cert. di qualità bonus)
