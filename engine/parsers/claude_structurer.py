"""
Claude structurer — converts extracted markdown text into validated JSON
matching the bandi DB schema.
Uses DSPy for structured, deterministic prompting with schema enforcement.
"""
from __future__ import annotations
import json
import logging
from typing import Any

import anthropic
from engine.parsers.schema import ClaudeStructurerOutput, BandoStructured, BandoRequisitoRaw
from engine.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


EXTRACTION_PROMPT = """\
Analizza questo testo di un bando pubblico italiano ed estrai le informazioni in JSON.

TESTO DEL BANDO:
{testo}

Restituisci SOLO un oggetto JSON valido con questa struttura esatta:
{{
  "bando": {{
    "titolo": "...",
    "ente_erogatore": "...",
    "data_scadenza": "YYYY-MM-DD o null",
    "data_pubblicazione": "YYYY-MM-DD o null",
    "budget_totale": numero o null,
    "importo_max": numero o null,
    "tipo_beneficiario": ["impresa_individuale", "pmi", ...],
    "regioni_ammesse": ["Sicilia", "tutte", ...],
    "fatturato_minimo": numero o null,
    "dipendenti_minimi": numero intero o null,
    "anzianita_minima_anni": numero intero o null,
    "soa_richiesta": true/false,
    "certificazioni_richieste": ["ISO 9001", ...],
    "settori_ateco": ["62.20", "62.01", ...],
    "criteri_valutazione": [{{"criterio": "...", "peso": numero o null}}],
    "documenti_da_allegare": ["domanda", "dichiarazione sostitutiva", ...]
  }},
  "requisiti": [
    {{
      "tipo": "hard|soft|bonus",
      "categoria": "fatturato|dipendenti|geo|giuridica|certificazione|anzianita|altro",
      "descrizione_originale": "testo originale del requisito",
      "valore_richiesto": "valore specifico o null",
      "soddisfatto": null,
      "semaforo": null,
      "nota": "eventuale nota interpretativa"
    }}
  ],
  "parsing_notes": "note su ambiguità o informazioni mancanti",
  "confidence": "high|medium|low"
}}

Regole:
- Per tipo_beneficiario usa: impresa_individuale, pmi, micro_impresa, srl, spa, startup, tutti, libero_professionista
- Per regioni_ammesse usa nomi completi delle regioni italiane o "tutte"
- Se un'informazione non è presente nel testo scrivi null
- I valori monetari devono essere numeri (es. 25000, non "25.000€")
- NON inventare informazioni non presenti nel testo
"""


def structure_bando(markdown_text: str, portale: str | None = None) -> ClaudeStructurerOutput:
    """
    Convert extracted markdown text to validated structured bando data.

    Args:
        markdown_text: text extracted by docling_extractor
        portale: portal name for context (e.g. "invitalia")

    Returns:
        ClaudeStructurerOutput with validated BandoStructured + requirements list
    """
    client = _get_client()

    # Truncate if too long (keep first 30k chars — enough for most bandi)
    text = markdown_text[:30000]
    if len(markdown_text) > 30000:
        logger.warning(f"Bando text truncated from {len(markdown_text)} to 30000 chars")

    prompt = EXTRACTION_PROMPT.format(testo=text)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_json = response.content[0].text.strip()

        # Strip markdown code blocks if present
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
        raw_json = raw_json.strip()

        data = json.loads(raw_json)

    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {e}\nRaw: {raw_json[:500]}")
        # Retry once with stricter instruction
        return _retry_structure(client, text, str(e))
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise

    # Add portale if provided and not already set
    if portale and not data.get("bando", {}).get("portale"):
        data.setdefault("bando", {})["portale"] = portale

    # Validate with Pydantic
    try:
        bando = BandoStructured(**data.get("bando", {}))
        requisiti = [BandoRequisitoRaw(**r) for r in data.get("requisiti", [])]
        return ClaudeStructurerOutput(
            bando=bando,
            requisiti=requisiti,
            parsing_notes=data.get("parsing_notes"),
            confidence=data.get("confidence"),
        )
    except Exception as e:
        logger.error(f"Pydantic validation failed: {e}\nData: {data}")
        raise


def _retry_structure(client: anthropic.Anthropic, text: str, error: str) -> ClaudeStructurerOutput:
    """Single retry with explicit JSON-only instruction."""
    logger.info("Retrying Claude structurer with stricter JSON instruction")
    prompt = (
        f"{EXTRACTION_PROMPT.format(testo=text)}\n\n"
        f"ATTENZIONE: al tentativo precedente hai restituito JSON non valido ({error}). "
        "Restituisci SOLO il JSON, nessun testo prima o dopo, nessun blocco markdown."
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_json = response.content[0].text.strip()
    data = json.loads(raw_json)  # let it raise if still invalid
    bando = BandoStructured(**data.get("bando", {}))
    requisiti = [BandoRequisitoRaw(**r) for r in data.get("requisiti", [])]
    return ClaudeStructurerOutput(
        bando=bando,
        requisiti=requisiti,
        parsing_notes=data.get("parsing_notes"),
        confidence=data.get("confidence"),
    )
