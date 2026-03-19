"""
Gap analyzer — identifies requirements not met but not immediately excluding.
Helps the user understand what's missing and if gaps are recoverable.
No DB dependency — pure Python logic.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from engine.eligibility.rules import get_profile, CompanyProfile


class GapType(str, Enum):
    BLOCKING   = "bloccante"       # blocks application — but wasn't a hard stop (edge case)
    RECOVERABLE= "recuperabile"    # can be fixed before deadline
    INFORMATIONAL = "informativo"  # useful to know, not blocking


@dataclass
class Gap:
    tipo: GapType
    categoria: str          # certificazione | anzianita | fatturato | geo | giuridica | altro
    descrizione: str        # human-readable in Italian (will appear in Streamlit)
    suggerimento: str       # what to do about it
    semaforo: str           # rosso | giallo | verde


@dataclass
class GapAnalysisResult:
    gaps: list[Gap]

    @property
    def blocking(self) -> list[Gap]:
        return [g for g in self.gaps if g.tipo == GapType.BLOCKING]

    @property
    def recoverable(self) -> list[Gap]:
        return [g for g in self.gaps if g.tipo == GapType.RECOVERABLE]

    @property
    def informational(self) -> list[Gap]:
        return [g for g in self.gaps if g.tipo == GapType.INFORMATIONAL]

    @property
    def semaforo_globale(self) -> str:
        if self.blocking:
            return "rosso"
        if self.recoverable:
            return "giallo"
        return "verde"


def _has_certification(profile: CompanyProfile, cert_text: str) -> bool:
    """Return True when the profile already has the requested certification."""
    cert_lower = cert_text.lower()
    if "9001" in cert_lower:
        return bool(getattr(profile, "iso_9001", False))
    if "27001" in cert_lower:
        return bool(getattr(profile, "iso_27001", False))
    if "soa" in cert_lower:
        return bool(getattr(profile, "soa", False))
    return False


def analyze_gaps(bando: dict, profile: CompanyProfile | None = None) -> GapAnalysisResult:
    """
    Analyze gaps between bando requirements and company profile.
    Called AFTER hard_stops passes (bando is not excluded).

    Args:
        bando: parsed bando dict
        profile: CompanyProfile singleton

    Returns:
        GapAnalysisResult with categorized gaps and traffic-light semaforo
    """
    if profile is None:
        profile = get_profile()

    gaps: list[Gap] = []

    # ── ISO 9001 ──────────────────────────────────────────────────────────────
    certificazioni = bando.get("certificazioni_richieste") or []
    for cert in certificazioni:
        cert_lower = cert.lower()
        if "9001" in cert_lower or "iso 9001" in cert_lower:
            if _has_certification(profile, cert):
                gaps.append(Gap(
                    tipo=GapType.INFORMATIONAL,
                    categoria="certificazione",
                    descrizione="Bando richiede ISO 9001 — certificazione gia' presente",
                    suggerimento="Allega attestato ISO 9001 aggiornato nella documentazione.",
                    semaforo="verde",
                ))
            else:
                gaps.append(Gap(
                    tipo=GapType.RECOVERABLE,
                    categoria="certificazione",
                    descrizione="Bando richiede ISO 9001 — impresa non certificata",
                    suggerimento="ISO 9001 ottenibile in 3-6 mesi (~2.000-5.000€). Valutare se deadline lo consente.",
                    semaforo="giallo",
                ))
        elif "27001" in cert_lower:
            if _has_certification(profile, cert):
                gaps.append(Gap(
                    tipo=GapType.INFORMATIONAL,
                    categoria="certificazione",
                    descrizione="Bando richiede ISO 27001 — certificazione gia' presente",
                    suggerimento="Allega attestato ISO 27001 aggiornato nella documentazione.",
                    semaforo="verde",
                ))
            else:
                gaps.append(Gap(
                    tipo=GapType.RECOVERABLE,
                    categoria="certificazione",
                    descrizione="Bando richiede ISO 27001 — impresa non certificata",
                    suggerimento="ISO 27001 richiede 6-12 mesi. Difficilmente recuperabile per bando imminente.",
                    semaforo="giallo",
                ))
        else:
            gaps.append(Gap(
                tipo=GapType.INFORMATIONAL,
                categoria="certificazione",
                descrizione=f"Certificazione richiesta: {cert} — verificare se posseduta",
                suggerimento=f"Verificare manualmente se l'impresa possiede '{cert}'.",
                semaforo="giallo",
            ))

    # ── Fatturato borderline ──────────────────────────────────────────────────
    fatturato_min = bando.get("fatturato_minimo")
    if fatturato_min is not None:
        try:
            fatturato_min = float(fatturato_min)
            ratio = fatturato_min / profile.fatturato_max
            if 0.7 <= ratio <= 1.0:  # within 30% of cap
                gaps.append(Gap(
                    tipo=GapType.INFORMATIONAL,
                    categoria="fatturato",
                    descrizione=f"Fatturato minimo richiesto ({fatturato_min:,.0f}€) è {ratio:.0%} del cap forfettario",
                    suggerimento="Verificare l'effettivo fatturato dell'esercizio corrente. Se vicino al requisito, documentare accuratamente.",
                    semaforo="giallo",
                ))
        except (ValueError, TypeError):
            pass

    # ── Anzianità borderline ──────────────────────────────────────────────────
    anzianita_min = bando.get("anzianita_minima_anni")
    if anzianita_min is not None:
        try:
            anzianita_min = int(anzianita_min)
            if anzianita_min == profile.anni_attivita:
                gaps.append(Gap(
                    tipo=GapType.INFORMATIONAL,
                    categoria="anzianita",
                    descrizione=f"Anzianità borderline: bando richiede {anzianita_min} anni, impresa attiva esattamente da {profile.anni_attivita}",
                    suggerimento=f"Verificare se la data di inizio attivita' ({profile.data_inizio}) soddisfa il requisito alla data di scadenza del bando.",
                    semaforo="giallo",
                ))
        except (ValueError, TypeError):
            pass

    # ── Dipendenti (se richiesti come opzionali/bonus) ────────────────────────
    dipendenti_min = bando.get("dipendenti_minimi")
    if dipendenti_min is not None:
        try:
            dipendenti_min = int(dipendenti_min)
            if dipendenti_min == 0:  # explicitly 0 is OK
                pass
            # if > 0 it would have been caught by hard stops
        except (ValueError, TypeError):
            pass

    # ── Tipo beneficiario ambiguo ─────────────────────────────────────────────
    tipo_ben = bando.get("tipo_beneficiario") or []
    if tipo_ben:
        normalized = {t.lower().replace(" ", "_") for t in tipo_ben}
        our_keywords = profile.forma_giuridica_keywords + ["tutti", "tutte_le_imprese"]
        admits_our_form = any(t in normalized for t in our_keywords)
        if not admits_our_form:
            gaps.append(Gap(
                tipo=GapType.RECOVERABLE,
                categoria="giuridica",
                descrizione=f"Tipo beneficiario non include esplicitamente '{profile.forma_giuridica}': {tipo_ben}",
                suggerimento=f"Leggere il disciplinare per verificare se '{profile.forma_giuridica}' e' ammessa tra i beneficiari.",
                semaforo="giallo",
            ))

    # ── Budget troppo basso per essere utile ─────────────────────────────────
    importo_max = bando.get("importo_max")
    if importo_max is not None:
        try:
            if float(importo_max) < 1000:
                gaps.append(Gap(
                    tipo=GapType.INFORMATIONAL,
                    categoria="altro",
                    descrizione=f"Importo massimo molto basso: {importo_max}€",
                    suggerimento="Valutare se il rapporto effort/beneficio è favorevole.",
                    semaforo="giallo",
                ))
        except (ValueError, TypeError):
            pass

    # ── Nessun gap trovato ────────────────────────────────────────────────────
    if not gaps:
        gaps.append(Gap(
            tipo=GapType.INFORMATIONAL,
            categoria="altro",
            descrizione="Nessun gap rilevato — profilo compatibile con i requisiti del bando",
            suggerimento="Procedere con la preparazione della documentazione.",
            semaforo="verde",
        ))

    return GapAnalysisResult(gaps=gaps)
