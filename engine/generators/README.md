# Generators — Document Generator

Produce i documenti pronti per la firma a partire dai dati del bando e del profilo.

## Pipeline

```
Bando approvato (stato: lavorazione)
       ↓
content_generator.py   → testi via Claude API (DSPy)
       ↓
fact_checker.py        → verifica ogni claim contro company_profile
       ↓ solo se tutti i claim sono verificati
pdf_generator.py       → PDF via WeasyPrint + Jinja2
docx_generator.py      → DOCX via python-docx (se richiesto)
       ↓
package_builder.py     → output/bandi/{id}_{slug}/ con tutti i file
```

## Struttura

```
generators/
├── templates/
│   ├── html/
│   │   ├── base.css
│   │   ├── proposta_tecnica.html
│   │   ├── dichiarazione_sostitutiva.html
│   │   ├── allegato_a.html
│   │   └── cv_impresa.html
│   └── docx/
│       ├── proposta_tecnica.docx
│       └── dichiarazione.docx
├── content_generator.py     ← Claude draft (Sprint 3)
├── fact_checker.py          ← verifica claims (Sprint 3)
├── pdf_generator.py         ← WeasyPrint (Sprint 3)
├── docx_generator.py        ← python-docx (Sprint 3)
└── package_builder.py       ← output ZIP (Sprint 3)
```

## Regola Anti-Allucinazione

**CRITICA**: ogni affermazione nella proposta deve essere tracciabile a una fonte in `company_profile.json` o `skills_matrix.json`. Se Claude genera un claim non verificabile, il `fact_checker.py` blocca l'output e richiede intervento manuale.

Questo protegge da responsabilità penali per dichiarazioni mendaci in atti pubblici.

## Output Package

```
output/bandi/{YYYYMMDD}_{slug}/
├── 00_README.md              ← istruzioni + URL portale + scadenza
├── 01_checklist_invio.md     ← step-by-step per invio manuale
├── 02_proposta_tecnica.pdf   ← DA FIRMARE
├── 03_dichiarazione.pdf      ← DA FIRMARE
├── 04_allegato_a.pdf         ← DA FIRMARE (se richiesto)
├── 05_cv_impresa.pdf         ← informativo
├── 06_visura_camerale.pdf    ← copia da context/documents/
└── submission_info.json      ← metadati invio
```
