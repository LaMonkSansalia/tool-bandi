"""
Pure decision helpers shared by Streamlit pages.
No Streamlit dependency: safe for unit testing.
"""
from __future__ import annotations

import json
from datetime import date


def to_date(value):
    """Normalize datetime-like values to date."""
    if value is None:
        return None

    if isinstance(value, date):
        return value

    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass

    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                from datetime import datetime
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def infer_bando_phase_key(row: dict, today: date | None = None) -> str:
    """
    Infer bando phase key: 'aperto' | 'annunciato' | 'chiuso'.
    Priority:
    1) metadata explicit status
    2) publication/deadline temporal inference
    """
    if today is None:
        today = date.today()

    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    if isinstance(metadata, dict):
        raw_status = " ".join(
            str(metadata.get(k, "")).lower()
            for k in ("stato_bando", "status", "fase", "phase")
        )
        if "annunc" in raw_status:
            return "annunciato"
        if "apert" in raw_status:
            return "aperto"
        if "chius" in raw_status:
            return "chiuso"

    pub = to_date(row.get("data_pubblicazione"))
    scad = to_date(row.get("data_scadenza"))
    if pub and pub > today:
        return "annunciato"
    if scad and scad < today:
        return "chiuso"
    return "aperto"


def format_currency(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.0f}€"
    except (ValueError, TypeError):
        return "—"


def minimum_requirements(bando: dict) -> list[str]:
    """Build compact list of minimum requirements for quick decision."""
    reqs: list[str] = []

    if bando.get("regioni_ammesse"):
        regioni = bando["regioni_ammesse"]
        if isinstance(regioni, list) and regioni:
            reqs.append(f"Regioni ammesse: {', '.join(regioni)}")

    if bando.get("tipo_beneficiario"):
        tb = bando["tipo_beneficiario"]
        if isinstance(tb, list) and tb:
            reqs.append(f"Beneficiari: {', '.join(tb)}")

    fatt = bando.get("fatturato_minimo")
    if fatt:
        reqs.append(f"Fatturato minimo: {format_currency(fatt)}")

    dip = bando.get("dipendenti_minimi")
    if dip:
        reqs.append(f"Dipendenti minimi: {int(dip)}")

    anz = bando.get("anzianita_minima_anni")
    if anz:
        reqs.append(f"Anzianita' minima: {int(anz)} anni")

    cert = bando.get("certificazioni_richieste")
    if isinstance(cert, list) and cert:
        reqs.append(f"Certificazioni: {', '.join(cert)}")

    if bando.get("soa_richiesta"):
        reqs.append("SOA: obbligatoria")

    return reqs


def normalize_gap_items(
    evaluation: dict | None,
    gap_result,
    hard_stop_excluded: bool,
    hard_stop_reason: str | None = None,
) -> list[dict]:
    """
    Normalize gap items from live gap_result or stored JSON.
    Ensures fallback suggestion and priority sorting.
    """
    items: list[dict] = []
    evaluation = evaluation or {}

    if hard_stop_excluded:
        items.append(
            {
                "tipo": "bloccante",
                "categoria": "hard_stop",
                "descrizione": hard_stop_reason or "Hard stop rilevato",
                "suggerimento": "Valuta adeguamento requisiti o partnership per superare il blocco.",
                "semaforo": "rosso",
            }
        )
        return items

    if gap_result and getattr(gap_result, "gaps", None):
        for g in gap_result.gaps:
            items.append(
                {
                    "tipo": g.tipo.value if hasattr(g.tipo, "value") else str(g.tipo),
                    "categoria": g.categoria,
                    "descrizione": g.descrizione,
                    "suggerimento": g.suggerimento,
                    "semaforo": g.semaforo,
                }
            )
    else:
        stored = evaluation.get("gap_analysis")
        if stored and isinstance(stored, list):
            for g in stored:
                if not isinstance(g, dict):
                    continue
                items.append(
                    {
                        "tipo": str(g.get("tipo", "")),
                        "categoria": str(g.get("categoria", "altro")),
                        "descrizione": str(g.get("descrizione", "")),
                        "suggerimento": str(g.get("suggerimento", "")),
                        "semaforo": str(g.get("semaforo", "giallo")),
                    }
                )

    fallback_suggestions = {
        "certificazione": "Valuta un partner gia' certificato o avvia la certificazione prima della scadenza.",
        "giuridica": "Verifica ammissibilita' nel disciplinare o valuta ATS/partnership con soggetto ammesso.",
        "fatturato": "Prepara evidenze contabili aggiornate o partnership con capofila piu' solido.",
        "anzianita": "Controlla il requisito alla data di scadenza, includendo visura e data avvio attivita'.",
    }
    for item in items:
        if not item.get("suggerimento"):
            item["suggerimento"] = fallback_suggestions.get(
                item.get("categoria", ""),
                "Verifica il requisito nel disciplinare e prepara azione correttiva.",
            )

    priority = {"rosso": 0, "giallo": 1, "verde": 2}
    items.sort(key=lambda g: priority.get(g.get("semaforo"), 3))
    return items

