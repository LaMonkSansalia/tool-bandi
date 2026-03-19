"""
Eligibility rules — company profile loading.
Supports both JSON file (legacy) and DB-based project profiles.
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field


PROFILE_PATH = Path(__file__).parent.parent.parent / "context" / "company_profile.json"

# Mapping forma_giuridica → keywords for beneficiary matching
_FORMA_GIURIDICA_MAP = {
    "impresa individuale": [
        "impresa_individuale", "impresa_individuale_e_libero_professionista",
        "micro_impresa", "pmi",
    ],
    "associazione": ["associazione", "ente_no_profit", "associazione_culturale"],
    "pro loco": ["pro_loco", "associazione", "ente_no_profit"],
    "fondazione": ["fondazione", "ente_no_profit"],
    "cooperativa": ["cooperativa", "societa_cooperativa", "pmi"],
    "srl": ["srl", "societa_di_capitali", "pmi"],
    "srls": ["srls", "srl", "societa_di_capitali", "pmi"],
    "spa": ["spa", "societa_di_capitali"],
    "snc": ["snc", "societa_di_persone", "pmi"],
    "sas": ["sas", "societa_di_persone", "pmi"],
    "ente pubblico": ["ente_pubblico", "pubblica_amministrazione"],
    "comune": ["comune", "ente_pubblico", "pubblica_amministrazione"],
}


@dataclass
class HardStop:
    constraint: str
    reason: str
    threshold: float | None = None
    exclusions: list[str] = field(default_factory=list)
    bool_value: bool | None = None


@dataclass
class YellowFlag:
    constraint: str
    note: str
    years: int | None = None


@dataclass
class CompanyProfile:
    # Anagrafica
    denominazione: str
    partita_iva: str
    forma_giuridica: str
    regime_fiscale: str

    # Dimensione
    dipendenti: int
    fatturato_max: float
    micro_impresa: bool

    # Sede
    regione: str
    comune: str
    zona_zes: bool
    zona_mezzogiorno: bool

    # Attivita
    ateco: str
    anni_attivita: int
    data_inizio: str

    # Certificazioni
    soa: bool
    iso_9001: bool
    iso_27001: bool

    # Eligibility
    hard_stops: list[HardStop]
    yellow_flags: list[YellowFlag]
    vantaggi: list[str]

    # Optional: birth year for age-based checks (default: not set)
    anno_nascita: int | None = None

    @property
    def under_36(self) -> bool:
        from datetime import date
        if self.anno_nascita is None:
            return False
        return (date.today().year - self.anno_nascita) < 36

    @property
    def ateco_ict(self) -> bool:
        return self.ateco.startswith(("62.", "63."))

    @property
    def forma_giuridica_keywords(self) -> list[str]:
        """Map forma_giuridica to beneficiary matching keywords."""
        key = self.forma_giuridica.lower().strip()
        if key in _FORMA_GIURIDICA_MAP:
            return _FORMA_GIURIDICA_MAP[key]
        return [key.replace(" ", "_")]

    @property
    def regione_match_terms(self) -> list[str]:
        """Region terms that should match for geographic eligibility."""
        terms = [
            "tutte", "tutte le regioni", "tutto il territorio nazionale",
            self.regione.lower(),
        ]
        if self.zona_mezzogiorno:
            terms.extend(["sud", "mezzogiorno", "sud italia"])
        return terms


def _parse_profile_data(data: dict) -> CompanyProfile:
    """Parse a company_profile.json-structured dict into CompanyProfile."""
    constraints = data.get("eligibility_constraints", {})

    hard_stops = []
    for hs in constraints.get("HARD_STOP", []):
        c = hs["constraint"]
        if c in ("fatturato_minimo", "dipendenti_minimi"):
            hard_stops.append(HardStop(
                constraint=c,
                reason=hs["motivo"],
                threshold=hs.get("soglia_esclusione"),
            ))
        elif c == "forma_giuridica":
            hard_stops.append(HardStop(
                constraint=c,
                reason=hs["motivo"],
                exclusions=hs.get("esclusioni", []),
            ))
        elif c == "soa_obbligatoria":
            hard_stops.append(HardStop(
                constraint=c,
                reason=hs["motivo"],
                bool_value=hs.get("valore", False),
            ))

    yellow_flags = []
    for yf in constraints.get("YELLOW_FLAG", []):
        yellow_flags.append(YellowFlag(
            constraint=yf["constraint"],
            note=yf["nota"],
            years=yf.get("anni"),
        ))

    # Extract birth year from anagrafica if available
    anno_nascita = None
    data_nascita = data.get("anagrafica", {}).get("data_nascita")
    if data_nascita and isinstance(data_nascita, str):
        # Format: DD/MM/YYYY
        try:
            anno_nascita = int(data_nascita.split("/")[-1])
        except (ValueError, IndexError):
            pass

    anagrafica = data.get("anagrafica", {})
    dimensione = data.get("dimensione", {})
    sede = data.get("sede", {})
    attivita = data.get("attivita", {})
    certificazioni = data.get("certificazioni", {})

    return CompanyProfile(
        denominazione=anagrafica.get("denominazione", ""),
        partita_iva=anagrafica.get("partita_iva", ""),
        forma_giuridica=anagrafica.get("forma_giuridica", ""),
        regime_fiscale=anagrafica.get("regime_fiscale", ""),
        dipendenti=dimensione.get("dipendenti", 0),
        fatturato_max=dimensione.get("fatturato_stimato_max", 0),
        micro_impresa=dimensione.get("micro_impresa", True),
        regione=sede.get("regione", ""),
        comune=sede.get("comune", ""),
        zona_zes=sede.get("zona_zes", False),
        zona_mezzogiorno=sede.get("zona_mezzogiorno", False),
        ateco=attivita.get("ateco_2025", attivita.get("ateco", "")),
        anni_attivita=attivita.get("anni_attivita", 0),
        data_inizio=attivita.get("data_inizio", ""),
        soa=certificazioni.get("soa") is not None,
        iso_9001=certificazioni.get("iso_9001", False),
        iso_27001=certificazioni.get("iso_27001", False),
        hard_stops=hard_stops,
        yellow_flags=yellow_flags,
        vantaggi=constraints.get("VANTAGGI", []),
        anno_nascita=anno_nascita,
    )


def load_profile() -> CompanyProfile:
    """Load and parse company_profile.json into a typed object (legacy)."""
    with open(PROFILE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return _parse_profile_data(data)


def load_profile_from_dict(data: dict) -> CompanyProfile:
    """Parse a profile dict (from DB JSONB) into CompanyProfile."""
    return _parse_profile_data(data)


# ── Profile cache (supports multiple projects) ─────────────────────────────────

_profiles: dict[int | None, CompanyProfile] = {}


def get_profile(project_id: int | None = None) -> CompanyProfile:
    """
    Get a CompanyProfile by project_id.
    - project_id=None: load from JSON file (legacy/default behavior)
    - project_id=int: load from DB via ProjectManager
    """
    if project_id in _profiles:
        return _profiles[project_id]

    if project_id is None:
        profile = load_profile()
    else:
        from engine.projects.manager import get_project_profile
        data = get_project_profile(project_id)
        if data is None:
            raise ValueError(f"Project {project_id} not found")
        profile = load_profile_from_dict(data)

    _profiles[project_id] = profile
    return profile


def get_profile_for_soggetto(soggetto_id: int) -> CompanyProfile:
    """
    Load CompanyProfile from soggetti.profilo (DB) by soggetto_id.
    Used by rivaluta_singolo after migration 008.
    Falls back to JSON singleton if soggetto not found.
    """
    cache_key = f"soggetto_{soggetto_id}"
    if cache_key in _profiles:
        return _profiles[cache_key]  # type: ignore[index]

    from engine.projects.manager import get_soggetto_profile
    data = get_soggetto_profile(soggetto_id)
    if data is None:
        raise ValueError(f"Soggetto {soggetto_id} not found or inactive")

    profile = load_profile_from_dict(data)
    _profiles[cache_key] = profile  # type: ignore[index]
    return profile


def clear_profile_cache(project_id: int | None = None):
    """Clear cached profile(s). Call after profile updates."""
    if project_id is None:
        _profiles.clear()
    else:
        _profiles.pop(project_id, None)
