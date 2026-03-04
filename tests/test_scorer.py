"""
Tests for engine/eligibility/scorer.py
"""
import pytest
from dataclasses import dataclass
from engine.eligibility.scorer import score_bando, ScoreResult, MAX_SCORE


@dataclass
class MockProfile:
    zona_zes: bool = True
    under_36: bool = True
    anni_attivita: int = 3
    ateco: str = "62.01.00"
    regione: str = "Sicilia"
    dipendenti: int = 1
    fatturato_max: float = 85_000.0


PROFILE = MockProfile()


class TestScoreRange:
    def test_score_between_0_and_100(self):
        bando = {}
        result = score_bando(bando, PROFILE)
        assert 0 <= result.score <= 100

    def test_max_score_definition(self):
        assert MAX_SCORE == 100

    def test_empty_bando_has_score(self):
        result = score_bando({}, PROFILE)
        assert isinstance(result.score, int)

    def test_breakdown_count(self):
        result = score_bando({}, PROFILE)
        assert len(result.breakdown) == 10  # 10 rules defined


class TestNotificationFlag:
    def test_notification_worthy_above_threshold(self):
        # Give a bando that matches many rules
        bando = {
            "regioni_ammesse": ["Sicilia"],
            "settori_ateco": ["62.01.00"],
            "tipo_beneficiario": ["tutti"],
            "titolo": "bando pnrr digitalizzazione",
            "importo_max": 50_000,
        }
        result = score_bando(bando, PROFILE, notification_threshold=60)
        if result.score > 60:
            assert result.notification_worthy is True

    def test_not_notification_worthy_below_threshold(self):
        bando = {
            "regioni_ammesse": ["Lombardia"],  # Sicilia excluded → 0 for sicilia rule
            "settori_ateco": ["01.11"],  # not ICT → 0
            "tipo_beneficiario": ["srl_obbligatoria"],  # not admitting individual
            "titolo": "bando agroalimentare",
            "importo_max": 0,
        }
        result = score_bando(bando, PROFILE, notification_threshold=60)
        if result.score <= 60:
            assert result.notification_worthy is False


class TestIndividualRules:
    def test_sicilia_rule_matched_when_no_region_restriction(self):
        bando = {"regioni_ammesse": []}
        result = score_bando(bando, PROFILE)
        sicilia_rule = next((r for r in result.breakdown if r.rule == "sicilia_ammessa"), None)
        assert sicilia_rule is not None
        assert sicilia_rule.matched is True

    def test_sicilia_rule_matched_with_national(self):
        bando = {"regioni_ammesse": ["tutto il territorio nazionale"]}
        result = score_bando(bando, PROFILE)
        sicilia_rule = next((r for r in result.breakdown if r.rule == "sicilia_ammessa"), None)
        assert sicilia_rule.matched is True

    def test_sicilia_rule_not_matched_north_only(self):
        bando = {"regioni_ammesse": ["Lombardia"]}
        result = score_bando(bando, PROFILE)
        sicilia_rule = next((r for r in result.breakdown if r.rule == "sicilia_ammessa"), None)
        assert sicilia_rule.matched is False

    def test_ateco_ict_matched_no_restriction(self):
        """No ATECO restriction → open to all → matched."""
        bando = {"settori_ateco": []}
        result = score_bando(bando, PROFILE)
        ateco_rule = next((r for r in result.breakdown if r.rule == "ateco_ict"), None)
        assert ateco_rule.matched is True

    def test_ateco_ict_matched_with_ict_code(self):
        bando = {"settori_ateco": ["62.01.00"]}
        result = score_bando(bando, PROFILE)
        ateco_rule = next((r for r in result.breakdown if r.rule == "ateco_ict"), None)
        assert ateco_rule.matched is True

    def test_no_cert_rule(self):
        bando = {"certificazioni_richieste": []}
        result = score_bando(bando, PROFILE)
        cert_rule = next((r for r in result.breakdown if r.rule == "no_certificazioni"), None)
        assert cert_rule.matched is True

    def test_cert_required_fails_no_cert_rule(self):
        bando = {"certificazioni_richieste": ["ISO 9001"]}
        result = score_bando(bando, PROFILE)
        cert_rule = next((r for r in result.breakdown if r.rule == "no_certificazioni"), None)
        assert cert_rule.matched is False

    def test_importo_adeguato_above_5000(self):
        bando = {"importo_max": 10_000}
        result = score_bando(bando, PROFILE)
        imp_rule = next((r for r in result.breakdown if r.rule == "importo_adeguato"), None)
        assert imp_rule.matched is True

    def test_importo_adeguato_below_5000(self):
        bando = {"importo_max": 1_000}
        result = score_bando(bando, PROFILE)
        imp_rule = next((r for r in result.breakdown if r.rule == "importo_adeguato"), None)
        assert imp_rule.matched is False

    def test_importo_adeguato_zero(self):
        bando = {"importo_max": 0}
        result = score_bando(bando, PROFILE)
        imp_rule = next((r for r in result.breakdown if r.rule == "importo_adeguato"), None)
        assert imp_rule.matched is False

    def test_pnrr_keyword_in_title(self):
        bando = {"titolo": "Bando PNRR digitalizzazione PMI"}
        result = score_bando(bando, PROFILE)
        pnrr_rule = next((r for r in result.breakdown if r.rule == "pnrr_digitalizzazione"), None)
        assert pnrr_rule.matched is True

    def test_pnrr_from_padigitale_portale(self):
        bando = {"portale": "padigitale", "titolo": "Bando generico"}
        result = score_bando(bando, PROFILE)
        pnrr_rule = next((r for r in result.breakdown if r.rule == "pnrr_digitalizzazione"), None)
        assert pnrr_rule.matched is True

    def test_under36_requires_keyword_in_title(self):
        """under36 rule requires keyword match in title, not just profile flag."""
        bando = {"titolo": "Bando Giovani Imprenditori Under 36"}
        profile = MockProfile(under_36=True)
        result = score_bando(bando, profile)
        u36_rule = next((r for r in result.breakdown if r.rule == "under_36"), None)
        assert u36_rule.matched is True

    def test_under36_not_matched_without_keyword(self):
        bando = {"titolo": "Bando generico per imprese"}
        profile = MockProfile(under_36=True)
        result = score_bando(bando, profile)
        u36_rule = next((r for r in result.breakdown if r.rule == "under_36"), None)
        assert u36_rule.matched is False

    def test_micro_impresa_matched_when_empty_beneficiary(self):
        """Empty tipo_beneficiario means open to all including micro."""
        bando = {"tipo_beneficiario": []}
        result = score_bando(bando, PROFILE)
        micro_rule = next((r for r in result.breakdown if r.rule == "micro_impresa_ok"), None)
        assert micro_rule.matched is True


class TestScoreConsistency:
    def test_score_increases_with_more_matches(self):
        bad_bando = {
            "regioni_ammesse": ["Lombardia"],
            "settori_ateco": ["01.00"],
            "importo_max": 100,
        }
        good_bando = {
            "regioni_ammesse": ["Sicilia"],
            "settori_ateco": ["62.01"],
            "importo_max": 50_000,
            "titolo": "pnrr digitalizzazione",
            "tipo_beneficiario": ["tutti"],
        }
        bad_result = score_bando(bad_bando, PROFILE)
        good_result = score_bando(good_bando, PROFILE)
        assert good_result.score > bad_result.score

    def test_borderline_flag(self):
        """Scores between 40-60 should be flagged as borderline."""
        # Find a bando that scores around 50
        bando = {
            "regioni_ammesse": ["Sicilia"],
            "importo_max": 10_000,
        }
        result = score_bando(bando, PROFILE, notification_threshold=60)
        if 40 <= result.score <= 60:
            assert result.borderline is True
