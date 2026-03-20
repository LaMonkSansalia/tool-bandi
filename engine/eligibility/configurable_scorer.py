"""
Configurable scorer — data-driven scoring engine.
Interprets scoring_rules JSONB from the projects table.
Each rule has a 'type' that maps to a handler function.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from engine.eligibility.rules import CompanyProfile


@dataclass
class ScoreBreakdown:
    rule: str
    points: int
    description: str
    matched: bool


@dataclass
class ScoreResult:
    score: int
    breakdown: list[ScoreBreakdown] = field(default_factory=list)
    notification_worthy: bool = False
    borderline: bool = False


# ── Rule handlers ───────────────────────────────────────────────────────────────
# Each returns True if the rule matches (points awarded).
# Signature: (bando: dict, profile: CompanyProfile, config: dict) -> bool


def _eval_region_match(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if bando's regioni_ammesse includes the project's region."""
    regioni = {r.lower().strip() for r in (bando.get("regioni_ammesse") or [])}
    if not regioni:
        return True  # no restriction = open to all
    match_terms = profile.regione_match_terms
    return any(r in regioni for r in match_terms)


def _eval_ateco_match(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if bando's settori_ateco includes the project's ATECO."""
    ateco_bando = {a.strip() for a in (bando.get("settori_ateco") or [])}
    if not ateco_bando:
        return config.get("match_empty", True)
    # Direct match
    if profile.ateco in ateco_bando:
        return True
    # Prefix match (e.g., profile 62.20.10 matches bando 62.)
    prefix = profile.ateco[:3]  # e.g., "62."
    return any(a.startswith(prefix) for a in ateco_bando)


def _eval_keyword_in_title(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if any configured keywords appear in bando title."""
    titolo = (bando.get("titolo") or "").lower()
    portale = (bando.get("portale") or "").lower()
    raw = (bando.get("raw_text") or "")[:2000].lower()
    text = f"{titolo} {portale} {raw}"
    keywords = config.get("keywords", [])
    return any(kw in text for kw in keywords)


def _eval_keyword_and_profile(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check keyword match AND a profile boolean field is True."""
    profile_field = config.get("profile_field", "")
    if not getattr(profile, profile_field, False):
        return False
    titolo = (bando.get("titolo") or "").lower()
    portale = (bando.get("portale") or "").lower()
    text = f"{titolo} {portale}"
    keywords = config.get("keywords", [])
    # Also check metadata
    metadata = bando.get("metadata") or {}
    if metadata.get(profile_field):
        return True
    return any(kw in text for kw in keywords)


def _eval_importo_min(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if importo_max exceeds a minimum threshold."""
    min_importo = config.get("min_importo", 5000)
    try:
        return float(bando.get("importo_max") or 0) > min_importo
    except (TypeError, ValueError):
        return False


def _eval_beneficiary_match(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if tipo_beneficiario includes accepted types."""
    tipo_ben = {t.lower().replace(" ", "_") for t in (bando.get("tipo_beneficiario") or [])}
    if not tipo_ben:
        return True  # no restriction
    accepted = config.get("accepted_types", [])
    if not accepted:
        # Fall back to profile's forma_giuridica_keywords
        accepted = profile.forma_giuridica_keywords + ["tutti", "tutte_le_imprese"]
    return any(t in tipo_ben for t in accepted)


def _eval_no_certs(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if no certifications are required."""
    certificazioni = bando.get("certificazioni_richieste") or []
    return len(certificazioni) == 0


def _eval_age_check(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if profile owner is under a certain age AND keywords match."""
    if not profile.under_36:
        return False
    titolo = (bando.get("titolo") or "").lower()
    keywords = config.get("keywords", ["under 35", "under 36", "giovani"])
    return any(kw in titolo for kw in keywords)


def _eval_company_age(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if company is younger than max_years AND keywords match."""
    max_years = config.get("max_years", 5)
    if profile.anni_attivita >= max_years:
        return False
    titolo = (bando.get("titolo") or "").lower()
    keywords = config.get("keywords", ["nuova impresa", "startup"])
    return any(kw in titolo for kw in keywords)


def _eval_qualifica_match(bando: dict, profile: CompanyProfile, config: dict) -> bool:
    """Check if soggetto has qualifiche premiali matching bando keywords.

    Config:
        qualifica: str — qualifica to check (e.g. "startup_innovativa")
        keywords: list[str] — bando title/text keywords that trigger the bonus
    """
    qualifica = config.get("qualifica", "")
    if qualifica not in (profile.qualifiche or []):
        return False
    # Check if bando title/text mentions relevant keywords
    titolo = (bando.get("titolo") or "").lower()
    raw = (bando.get("raw_text") or "")[:2000].lower()
    tipo_ben = " ".join(t.lower() for t in (bando.get("tipo_beneficiario") or []))
    text = f"{titolo} {tipo_ben} {raw}"
    keywords = config.get("keywords", [])
    if not keywords:
        return True  # qualifica presente, nessun keyword filter
    return any(kw in text for kw in keywords)


# ── Handler registry ────────────────────────────────────────────────────────────

RULE_HANDLERS = {
    "region_match": _eval_region_match,
    "ateco_match": _eval_ateco_match,
    "keyword_in_title": _eval_keyword_in_title,
    "keyword_and_profile": _eval_keyword_and_profile,
    "importo_min": _eval_importo_min,
    "beneficiary_match": _eval_beneficiary_match,
    "no_certifications_required": _eval_no_certs,
    "profile_age_check": _eval_age_check,
    "company_age": _eval_company_age,
    "qualifica_match": _eval_qualifica_match,
}


# ── Main scorer ─────────────────────────────────────────────────────────────────

def score_bando_configurable(
    bando: dict,
    profile: CompanyProfile,
    scoring_rules: dict,
    notification_threshold: int = 60,
) -> ScoreResult:
    """
    Calculate compatibility score using configurable rules from DB.

    Args:
        bando: parsed bando dict
        profile: CompanyProfile for the project
        scoring_rules: JSONB from projects.scoring_rules
        notification_threshold: min score to trigger notification

    Returns:
        ScoreResult with normalized 0-100 score and breakdown
    """
    rules = scoring_rules.get("rules", [])
    max_score = sum(r["points"] for r in rules)
    raw_score = 0
    breakdown: list[ScoreBreakdown] = []

    for rule in rules:
        handler = RULE_HANDLERS.get(rule.get("type"))
        config = rule.get("config", {})

        if handler:
            matched = handler(bando, profile, config)
        else:
            matched = False

        if matched:
            raw_score += rule["points"]

        breakdown.append(ScoreBreakdown(
            rule=rule["name"],
            points=rule["points"],
            description=rule.get("description", ""),
            matched=matched,
        ))

    normalized = min(100, round(raw_score * 100 / max_score)) if max_score > 0 else 0

    return ScoreResult(
        score=normalized,
        breakdown=breakdown,
        notification_worthy=normalized > notification_threshold,
        borderline=40 <= normalized <= notification_threshold,
    )
