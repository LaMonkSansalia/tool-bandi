"""
Hard stop engine — immediate exclusion rules.
Returns exclusion reason or passes through with yellow flags.
No DB dependency — pure Python logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from engine.eligibility.rules import get_profile, CompanyProfile


@dataclass
class HardStopResult:
    excluded: bool
    reason: str | None = None
    yellow_flags: list[str] = field(default_factory=list)


def check_hard_stops(bando: dict, profile: CompanyProfile | None = None) -> HardStopResult:
    """
    Apply hard stop rules to a parsed bando dict.

    Args:
        bando: dict with parsed bando fields (from claude_structurer output)
        profile: CompanyProfile (loaded from company_profile.json). Uses singleton if None.

    Returns:
        HardStopResult with excluded=True and reason if any hard stop triggered,
        or excluded=False with list of yellow flags if passed.
    """
    if profile is None:
        profile = get_profile()

    yellow_flags: list[str] = []

    # ── 1. Fatturato minimo ──────────────────────────────────────────────────
    fatturato_min = bando.get("fatturato_minimo")
    if fatturato_min is not None:
        try:
            fatturato_min = float(fatturato_min)
            if fatturato_min > profile.fatturato_max:
                return HardStopResult(
                    excluded=True,
                    reason=f"Fatturato minimo richiesto ({fatturato_min:,.0f}€) supera il cap forfettario ({profile.fatturato_max:,.0f}€)",
                )
        except (ValueError, TypeError):
            yellow_flags.append("fatturato_minimo non parsabile — verificare manualmente")

    # ── 2. Dipendenti minimi ─────────────────────────────────────────────────
    dipendenti_min = bando.get("dipendenti_minimi")
    if dipendenti_min is not None:
        try:
            dipendenti_min = int(dipendenti_min)
            if dipendenti_min > profile.dipendenti:
                return HardStopResult(
                    excluded=True,
                    reason=f"Bando richiede almeno {dipendenti_min} dipendenti — impresa ha {profile.dipendenti}",
                )
        except (ValueError, TypeError):
            yellow_flags.append("dipendenti_minimi non parsabile — verificare manualmente")

    # ── 3. SOA obbligatoria ──────────────────────────────────────────────────
    soa_richiesta = bando.get("soa_richiesta")
    if soa_richiesta is True and not profile.soa:
        return HardStopResult(
            excluded=True,
            reason=f"Bando richiede attestazione SOA — {profile.denominazione} non certificata",
        )

    # ── 4. Forma giuridica ───────────────────────────────────────────────────
    tipo_beneficiario = bando.get("tipo_beneficiario", [])
    if isinstance(tipo_beneficiario, list) and len(tipo_beneficiario) > 0:
        # Exclusion patterns that rule out impresa individuale
        societario_only = {
            "societa_di_capitali_obbligatoria",
            "srl_obbligatoria",
            "spa_obbligatoria",
            "solo_srl",
            "solo_spa",
            "solo_societa_di_capitali",
        }
        normalized = {t.lower().replace(" ", "_") for t in tipo_beneficiario}

        # Check if our forma giuridica is admitted
        our_keywords = profile.forma_giuridica_keywords + ["tutti", "tutte_le_imprese"]
        admits_our_form = any(t in normalized for t in our_keywords)
        requires_society_only = any(t in societario_only for t in normalized)

        if requires_society_only and not admits_our_form:
            return HardStopResult(
                excluded=True,
                reason=f"Bando ammette solo forme societarie strutturate: {tipo_beneficiario} — {profile.denominazione} è {profile.forma_giuridica}",
            )

        if not admits_our_form and len(normalized) > 0:
            # Ambiguous — yellow flag
            yellow_flags.append(
                f"Forma giuridica: verificare se '{profile.forma_giuridica}' è ammessa tra: {tipo_beneficiario}"
            )

    # ── 5. Area geografica ───────────────────────────────────────────────────
    regioni_ammesse = bando.get("regioni_ammesse", [])
    if isinstance(regioni_ammesse, list) and len(regioni_ammesse) > 0:
        normalized_regioni = {r.lower().strip() for r in regioni_ammesse}
        geo_ok = any(r in normalized_regioni for r in profile.regione_match_terms)
        if not geo_ok:
            return HardStopResult(
                excluded=True,
                reason=f"Bando non aperto a {profile.regione}. Regioni ammesse: {regioni_ammesse}",
            )

    # ── 6. Anzianità minima ──────────────────────────────────────────────────
    anzianita_min = bando.get("anzianita_minima_anni")
    if anzianita_min is not None:
        try:
            anzianita_min = int(anzianita_min)
            if anzianita_min > profile.anni_attivita:
                return HardStopResult(
                    excluded=True,
                    reason=f"Bando richiede {anzianita_min} anni di attività — impresa attiva da {profile.anni_attivita} anni",
                )
            if anzianita_min == profile.anni_attivita:
                yellow_flags.append(
                    f"Anzianità borderline: bando richiede {anzianita_min} anni, impresa attiva esattamente da {profile.anni_attivita} anni"
                )
        except (ValueError, TypeError):
            yellow_flags.append("anzianita_minima_anni non parsabile — verificare manualmente")

    # ── Passed all hard stops ────────────────────────────────────────────────
    return HardStopResult(excluded=False, yellow_flags=yellow_flags)
