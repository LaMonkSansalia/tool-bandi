"""
Package Builder — assembles the complete submission package for a bando.

Creates:
    output/bandi/{YYYYMMDD}_{slug}/
    ├── 00_README.md                   — bando-specific overview
    ├── 01_checklist_invio.md          — step-by-step submission checklist
    ├── submission_info.json           — machine-readable submission metadata
    ├── documenti/
    │   ├── 02_proposta_tecnica_v1.pdf
    │   ├── 02_proposta_tecnica_v1.docx
    │   ├── 03_dichiarazione_sostitutiva_v1.pdf
    │   ├── 04_cv_impresa_v1.pdf
    │   └── (visura_camerale.pdf — copied from context/documents/ if present)
    └── (bozze precedenti in sottocartella versioni/)

Also saves document records in DB (bando_documenti_generati table).

Usage:
    from engine.generators.package_builder import build_package

    output_dir = build_package(bando_id=42)
    # Returns path to output folder
"""
from __future__ import annotations
import json
import logging
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2

from engine.config import DATABASE_URL
from engine.generators.content_generator import generate_content
from engine.generators.fact_checker import check_claims
from engine.generators.pdf_generator import generate_pdf
from engine.generators.docx_generator import generate_docx

logger = logging.getLogger(__name__)

OUTPUT_BASE = Path(__file__).parent.parent.parent / "output" / "bandi"
CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"
CONTEXT_DOCS = CONTEXT_DIR / "documents"


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to filesystem-safe slug."""
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:max_len]


def _get_next_version(output_dir: Path, doc_name: str) -> int:
    """Find the next version number for a document in the output dir."""
    existing = list(output_dir.glob(f"{doc_name}_v*.pdf")) + list(output_dir.glob(f"{doc_name}_v*.docx"))
    if not existing:
        return 1
    versions = []
    for f in existing:
        m = re.search(r"_v(\d+)\.", f.name)
        if m:
            versions.append(int(m.group(1)))
    return max(versions) + 1 if versions else 1


def _load_bando(bando_id: int) -> dict[str, Any]:
    """Load bando from DB."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT * FROM bandi WHERE id = %s", (bando_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Bando {bando_id} not found in DB")
    cols = [d[0] for d in cur.description]
    bando = dict(zip(cols, row))

    # Load requirements
    cur.execute("SELECT * FROM bando_requisiti WHERE bando_id = %s", (bando_id,))
    req_rows = cur.fetchall()
    req_cols = [d[0] for d in cur.description]
    bando["requisiti"] = [dict(zip(req_cols, r)) for r in req_rows]

    cur.close()
    conn.close()
    return bando


def _load_company_context() -> dict[str, Any]:
    """Load company profile for template context."""
    import json
    profile_path = CONTEXT_DIR / "company_profile.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"company_profile.json not found at {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def _save_document_to_db(
    bando_id: int,
    tipo: str,
    filename: str,
    versione: int,
    is_draft: bool,
) -> int | None:
    """Save generated document record to DB."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bando_documenti_generati
                (bando_id, tipo_documento, filename, versione, stato, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (
            bando_id,
            tipo,
            filename,
            versione,
            "bozza" if is_draft else "pronto",
        ))
        doc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return doc_id
    except Exception as e:
        logger.error(f"Failed to save document to DB: {e}")
        return None


def _write_readme(output_dir: Path, bando: dict[str, Any], package_files: list[str]) -> None:
    """Generate 00_README.md for the package."""
    titolo = bando.get("titolo", "Bando")
    ente = bando.get("ente_erogatore", "")
    scadenza = bando.get("data_scadenza")
    if scadenza and hasattr(scadenza, "strftime"):
        scadenza_str = scadenza.strftime("%d/%m/%Y")
    elif scadenza:
        scadenza_str = str(scadenza)
    else:
        scadenza_str = "⚠ verificare"

    portale = bando.get("portale", "")
    url = bando.get("url_fonte") or bando.get("url", "")
    importo = bando.get("importo_max")
    importo_str = f"€{importo:,.0f}".replace(",", ".") if importo else "⚠ verificare"

    files_list = "\n".join(f"- `{f}`" for f in sorted(package_files))

    readme = f"""# {titolo}

## Informazioni Bando

| Campo | Valore |
|-------|--------|
| **Ente erogatore** | {ente} |
| **Portale** | {portale} |
| **Scadenza** | **{scadenza_str}** |
| **Importo massimo** | {importo_str} |
| **URL** | {url} |
| **ID DB** | {bando.get('id')} |

## Score di idoneità

Score: **{bando.get('score', 'N/D')}**/100

## Contenuto del pacchetto

{files_list}

## ⚠ IMPORTANTE — Prima dell'invio

1. **Verificare tutti i campi marcati "⚠ DA COMPILARE MANUALMENTE"** nelle bozze
2. **Leggere la checklist** `01_checklist_invio.md` per le istruzioni di invio specifiche
3. **Firmare digitalmente** (firma digitale CAdES o PAdES) i documenti richiesti
4. **Non inviare bozze** — i documenti devono essere revisionati e approvati in Streamlit

## Generazione

Package generato il: {datetime.now().strftime("%d/%m/%Y %H:%M")}
"""

    (output_dir / "00_README.md").write_text(readme, encoding="utf-8")


def _write_checklist(output_dir: Path, bando: dict[str, Any]) -> None:
    """Generate 01_checklist_invio.md with submission instructions."""
    portale = bando.get("portale", "")
    titolo = bando.get("titolo", "")
    url = bando.get("url_fonte") or bando.get("url", "")
    scadenza = bando.get("data_scadenza")
    scadenza_str = str(scadenza) if scadenza else "⚠ verificare"

    # Portal-specific instructions
    portal_instructions = {
        "invitalia": """
### Invitalia — Portale Click Day / Gestione incentivi

1. Accedere al portale Invitalia: https://www.invitalia.it
2. Registrarsi/accedere con SPID o CNS
3. Cercare il bando: "{titolo}"
4. Compilare il modulo online inserendo i dati dell'impresa
5. Caricare i seguenti allegati nella sezione "Documenti":
   - [ ] Proposta tecnica (PDF firmato digitalmente)
   - [ ] Dichiarazione sostitutiva (PDF firmato)
   - [ ] Visura camerale (recente, max 6 mesi)
   - [ ] CV Impresa (PDF)
   - [ ] Piano finanziario dettagliato (compilare manualmente)
6. Verificare che tutti i campi obbligatori siano compilati
7. Inviare la domanda e **salvare il numero di protocollo**
""",
        "regione_sicilia": """
### Regione Siciliana — Portale SIAP / email PEC

1. Accedere al portale: https://www.regione.sicilia.it
2. Verificare le istruzioni specifiche nel bando (alcune richiedono PEC, altre form online)
3. **Se invio via PEC:**
   - Destinatario PEC: verificare nel bando
   - Oggetto: "Domanda partecipazione — {titolo} — [P.IVA]"
   - Allegare TUTTI i documenti in PDF
4. **Se invio via portale:**
   - Completare registrazione con SPID
   - Caricare documenti nella sezione dedicata
5. Documenti da allegare:
   - [ ] Allegato A (domanda di partecipazione) firmato
   - [ ] Proposta tecnica firmata
   - [ ] Dichiarazione sostitutiva firmata + copia CIE/Passaporto
   - [ ] Visura camerale
   - [ ] Piano finanziario
6. Salvare ricevuta/protocollo
""",
        "padigitale": """
### PA Digitale 2026 — Piattaforma PNRR

1. Accedere a: https://padigitale2026.gov.it
2. Accedere con SPID (obbligatorio)
3. Navigare alla misura: "{titolo}"
4. Compilare il form online (dati impresa, progetto, budget)
5. Caricare documentazione richiesta:
   - [ ] Proposta tecnica (PDF firmato)
   - [ ] Dichiarazione sostitutiva
   - [ ] Visura camerale
6. Inviare e salvare il numero di candidatura
""",
        "mimit": """
### MIMIT — Portale Incentivi Imprese

1. Accedere a: https://www.mimit.gov.it/it/incentivi
2. Seguire il link al portale specifico dell'incentivo (spesso reindirizza a Invitalia o Mediocredito)
3. Registrarsi con SPID/CNS
4. Caricare la documentazione richiesta
5. Compilare il form e inviare
""",
        "inpa": """
### InPA — Portale Bandi

1. Accedere a: https://www.inpa.gov.it
2. Accedere con SPID
3. Cercare il bando e seguire le istruzioni specifiche
4. Caricare documenti e inviare
""",
        "comune_palermo": """
### Comune di Palermo — Invio via PEC o sportello

1. Verificare il metodo di invio richiesto nel bando (PEC, sportello, SUAP)
2. **Se via PEC:**
   - Destinatario: verificare nel bando (spesso suap@pec.comune.palermo.it)
   - Oggetto: "Domanda bando — {titolo} — P.IVA [tua_piva]"
3. **Se via SUAP:** https://www.comune.palermo.it/suap.php
4. Allegare tutti i documenti firmati digitalmente
""",
        "euroinfosicilia": """
### EuroInfoSicilia — Bando aggregato

1. EuroInfoSicilia è un aggregatore: verificare l'ente erogatore originale del bando
2. Seguire il link all'ente originale e le istruzioni specifiche
3. L'invio avviene direttamente sull'ente emittente (Regione, MIMIT, ecc.)
""",
    }

    specific_instr = portal_instructions.get(
        portale,
        f"\n### Istruzioni invio\n\nVerificare le istruzioni specifiche sul portale: {url}\n"
    ).format(titolo=titolo)

    checklist = f"""# Checklist Invio — {titolo}

**Scadenza: {scadenza_str}**
**Portale: {portale}**
**URL bando: {url}**

---

## Fase 1 — Preparazione documenti (fare PRIMA)

- [ ] Leggere il bando completo (PDF allegati)
- [ ] Verificare tutti i campi `⚠ DA COMPILARE MANUALMENTE` nella proposta tecnica
- [ ] Compilare il piano finanziario dettagliato (budget dettagliato)
- [ ] Verificare che la visura camerale in `context/documents/` sia recente (< 6 mesi)
- [ ] Preparare firma digitale (CNS/SmartCard o firma remota)

## Fase 2 — Revisione documenti

- [ ] Rileggere `02_proposta_tecnica_v1.pdf` e correggere/completare
- [ ] Rileggere `03_dichiarazione_sostitutiva_v1.pdf` e verificare dati anagrafici
- [ ] Approvare documenti in Streamlit (pagina Documenti)
- [ ] Firmare digitalmente tutti i PDF richiesti

## Fase 3 — Invio
{specific_instr}

## Fase 4 — Post-invio

- [ ] Salvare la **ricevuta/protocollo** di invio
- [ ] Aggiornare in Streamlit:
  - Stato bando → "Inviato"
  - Data invio
  - Numero protocollo ricevuto
- [ ] Impostare reminder per eventuali comunicazioni dell'ente

---

*Checklist generata il {datetime.now().strftime("%d/%m/%Y %H:%M")}*
"""

    (output_dir / "01_checklist_invio.md").write_text(checklist, encoding="utf-8")


def _write_submission_info(output_dir: Path, bando: dict[str, Any]) -> None:
    """Generate submission_info.json."""
    scadenza = bando.get("data_scadenza")
    scadenza_str = scadenza.isoformat() if hasattr(scadenza, "isoformat") else str(scadenza) if scadenza else None

    info = {
        "bando_id": bando.get("id"),
        "titolo": bando.get("titolo"),
        "ente_erogatore": bando.get("ente_erogatore"),
        "portal_url": bando.get("url_fonte") or bando.get("url"),
        "portale": bando.get("portale"),
        "deadline": scadenza_str,
        "importo_max": bando.get("importo_max"),
        "score": bando.get("score"),
        "submission_type": "online_form",   # default — update manually if needed
        "checklist_fields": [],             # to be filled manually
        "data_invio": None,
        "protocollo_ricevuto": None,
        "notes": "",
        "generated_at": datetime.now().isoformat(),
    }

    (output_dir / "submission_info.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────
# MAIN PUBLIC API
# ─────────────────────────────────────────────

def build_package(bando_id: int, is_draft: bool = True) -> Path:
    """
    Build the complete submission package for a bando.

    Args:
        bando_id: DB id of the bando
        is_draft: If True, all documents will have BOZZA watermark (default True)

    Returns:
        Path to the generated output directory

    Raises:
        ValueError: Bando not found
        FileNotFoundError: Required context files missing
    """
    bando = _load_bando(bando_id)
    company = _load_company_context()

    titolo = bando.get("titolo", f"bando_{bando_id}")
    slug = _slugify(titolo)
    date_prefix = datetime.now().strftime("%Y%m%d")
    package_dir = OUTPUT_BASE / f"{date_prefix}_{slug}"
    docs_dir = package_dir / "documenti"
    docs_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Building package for bando {bando_id}: {package_dir}")

    # 1. Generate content
    try:
        generated = generate_content(bando, company)
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        generated = None

    # 2. Fact check (non-blocking for drafts)
    if generated and generated.claims:
        try:
            fact_result = check_claims(generated.claims)
            if not fact_result.all_verified and not is_draft:
                raise RuntimeError(
                    f"Fact check failed: {fact_result.unverified_count} unverified claims. "
                    "Document blocked. Set is_draft=True to generate draft anyway."
                )
            logger.info(fact_result.summary())
        except Exception as e:
            logger.warning(f"Fact check error: {e}")
            fact_result = None
    else:
        fact_result = None

    # 3. Build template context
    base_context = {
        "bando": {
            "id": bando.get("id"),
            "titolo": bando.get("titolo"),
            "ente_erogatore": bando.get("ente_erogatore"),
            "data_scadenza": str(bando.get("data_scadenza", "")),
            "importo_max": bando.get("importo_max"),
            "url": bando.get("url_fonte") or bando.get("url"),
            "obiettivi": bando.get("obiettivi"),
            "sede_presentazione": "Palermo",
        },
        "company": company,
        "is_draft": is_draft,
    }

    if generated:
        base_context.update(generated.to_context_dict())
    else:
        base_context.update({
            "content": {},
            "references": [],
            "claim_sources": [],
        })

    package_files: list[str] = []

    # 4. Generate documents with versioning
    documents_to_generate = [
        ("proposta_tecnica", "02_proposta_tecnica", True, True),   # (template, prefix, pdf, docx)
        ("dichiarazione_sostitutiva", "03_dichiarazione_sostitutiva", True, False),
        ("cv_impresa", "04_cv_impresa", True, False),
    ]

    for template_name, file_prefix, make_pdf, make_docx in documents_to_generate:
        version = _get_next_version(docs_dir, file_prefix)
        version_str = f"v{version}"
        ctx = {**base_context, "version": version_str}

        # PDF
        if make_pdf:
            pdf_filename = f"{file_prefix}_{version_str}.pdf"
            pdf_path = docs_dir / pdf_filename
            try:
                pdf_bytes = generate_pdf(template_name, ctx, is_draft=is_draft)
                pdf_path.write_bytes(pdf_bytes)
                package_files.append(f"documenti/{pdf_filename}")
                logger.info(f"Generated: {pdf_filename}")
                _save_document_to_db(bando_id, template_name, pdf_filename, version, is_draft)
            except Exception as e:
                logger.error(f"PDF generation failed for {template_name}: {e}")

        # DOCX
        if make_docx:
            docx_filename = f"{file_prefix}_{version_str}.docx"
            docx_path = docs_dir / docx_filename
            try:
                docx_bytes = generate_docx(template_name, ctx)
                docx_path.write_bytes(docx_bytes)
                package_files.append(f"documenti/{docx_filename}")
                logger.info(f"Generated: {docx_filename}")
            except Exception as e:
                logger.error(f"DOCX generation failed for {template_name}: {e}")

    # 5. Copy static documents from context/documents/
    if CONTEXT_DOCS.exists():
        for doc_file in CONTEXT_DOCS.glob("*"):
            if doc_file.is_file():
                dest = docs_dir / doc_file.name
                shutil.copy2(doc_file, dest)
                package_files.append(f"documenti/{doc_file.name}")
                logger.info(f"Copied: {doc_file.name}")

    # 6. Generate README + checklist + submission_info
    _write_readme(package_dir, bando, package_files)
    _write_checklist(package_dir, bando)
    _write_submission_info(package_dir, bando)

    package_files = ["00_README.md", "01_checklist_invio.md", "submission_info.json"] + package_files

    logger.info(
        f"Package complete: {package_dir} ({len(package_files)} files)"
    )
    return package_dir


def create_zip_package(bando_id: int) -> bytes:
    """
    Build package and return as ZIP bytes (for Streamlit download button).
    """
    import zipfile
    import io

    package_dir = build_package(bando_id)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(package_dir.rglob("*")):
            if file_path.is_file():
                arcname = file_path.relative_to(package_dir)
                zf.write(file_path, arcname)

    zip_bytes = buffer.getvalue()
    logger.info(f"ZIP package: {len(zip_bytes)} bytes")
    return zip_bytes
