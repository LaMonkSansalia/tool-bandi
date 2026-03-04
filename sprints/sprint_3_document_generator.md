# Sprint 3 — Document Generator

**Status:** PENDING
**Objective:** For an eligible bando, the system automatically generates draft documents ready for human review.
**Definition of Done:** Click "Generate Documents" in Streamlit → find `output/bandi/{id}/` folder with versioned PDFs ready for review.

---

## Tasks

### 3.1 — Template Engine (WeasyPrint + Jinja2)

- [ ] `engine/generators/templates/html/` — HTML/CSS templates
  - `base.css` — formal PA document style (fonts, margins, header/footer)
  - `proposta_tecnica.html` — technical proposal with formal Italian PA layout
  - `dichiarazione_sostitutiva.html` — DPR 445/2000 self-declaration
  - `allegato_a.html` — generic attachment template
  - `cv_impresa.html` — company presentation + project references
- [ ] `engine/generators/pdf_generator.py`
  - Input: `template_name: str`, `context: dict`
  - Output: PDF bytes via WeasyPrint
- [ ] Verify: generated PDFs meet Italian PA formal standards

### 3.2 — DOCX Generator

- [ ] `engine/generators/docx_generator.py`
  - Input: `template_name: str`, `context: dict`
  - Output: `.docx` file via python-docx
  - Required when bando explicitly asks for Word format (common)
- [ ] `engine/generators/templates/docx/` — Word templates:
  - `proposta_tecnica.docx`, `dichiarazione.docx`
- [ ] Verify: DOCX opens correctly and is properly formatted

### 3.3 — Claude Content Generator

- [ ] `engine/generators/content_generator.py`
  - Input: bando (requirements + evaluation criteria) + company_profile + skills_matrix
  - Output: customized technical proposal text
  - Uses DSPy for structured generation
  - **CRITICAL RULE:** use ONLY verified data from company_profile.json and skills_matrix.json
  - Output includes "sources used" section for audit trail
  - Missing economic amounts (referenze have no monetary values):
    → generate with `"⚠️ TO FILL MANUALLY"` placeholder
    → Streamlit highlights these fields with warning before approval
- [ ] `engine/generators/fact_checker.py`
  - Verifies every generated claim against company_profile and skills_matrix data
  - Flags any unverifiable statement
  - **BLOCKS output if any claim is unverified** — requires human intervention
  - Rationale: false declarations in public documents carry criminal liability

**Anti-hallucination claim record format:**
```python
{
    "claim": "Developed 3 e-commerce projects in the last 3 years",
    "source": "skills_matrix.json → referenze_progetti[namamandorle, phimostop, sansalia]",
    "verified": True,
    "verified_at": "2026-03-02"
}
# If verified == False → BLOCK output, raise exception, alert human
```

- [ ] Verify: generated proposal cites only real references from skills_matrix.json

### 3.4 — Document Versioning

When a document is regenerated, **NEVER overwrite** — create a new version:

- [ ] File naming: `02_proposta_tecnica_v1.pdf`, `_v2.pdf`, `_v3.pdf`
- [ ] DB: `bando_documenti_generati.versione` increments on each generation
- [ ] Streamlit shows version list with: version number, generation date, status (draft/approved)
- [ ] Old versions remain accessible for comparison
- [ ] Verify: clicking "Regenerate" creates v2 while v1 remains in folder and DB

### 3.5 — Output Package Builder

- [ ] `engine/generators/package_builder.py`
  - Creates `output/bandi/{YYYYMMDD}_{slug}/` folder
  - Copies visura camerale from `context/documents/`
  - Generates all documents required by the specific bando
  - Creates `00_README.md` with bando-specific submission instructions
  - Creates `01_checklist_invio.md` step-by-step todo for manual submission
    - **For form-based portals (InPA, etc.):** checklist explains field-by-field where to upload each PDF on the web form
  - Creates `submission_info.json`:
    ```json
    {
      "bando_id": 42,
      "portal_url": "https://...",
      "deadline": "2026-04-30",
      "submission_type": "online_form",
      "checklist_fields": ["upload proposta", "upload dichiarazione", "firma digitale"],
      "data_invio": null,
      "protocollo_ricevuto": null,
      "notes": ""
    }
    ```
- [ ] Verify: output folder is complete and navigable

### 3.6 — Streamlit: Document Management Page

- [ ] `engine/ui/pages/04_documenti.py`
  - For each bando in stato "lavorazione": shows generated documents
  - PDF inline preview (via base64)
  - Version selector: shows v1, v2, v3... with dates and status badges
  - Buttons: "Approve" / "Regenerate" / "Edit manually"
  - Each document status: draft | approved | to-sign
  - ⚠️ Highlights fields marked "TO FILL MANUALLY" before approval
  - Download: single file OR complete ZIP package
  - Submission tracking: when user marks as "Inviato":
    - Prompts for `data_invio` and `protocollo_ricevuto`
    - Saves both to DB
- [ ] Verify: full flow review → approve → download works

---

## Technical Proposal Structure

```
1. Proponente (Submitting Entity)
   → Data from company_profile.json

2. Descrizione del progetto proposto (Project Description)
   → Generated by Claude based on bando evaluation criteria

3. Competenze e referenze (Skills and References)
   → Extracted from skills_matrix.json → referenze_progetti (verified only)

4. Metodologia e piano di lavoro (Methodology and Work Plan)
   → Standard template + Claude customization per bando

5. Risultati attesi e indicatori (Expected Results and KPIs)
   → Mapped to bando's own KPI definitions

6. Budget dettagliato (Detailed Budget)
   → Template with "⚠️ TO FILL MANUALLY" placeholders
```

---

## Expected Output

```
engine/generators/
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
├── content_generator.py      ✓
├── fact_checker.py           ✓
├── pdf_generator.py          ✓
├── docx_generator.py         ✓
└── package_builder.py        ✓
engine/ui/pages/
└── 04_documenti.py           ✓
```
