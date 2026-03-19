"""
Tests for engine/eligibility/gap_analyzer.py
"""
from dataclasses import dataclass

from engine.eligibility.gap_analyzer import analyze_gaps


@dataclass
class MockProfile:
    fatturato_max: float = 85_000.0
    dipendenti: int = 0
    anni_attivita: int = 3
    data_inizio: str = "26/01/2023"
    forma_giuridica: str = "impresa individuale"
    iso_9001: bool = False
    iso_27001: bool = False
    soa: bool = False

    @property
    def forma_giuridica_keywords(self):
        return ["impresa_individuale", "micro_impresa", "pmi"]


class TestCertificationGaps:
    def test_iso_9001_missing_is_recoverable_gap(self):
        profile = MockProfile(iso_9001=False)
        result = analyze_gaps({"certificazioni_richieste": ["ISO 9001"]}, profile)
        assert any(g.semaforo == "giallo" for g in result.gaps)
        assert any("non certificata" in g.descrizione for g in result.gaps)

    def test_iso_9001_present_is_not_reported_as_missing(self):
        profile = MockProfile(iso_9001=True)
        result = analyze_gaps({"certificazioni_richieste": ["ISO 9001"]}, profile)
        assert any(g.semaforo == "verde" for g in result.gaps)
        assert any("gia' presente" in g.descrizione for g in result.gaps)
        assert not any("non certificata" in g.descrizione for g in result.gaps)

    def test_iso_27001_present_is_not_reported_as_missing(self):
        profile = MockProfile(iso_27001=True)
        result = analyze_gaps({"certificazioni_richieste": ["ISO 27001"]}, profile)
        assert any(g.semaforo == "verde" for g in result.gaps)
        assert any("gia' presente" in g.descrizione for g in result.gaps)


class TestFallbackGap:
    def test_no_gaps_returns_positive_informational_item(self):
        result = analyze_gaps({}, MockProfile())
        assert len(result.gaps) == 1
        assert result.gaps[0].semaforo == "verde"
        assert "Nessun gap rilevato" in result.gaps[0].descrizione
