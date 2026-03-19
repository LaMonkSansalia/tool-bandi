"""
Tests for engine/eligibility/hard_stops.py
All tests use a mock CompanyProfile (no file I/O).
"""
from dataclasses import dataclass
from engine.eligibility.hard_stops import check_hard_stops


@dataclass
class MockProfile:
    """Minimal CompanyProfile substitute for testing."""
    denominazione: str = "Impresa Test"
    forma_giuridica: str = "impresa individuale"
    fatturato_max: float = 85_000.0
    dipendenti: int = 1
    anni_attivita: int = 3
    zona_zes: bool = True
    zona_mezzogiorno: bool = True
    ateco: str = "62.01.00"
    under_36: bool = True
    regione: str = "Sicilia"
    soa: bool = False

    @property
    def forma_giuridica_keywords(self):
        return ["impresa_individuale", "micro_impresa", "pmi"]

    @property
    def regione_match_terms(self):
        terms = ["tutte", "tutte le regioni", "tutto il territorio nazionale", self.regione.lower()]
        if self.zona_mezzogiorno:
            terms.extend(["sud", "mezzogiorno", "sud italia"])
        return terms


PROFILE = MockProfile()


class TestFatturato:
    def test_excluded_when_fatturato_too_high(self):
        bando = {"fatturato_minimo": 200_000}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True
        assert "fatturato" in result.reason.lower()

    def test_passes_when_fatturato_ok(self):
        bando = {"fatturato_minimo": 50_000}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_fatturato_none(self):
        bando = {"fatturato_minimo": None}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_yellow_flag_when_fatturato_unparsable(self):
        bando = {"fatturato_minimo": "non_numero"}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False
        assert len(result.yellow_flags) > 0

    def test_exact_boundary_passes(self):
        """Exactly at profile max passes (strictly greater than triggers exclusion)."""
        bando = {"fatturato_minimo": PROFILE.fatturato_max}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False


class TestDipendenti:
    def test_excluded_when_dipendenti_too_high(self):
        bando = {"dipendenti_minimi": 10}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True
        assert "dipendenti" in result.reason.lower()

    def test_passes_when_dipendenti_ok(self):
        bando = {"dipendenti_minimi": 1}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_no_requirement(self):
        bando = {}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False


class TestSOA:
    def test_excluded_when_soa_required(self):
        bando = {"soa_richiesta": True}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True
        assert "SOA" in result.reason

    def test_passes_when_soa_not_required(self):
        bando = {"soa_richiesta": False}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_soa_none(self):
        bando = {}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False


class TestFormaGiuridica:
    def test_excluded_when_only_srl_required(self):
        bando = {"tipo_beneficiario": ["srl_obbligatoria"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True

    def test_passes_when_tutti_ammessi(self):
        bando = {"tipo_beneficiario": ["tutti"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_impresa_individuale_explicit(self):
        bando = {"tipo_beneficiario": ["impresa_individuale"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_yellow_flag_ambiguous_beneficiary(self):
        bando = {"tipo_beneficiario": ["cooperative"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False  # not hard excluded
        assert len(result.yellow_flags) > 0

    def test_passes_empty_tipo(self):
        bando = {"tipo_beneficiario": []}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False


class TestGeografia:
    def test_excluded_when_only_north_admitted(self):
        bando = {"regioni_ammesse": ["Lombardia", "Veneto", "Piemonte"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True
        assert "Sicilia" in result.reason

    def test_passes_when_sicilia_explicit(self):
        bando = {"regioni_ammesse": ["Sicilia"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_nazionale(self):
        bando = {"regioni_ammesse": ["tutto il territorio nazionale"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_mezzogiorno(self):
        bando = {"regioni_ammesse": ["Mezzogiorno"]}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_passes_when_no_geo_restriction(self):
        bando = {"regioni_ammesse": []}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False


class TestAnzianita:
    def test_excluded_when_too_new(self):
        """Profile has 3 anni_attivita, bando requires 5."""
        bando = {"anzianita_minima_anni": 5}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True

    def test_passes_when_old_enough(self):
        bando = {"anzianita_minima_anni": 2}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False

    def test_yellow_flag_when_borderline(self):
        bando = {"anzianita_minima_anni": 3}  # exact match
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False
        assert len(result.yellow_flags) > 0

    def test_passes_when_none(self):
        bando = {"anzianita_minima_anni": None}
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False


class TestMultipleHardStops:
    def test_first_stop_wins(self):
        """When multiple hard stops are triggered, the first one encountered wins."""
        bando = {
            "fatturato_minimo": 999_000,  # first check, fails
            "soa_richiesta": True,         # also fails, but fatturato checked first
        }
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is True
        assert "fatturato" in result.reason.lower()

    def test_all_pass_no_exclusion(self):
        bando = {
            "fatturato_minimo": 10_000,
            "dipendenti_minimi": 1,
            "soa_richiesta": False,
            "tipo_beneficiario": ["tutti"],
            "regioni_ammesse": ["Sicilia"],
            "anzianita_minima_anni": 1,
        }
        result = check_hard_stops(bando, PROFILE)
        assert result.excluded is False
        assert result.yellow_flags == []
