"""
Project onboarding pure helpers for form prefill and validation.
"""
from __future__ import annotations

import re


def seed_from_profile_json(data: dict) -> dict:
    """Extract prefill values from a company_profile-like JSON."""
    anagrafica = data.get("anagrafica", {})
    sede = data.get("sede", {})
    attivita = data.get("attivita", {})
    dimensione = data.get("dimensione", {})
    certificazioni = data.get("certificazioni", {})

    nome = anagrafica.get("denominazione", "")
    slug = (
        re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
        if isinstance(nome, str) and nome else ""
    )
    slug = slug[:32]

    ateco_primary = attivita.get("ateco_2025", attivita.get("ateco", ""))
    ateco_secondary = attivita.get("ateco_secondari", [])
    if not isinstance(ateco_secondary, list):
        ateco_secondary = []

    skills_keywords = data.get("skills", {}).get("keywords", [])
    if not isinstance(skills_keywords, list):
        skills_keywords = []

    return {
        "new_slug": slug,
        "new_nome": nome,
        "new_desc_breve": attivita.get("settore_principale", ""),
        "new_desc": "",
        "new_prefix": "",
        "new_chat_id": "",
        "denominazione": nome,
        "forma_giuridica": anagrafica.get("forma_giuridica", "impresa individuale"),
        "partita_iva": anagrafica.get("partita_iva", ""),
        "regime_fiscale": anagrafica.get("regime_fiscale", "ordinario"),
        "comune": sede.get("comune", ""),
        "provincia": sede.get("provincia", ""),
        "regione": sede.get("regione", "Sicilia"),
        "zona_zes": bool(sede.get("zona_zes", True)),
        "zona_mezzogiorno": bool(sede.get("zona_mezzogiorno", True)),
        "ateco": ateco_primary,
        "ateco_secondari_text": "\n".join(x for x in ateco_secondary if isinstance(x, str)),
        "settore": attivita.get("settore_principale", ""),
        "data_inizio": attivita.get("data_inizio", ""),
        "anni_attivita": int(attivita.get("anni_attivita", 0) or 0),
        "dipendenti": int(dimensione.get("dipendenti", 0) or 0),
        "fatturato_max": int(dimensione.get("fatturato_stimato_max", 0) or 0),
        "micro_impresa": bool(dimensione.get("micro_impresa", True)),
        "iso_9001": bool(certificazioni.get("iso_9001", False)),
        "iso_27001": bool(certificazioni.get("iso_27001", False)),
        "soa": bool(certificazioni.get("soa")),
        "skills_text": "\n".join(x for x in skills_keywords if isinstance(x, str)),
    }


def validate_project_form(payload: dict) -> list[str]:
    errors: list[str] = []

    slug = str(payload.get("new_slug", "")).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,30}[a-z0-9]", slug):
        errors.append("Slug non valido: usa solo minuscole, numeri e trattini (3-32 caratteri).")

    if not str(payload.get("new_nome", "")).strip():
        errors.append("Nome progetto obbligatorio.")

    if not str(payload.get("denominazione", "")).strip():
        errors.append("Denominazione legale obbligatoria.")

    ateco = str(payload.get("ateco", "")).strip()
    if ateco and not re.fullmatch(r"\d{2}(?:\.\d{2}){0,2}", ateco):
        errors.append("ATECO principale non valido (esempio corretto: 62.01.00).")

    piva = str(payload.get("partita_iva", "")).strip().upper()
    if piva and not re.fullmatch(r"(?:\d{11}|[A-Z0-9]{16})", piva):
        errors.append("P.IVA/Codice Fiscale non valido.")

    data_inizio = str(payload.get("data_inizio", "")).strip()
    if data_inizio and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", data_inizio):
        errors.append("Data inizio non valida (usa formato GG/MM/AAAA).")

    return errors

