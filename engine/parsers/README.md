# Parsers — Document AI

Docling + Claude API per estrarre informazioni strutturate dai PDF dei bandi.

## Pipeline

```
PDF / Word / HTML
       ↓
docling_extractor.py     → testo markdown strutturato (Docling)
       ↓                    fallback: Claude multimodal per PDF scansionati
claude_structurer.py     → JSON strutturato (DSPy + Claude API)
       ↓
PostgreSQL: bandi + bando_requisiti
```

## Struttura

```
parsers/
├── docling_extractor.py     ← PDF → Markdown (Sprint 1)
├── claude_structurer.py     ← Markdown → JSON strutturato (Sprint 1)
└── schema.py                ← Pydantic models per validazione output
```

## Output Atteso da claude_structurer

```json
{
  "titolo": "...",
  "ente_erogatore": "...",
  "data_scadenza": "2026-04-30",
  "budget_totale": 500000,
  "importo_max": 25000,
  "tipo_beneficiario": ["impresa_individuale", "pmi"],
  "fatturato_minimo": null,
  "dipendenti_minimi": null,
  "anzianita_minima_anni": 1,
  "soa_richiesta": false,
  "certificazioni_richieste": [],
  "settori_ateco": ["62.20", "62.01"],
  "regioni_ammesse": ["tutte"],
  "criteri_valutazione": [
    {"criterio": "qualita_tecnica", "peso": 60},
    {"criterio": "costo", "peso": 40}
  ],
  "documenti_da_allegare": ["domanda", "dichiarazione_sostitutiva"]
}
```

## Gestione Fallback

- PDF testo digitale → Docling (veloce, gratuito)
- PDF scansionato → Claude API multimodal (a pagamento, preciso)
- PDF con tabelle → pdfplumber (estratto separatamente)
