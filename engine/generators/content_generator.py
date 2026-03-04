"""
Content Generator — uses Claude (via DSPy) to generate document content.

CRITICAL RULES:
1. ONLY use data from company_profile.json and skills_matrix.json
2. Every factual claim MUST be traceable to a specific source field
3. Missing data → placeholder "⚠ DA COMPILARE MANUALMENTE" (never invent)
4. Output must pass fact_checker.py before use in documents

Usage:
    from engine.generators.content_generator import generate_content

    result = generate_content(bando, company_profile, skills_matrix)
    # result.content = dict with document sections
    # result.claims = list of ClaimRecord (for fact_checker)
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import dspy

from engine.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

PLACEHOLDER = "⚠ DA COMPILARE MANUALMENTE"
CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class ClaimRecord:
    """Represents a verifiable factual claim in a generated document."""
    claim: str
    source: str          # e.g. "company_profile.json → dipendenti_ultimo_esercizio"
    value_used: str      # the actual value from source
    verified: bool = False
    verified_at: str | None = None


@dataclass
class GeneratedContent:
    """Container for all generated document sections + claim audit trail."""
    descrizione_progetto: str
    competenze_tecniche: str
    metodologia: str
    risultati_attesi: str
    budget_note: str
    references: list[dict[str, Any]] = field(default_factory=list)
    claims: list[ClaimRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_context_dict(self) -> dict[str, Any]:
        """Convert to template context format."""
        return {
            "content": {
                "descrizione_progetto": self.descrizione_progetto,
                "competenze_tecniche": self.competenze_tecniche,
                "metodologia": self.metodologia,
                "risultati_attesi": self.risultati_attesi,
                "budget_note": self.budget_note,
            },
            "references": self.references,
            "claim_sources": [
                {
                    "claim": c.claim,
                    "source": c.source,
                    "verified": c.verified,
                }
                for c in self.claims
            ],
        }


# ─────────────────────────────────────────────
# DSPy SIGNATURES
# ─────────────────────────────────────────────

class BandoContentSignature(dspy.Signature):
    """
    Generate technical proposal content for an Italian public grant (bando).
    Use ONLY data provided in company_profile and skills_matrix.
    For missing information, use the exact placeholder: ⚠ DA COMPILARE MANUALMENTE
    All text must be in formal Italian (PA style).
    """
    bando_titolo: str = dspy.InputField(desc="Titolo del bando")
    bando_obiettivi: str = dspy.InputField(desc="Obiettivi e criteri di valutazione del bando")
    company_summary: str = dspy.InputField(desc="Dati aziendali verificati (da company_profile.json)")
    skills_summary: str = dspy.InputField(desc="Competenze e referenze verificate (da skills_matrix.json)")

    descrizione_progetto: str = dspy.OutputField(
        desc="2-4 paragrafi che descrivono il progetto proposto in relazione agli obiettivi del bando. "
             "Solo fatti verificabili. Placeholder per dati mancanti."
    )
    competenze_tecniche: str = dspy.OutputField(
        desc="Paragrafo sulle competenze tecniche rilevanti per questo bando specifico. "
             "Citare solo competenze presenti in skills_matrix."
    )
    metodologia: str = dspy.OutputField(
        desc="Piano di lavoro con fasi, deliverable, timeline indicativa. "
             "Adattare agli obiettivi del bando."
    )
    risultati_attesi: str = dspy.OutputField(
        desc="Risultati attesi con indicatori quantificabili. "
             "Allineare ai KPI definiti nel bando se specificati."
    )


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def _load_company_profile() -> dict[str, Any]:
    """Load company profile from JSON."""
    path = CONTEXT_DIR / "company_profile.json"
    if not path.exists():
        raise FileNotFoundError(f"company_profile.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_skills_matrix() -> dict[str, Any]:
    """Load skills matrix from JSON."""
    path = CONTEXT_DIR / "skills_matrix.json"
    if not path.exists():
        raise FileNotFoundError(f"skills_matrix.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _build_company_summary(profile: dict[str, Any]) -> tuple[str, list[ClaimRecord]]:
    """
    Build a text summary of company data with claim records.
    Only include fields that are actually populated.
    """
    claims: list[ClaimRecord] = []
    lines: list[str] = []

    def add_field(label: str, keys: list[str], source_path: str) -> str | None:
        """Extract nested value and record claim."""
        val = profile
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                val = None
            if val is None:
                break
        if val is not None:
            val_str = str(val)
            lines.append(f"- {label}: {val_str}")
            claims.append(ClaimRecord(
                claim=f"{label}: {val_str}",
                source=f"company_profile.json → {source_path}",
                value_used=val_str,
            ))
            return val_str
        return None

    add_field("Denominazione", ["denominazione"], "denominazione")
    add_field("Forma giuridica", ["forma_giuridica"], "forma_giuridica")
    add_field("P.IVA", ["partita_iva"], "partita_iva")
    add_field("ATECO primario", ["ateco_primario"], "ateco_primario")
    add_field("Comune sede", ["sede", "comune"], "sede.comune")
    add_field("Dipendenti", ["dipendenti_ultimo_esercizio"], "dipendenti_ultimo_esercizio")
    add_field("Fatturato", ["fatturato_ultimo_esercizio"], "fatturato_ultimo_esercizio")
    add_field("Anno costituzione", ["anno_costituzione"], "anno_costituzione")

    # Certifications
    certs = profile.get("certificazioni", [])
    if certs:
        certs_str = ", ".join(certs)
        lines.append(f"- Certificazioni: {certs_str}")
        claims.append(ClaimRecord(
            claim=f"Certificazioni: {certs_str}",
            source="company_profile.json → certificazioni",
            value_used=certs_str,
        ))

    return "\n".join(lines), claims


def _build_skills_summary(
    matrix: dict[str, Any],
    bando: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[ClaimRecord]]:
    """
    Build skills summary + references list from skills_matrix.
    Returns: (text_summary, references_list, claims)
    """
    claims: list[ClaimRecord] = []
    lines: list[str] = []
    references: list[dict[str, Any]] = []

    # Technical skills
    for categoria, items in matrix.items():
        if categoria == "referenze_progetti":
            continue
        if isinstance(items, list):
            relevant = [str(i) for i in items if i]
            if relevant:
                lines.append(f"\n{categoria.upper()}:")
                for skill in relevant:
                    lines.append(f"  - {skill}")
                    claims.append(ClaimRecord(
                        claim=f"Competenza: {skill}",
                        source=f"skills_matrix.json → {categoria}",
                        value_used=skill,
                    ))
        elif isinstance(items, dict):
            lines.append(f"\n{categoria.upper()}:")
            for sub_cat, sub_items in items.items():
                if isinstance(sub_items, list):
                    for skill in sub_items:
                        lines.append(f"  [{sub_cat}] {skill}")
                        claims.append(ClaimRecord(
                            claim=f"Competenza {sub_cat}: {skill}",
                            source=f"skills_matrix.json → {categoria}.{sub_cat}",
                            value_used=str(skill),
                        ))

    # References
    progetti = matrix.get("referenze_progetti", {})
    if isinstance(progetti, dict):
        for proj_key, proj_data in progetti.items():
            if not isinstance(proj_data, dict):
                continue
            ref = {
                "nome": proj_data.get("nome", proj_key),
                "descrizione": proj_data.get("descrizione", ""),
                "cliente_settore": proj_data.get("settore", proj_data.get("cliente", "—")),
                "anno": proj_data.get("anno", "—"),
                "url": proj_data.get("url", ""),
                "_source_key": proj_key,
            }
            references.append(ref)
            desc_short = ref["descrizione"][:80]
            claims.append(ClaimRecord(
                claim=f"Referenza: {ref['nome']} — {desc_short}",
                source=f"skills_matrix.json → referenze_progetti.{proj_key}",
                value_used=ref["nome"],
            ))
    elif isinstance(progetti, list):
        for i, proj in enumerate(progetti):
            if isinstance(proj, dict):
                ref = {
                    "nome": proj.get("nome", f"Progetto {i+1}"),
                    "descrizione": proj.get("descrizione", ""),
                    "cliente_settore": proj.get("settore", "—"),
                    "anno": proj.get("anno", "—"),
                    "url": proj.get("url", ""),
                    "_source_key": f"referenze_progetti[{i}]",
                }
                references.append(ref)

    return "\n".join(lines), references, claims


def _configure_dspy() -> None:
    """Configure DSPy with Claude via Anthropic."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    lm = dspy.LM(
        model=f"anthropic/{CLAUDE_MODEL}",
        api_key=ANTHROPIC_API_KEY,
        max_tokens=4096,
    )
    dspy.configure(lm=lm)


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def generate_content(
    bando: dict[str, Any],
    company_profile: dict[str, Any] | None = None,
    skills_matrix: dict[str, Any] | None = None,
) -> GeneratedContent:
    """
    Generate technical proposal content for a bando.

    Args:
        bando: Bando dict from DB (needs titolo, criteri_valutazione, testo_html, etc.)
        company_profile: If None, loads from context/company_profile.json
        skills_matrix: If None, loads from context/skills_matrix.json

    Returns:
        GeneratedContent with all sections + claim audit trail

    Raises:
        FileNotFoundError: Context files missing
        ValueError: API key not set
    """
    if company_profile is None:
        company_profile = _load_company_profile()
    if skills_matrix is None:
        skills_matrix = _load_skills_matrix()

    # Build summaries with claims
    company_summary, company_claims = _build_company_summary(company_profile)
    skills_summary, references, skills_claims = _build_skills_summary(skills_matrix, bando)
    all_claims = company_claims + skills_claims

    # Build bando objectives text
    obiettivi_parts = []
    if bando.get("obiettivi"):
        obiettivi_parts.append(f"Obiettivi: {bando['obiettivi']}")
    if bando.get("criteri_valutazione"):
        criteri = bando["criteri_valutazione"]
        if isinstance(criteri, list):
            criteri_str = "; ".join(
                f"{c.get('criterio', '')}: {c.get('peso_percentuale', '')}%"
                for c in criteri if isinstance(c, dict)
            )
        else:
            criteri_str = str(criteri)
        obiettivi_parts.append(f"Criteri di valutazione: {criteri_str}")
    if bando.get("beneficiari"):
        obiettivi_parts.append(f"Beneficiari: {bando['beneficiari']}")
    if bando.get("settori_ammessi"):
        obiettivi_parts.append(f"Settori: {bando['settori_ammessi']}")

    bando_obiettivi = "\n".join(obiettivi_parts) or (
        bando.get("testo_html", "")[:500] if bando.get("testo_html") else "Obiettivi non specificati"
    )

    # Generate with Claude via DSPy
    warnings: list[str] = []
    try:
        _configure_dspy()
        generator = dspy.Predict(BandoContentSignature)
        result = generator(
            bando_titolo=bando.get("titolo", ""),
            bando_obiettivi=bando_obiettivi,
            company_summary=company_summary,
            skills_summary=skills_summary,
        )
        descrizione = result.descrizione_progetto
        competenze = result.competenze_tecniche
        metodologia = result.metodologia
        risultati = result.risultati_attesi

    except Exception as e:
        logger.error(f"DSPy/Claude generation failed: {e}")
        warnings.append(f"Generazione automatica fallita: {e}")
        descrizione = PLACEHOLDER
        competenze = PLACEHOLDER
        metodologia = PLACEHOLDER
        risultati = PLACEHOLDER

    return GeneratedContent(
        descrizione_progetto=descrizione,
        competenze_tecniche=competenze,
        metodologia=metodologia,
        risultati_attesi=risultati,
        budget_note=PLACEHOLDER,
        references=references,
        claims=all_claims,
        warnings=warnings,
    )
