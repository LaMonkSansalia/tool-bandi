"""
Compatibility scorer — calculates 0-100 score for bandi that pass hard stops.
No DB dependency — pure Python logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from engine.eligibility.rules import get_profile, CompanyProfile


SCORE_RULES = [
    # (rule_name, points, description)
    ("sicilia_ammessa",        15, "Sicilia / Sud / Mezzogiorno ammessi"),
    ("ateco_ict",              20, "ATECO ICT (62.x) prioritario PNRR"),
    ("zona_zes",               10, "Zona ZES — bonus automatico"),
    ("under_36",               10, "Titolare under 36 — bandi giovani imprenditori"),
    ("nuova_impresa",          10, "Impresa attiva da meno di 5 anni"),
    ("impresa_individuale_ok",  5, "Impresa individuale esplicitamente ammessa"),
    ("no_certificazioni",       5, "Nessuna certificazione obbligatoria richiesta"),
    ("micro_impresa_ok",        5, "Micro-impresa ammessa"),
    ("pnrr_digitalizzazione",  10, "Bando PNRR digitalizzazione / ICT"),
    ("importo_adeguato",       10, "Importo max > 5.000€ (significativo)"),
]

MAX_SCORE = sum(pts for _, pts, _ in SCORE_RULES)  # 100


@dataclass
class ScoreBreakdown:
    rule: str
    points: int
    description: str
    matched: bool


@dataclass
class ScoreResult:
    score: int                              # 0-100
    breakdown: list[ScoreBreakdown] = field(default_factory=list)
    notification_worthy: bool = False       # score > SCORE_NOTIFICATION_THRESHOLD
    borderline: bool = False                # 40 <= score <= threshold


def score_bando(
    bando: dict,
    profile: CompanyProfile | None = None,
    notification_threshold: int = 60,
) -> ScoreResult:
    """
    Calculate compatibility score for a bando that passed hard stops.

    Args:
        bando: dict with parsed bando fields
        profile: CompanyProfile singleton
        notification_threshold: min score to trigger Telegram notification

    Returns:
        ScoreResult with score 0-100 and per-rule breakdown
    """
    if profile is None:
        profile = get_profile()

    raw_score = 0
    breakdown: list[ScoreBreakdown] = []

    regioni = {r.lower().strip() for r in (bando.get("regioni_ammesse") or [])}
    tipo_ben = {t.lower().replace(" ", "_") for t in (bando.get("tipo_beneficiario") or [])}
    certificazioni = bando.get("certificazioni_richieste") or []
    ateco_bando = {a.strip() for a in (bando.get("settori_ateco") or [])}
    portale = (bando.get("portale") or "").lower()
    titolo = (bando.get("titolo") or "").lower()
    importo_max = bando.get("importo_max") or 0

    def add(rule: str, points: int, desc: str, matched: bool):
        nonlocal raw_score
        if matched:
            raw_score += points
        breakdown.append(ScoreBreakdown(rule=rule, points=points, description=desc, matched=matched))

    # ── Sicilia / Sud ammessi ────────────────────────────────────────────────
    sicilia_ok = not regioni or any(r in regioni for r in (
        "tutte", "tutto il territorio nazionale",
        "sicilia", "sud", "mezzogiorno", "sud italia",
    ))
    add("sicilia_ammessa", 15, "Sicilia / Sud / Mezzogiorno ammessi", sicilia_ok)

    # ── ATECO ICT ────────────────────────────────────────────────────────────
    ateco_match = (
        not ateco_bando  # bando non specifica → aperto a tutti
        or any(a.startswith(("62.", "63.")) for a in ateco_bando)
        or profile.ateco in ateco_bando
    )
    add("ateco_ict", 20, "ATECO ICT (62.x) prioritario PNRR", ateco_match)

    # ── Zona ZES ─────────────────────────────────────────────────────────────
    zes_keywords = {"zes", "zona economica speciale", "mezzogiorno", "sud"}
    zes_ok = profile.zona_zes and any(kw in titolo or kw in portale for kw in zes_keywords)
    # also check if bando explicitly mentions ZES
    metadata = bando.get("metadata") or {}
    if metadata.get("zona_zes"):
        zes_ok = True
    add("zona_zes", 10, "Zona ZES — bonus automatico", zes_ok)

    # ── Under 36 ─────────────────────────────────────────────────────────────
    under36_keywords = {"under 35", "under 36", "giovani", "giovane imprenditore", "under35"}
    under36_ok = profile.under_36 and any(kw in titolo for kw in under36_keywords)
    add("under_36", 10, "Titolare under 36 — bandi giovani imprenditori", under36_ok)

    # ── Nuova impresa (< 5 anni) ─────────────────────────────────────────────
    nuova_keywords = {"nuova impresa", "startup", "nuove imprese", "neo-impresa", "neo impresa"}
    nuova_ok = profile.anni_attivita < 5 and any(kw in titolo for kw in nuova_keywords)
    add("nuova_impresa", 10, "Impresa attiva da meno di 5 anni", nuova_ok)

    # ── Impresa individuale esplicitamente ammessa ───────────────────────────
    ind_ok = any(t in tipo_ben for t in (
        "impresa_individuale", "impresa_individuale_e_libero_professionista",
        "tutti", "tutte_le_imprese",
    ))
    add("impresa_individuale_ok", 5, "Impresa individuale esplicitamente ammessa", ind_ok)

    # ── Nessuna certificazione obbligatoria ──────────────────────────────────
    no_cert_ok = len(certificazioni) == 0
    add("no_certificazioni", 5, "Nessuna certificazione obbligatoria richiesta", no_cert_ok)

    # ── Micro-impresa ammessa ─────────────────────────────────────────────────
    micro_ok = any(t in tipo_ben for t in ("micro_impresa", "pmi", "tutti", "tutte_le_imprese")) or not tipo_ben
    add("micro_impresa_ok", 5, "Micro-impresa ammessa", micro_ok)

    # ── PNRR / Digitalizzazione ───────────────────────────────────────────────
    pnrr_keywords = {"pnrr", "digitalizzazione", "digitale", "digital", "ict", "innovazione digitale"}
    pnrr_ok = any(kw in titolo for kw in pnrr_keywords) or portale in ("padigitale", "pa_digitale")
    add("pnrr_digitalizzazione", 10, "Bando PNRR digitalizzazione / ICT", pnrr_ok)

    # ── Importo adeguato ──────────────────────────────────────────────────────
    try:
        importo_ok = float(importo_max) > 5000
    except (TypeError, ValueError):
        importo_ok = False
    add("importo_adeguato", 10, "Importo max > 5.000€ (significativo)", importo_ok)

    # ── Normalize to 0-100 ────────────────────────────────────────────────────
    score = min(100, round(raw_score * 100 / MAX_SCORE))

    return ScoreResult(
        score=score,
        breakdown=breakdown,
        notification_worthy=score > notification_threshold,
        borderline=40 <= score <= notification_threshold,
    )
