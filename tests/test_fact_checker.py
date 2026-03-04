"""
Tests for engine/generators/fact_checker.py
Tests use in-memory source data only (no file I/O).

dspy and content_generator are stubbed to avoid heavy optional deps in test env.
"""
import sys
import types
import pytest
from unittest.mock import patch
from dataclasses import dataclass, field

# Stub out dspy (optional heavy dep) before importing anything from engine.generators
_dspy_stub = types.ModuleType("dspy")
for _attr in ["Signature", "InputField", "OutputField", "LM", "configure", "ChainOfThought", "Predict"]:
    setattr(_dspy_stub, _attr, object)
sys.modules.setdefault("dspy", _dspy_stub)

# Local ClaimRecord matching the real interface (avoids importing content_generator → dspy)
@dataclass
class ClaimRecord:
    claim: str
    source: str
    value_used: str
    verified: bool = False
    verified_at: str | None = None

# Inject stub so fact_checker's `from engine.generators.content_generator import ClaimRecord` resolves
_cg_stub = types.ModuleType("engine.generators.content_generator")
_cg_stub.ClaimRecord = ClaimRecord
sys.modules.setdefault("engine.generators.content_generator", _cg_stub)

from engine.generators.fact_checker import (  # noqa: E402
    _flatten_dict,
    _verify_claim,
    check_claims,
    assert_all_verified,
    FactCheckResult,
    DocumentBlockedError,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_claim(claim="test", source="company_profile.json → field", value="value"):
    return ClaimRecord(claim=claim, source=source, value_used=value)


SAMPLE_SOURCES = {
    "company_profile.json": {
        "anagrafica.denominazione": "La Monica Luciano",
        "anagrafica.partita_iva": "12345678901",
        "dimensione.fatturato_stimato_max": "85000",
        "sede.regione": "Sicilia",
        "attivita.ateco_2025": "62.01.00",
        "attivita.anni_attivita": "3",
    }
}


class TestFlattenDict:
    def test_simple_flat_dict(self):
        d = {"a": "1", "b": "2"}
        result = _flatten_dict(d)
        assert result == {"a": "1", "b": "2"}

    def test_nested_dict(self):
        d = {"level1": {"level2": "value"}}
        result = _flatten_dict(d)
        assert "level1.level2" in result
        assert result["level1.level2"] == "value"

    def test_deeply_nested(self):
        d = {"a": {"b": {"c": "deep"}}}
        result = _flatten_dict(d)
        assert result["a.b.c"] == "deep"

    def test_list_values(self):
        d = {"items": ["alpha", "beta"]}
        result = _flatten_dict(d)
        assert "items[0]" in result
        assert result["items[0]"] == "alpha"
        assert result["items[1]"] == "beta"

    def test_none_value(self):
        d = {"field": None}
        result = _flatten_dict(d)
        assert result["field"] == ""

    def test_numeric_values(self):
        d = {"count": 42, "ratio": 0.5}
        result = _flatten_dict(d)
        assert result["count"] == "42"
        assert result["ratio"] == "0.5"


class TestVerifyClaim:
    def test_exact_match(self):
        claim = make_claim(
            source="company_profile.json → anagrafica.denominazione",
            value="La Monica Luciano"
        )
        assert _verify_claim(claim, SAMPLE_SOURCES) is True

    def test_substring_match(self):
        claim = make_claim(
            source="company_profile.json → anagrafica.denominazione",
            value="La Monica"  # substring of "La Monica Luciano"
        )
        assert _verify_claim(claim, SAMPLE_SOURCES) is True

    def test_case_insensitive(self):
        claim = make_claim(
            source="company_profile.json → anagrafica.denominazione",
            value="la monica luciano"
        )
        assert _verify_claim(claim, SAMPLE_SOURCES) is True

    def test_value_not_in_source(self):
        claim = make_claim(
            source="company_profile.json → anagrafica.denominazione",
            value="Mario Rossi"
        )
        assert _verify_claim(claim, SAMPLE_SOURCES) is False

    def test_missing_source(self):
        claim = make_claim(source="", value="something")
        assert _verify_claim(claim, SAMPLE_SOURCES) is False

    def test_missing_value(self):
        claim = make_claim(source="company_profile.json → anagrafica.denominazione", value="")
        assert _verify_claim(claim, SAMPLE_SOURCES) is False

    def test_malformed_source_no_arrow(self):
        claim = make_claim(source="company_profile.json", value="something")
        assert _verify_claim(claim, SAMPLE_SOURCES) is False

    def test_unknown_file(self):
        claim = make_claim(
            source="unknown_file.json → field",
            value="value"
        )
        assert _verify_claim(claim, SAMPLE_SOURCES) is False

    def test_numeric_match(self):
        """Numbers should match even with different formatting."""
        claim = make_claim(
            source="company_profile.json → dimensione.fatturato_stimato_max",
            value="85,000"  # formatted differently
        )
        # Numeric stripping: "85000" vs "85000" → match
        assert _verify_claim(claim, SAMPLE_SOURCES) is True

    def test_field_not_in_source(self):
        claim = make_claim(
            source="company_profile.json → nonexistent.field",
            value="value"
        )
        assert _verify_claim(claim, SAMPLE_SOURCES) is False


class TestCheckClaims:
    def test_all_verified_result(self):
        claims = [
            make_claim(
                source="company_profile.json → anagrafica.denominazione",
                value="La Monica Luciano"
            ),
            make_claim(
                source="company_profile.json → sede.regione",
                value="Sicilia"
            ),
        ]
        with patch("engine.generators.fact_checker._load_source_data", return_value=SAMPLE_SOURCES):
            result = check_claims(claims)

        assert result.total_claims == 2
        assert result.verified_count == 2
        assert result.unverified_count == 0
        assert result.all_verified is True

    def test_partial_verification(self):
        claims = [
            make_claim(
                source="company_profile.json → anagrafica.denominazione",
                value="La Monica Luciano"
            ),
            make_claim(
                source="company_profile.json → anagrafica.denominazione",
                value="Mario Rossi"  # wrong
            ),
        ]
        with patch("engine.generators.fact_checker._load_source_data", return_value=SAMPLE_SOURCES):
            result = check_claims(claims)

        assert result.total_claims == 2
        assert result.verified_count == 1
        assert result.unverified_count == 1
        assert result.all_verified is False

    def test_verification_rate(self):
        claims = [
            make_claim(source="company_profile.json → sede.regione", value="Sicilia"),
            make_claim(source="company_profile.json → sede.regione", value="Sicilia"),
            make_claim(source="company_profile.json → sede.regione", value="WRONG"),
            make_claim(source="company_profile.json → sede.regione", value="Sicilia"),
        ]
        with patch("engine.generators.fact_checker._load_source_data", return_value=SAMPLE_SOURCES):
            result = check_claims(claims)

        assert abs(result.verification_rate - 0.75) < 0.01

    def test_empty_claims_all_verified(self):
        with patch("engine.generators.fact_checker._load_source_data", return_value=SAMPLE_SOURCES):
            result = check_claims([])

        assert result.all_verified is True
        assert result.total_claims == 0
        assert result.verification_rate == 1.0

    def test_pre_loaded_profile_merged(self):
        """Pre-loaded profile data should be merged with file-loaded data."""
        claims = [
            make_claim(
                source="company_profile.json → extra.field",
                value="custom_value"
            ),
        ]
        extra_profile = {"extra": {"field": "custom_value"}}
        with patch("engine.generators.fact_checker._load_source_data", return_value={}):
            result = check_claims(claims, company_profile=extra_profile)

        assert result.verified_count == 1


class TestAssertAllVerified:
    def test_passes_when_all_verified(self):
        claims = [
            make_claim(source="company_profile.json → sede.regione", value="Sicilia"),
        ]
        with patch("engine.generators.fact_checker._load_source_data", return_value=SAMPLE_SOURCES):
            result = assert_all_verified(claims)
        assert result.all_verified is True

    def test_raises_when_unverified(self):
        claims = [
            make_claim(source="company_profile.json → sede.regione", value="Torino"),
        ]
        with patch("engine.generators.fact_checker._load_source_data", return_value=SAMPLE_SOURCES):
            with pytest.raises(DocumentBlockedError) as exc_info:
                assert_all_verified(claims)

        assert len(exc_info.value.unverified) == 1

    def test_document_blocked_error_message(self):
        claims = [make_claim(source="f.json → x", value="y")]
        with patch("engine.generators.fact_checker._load_source_data", return_value={}):
            with pytest.raises(DocumentBlockedError) as exc_info:
                assert_all_verified(claims)

        error_msg = str(exc_info.value)
        assert "unverifiable" in error_msg.lower() or "blocked" in error_msg.lower()


class TestFactCheckResult:
    def test_summary_pass(self):
        result = FactCheckResult(
            total_claims=5, verified_count=5, unverified_count=0
        )
        assert "PASS" in result.summary()
        assert "5/5" in result.summary()

    def test_summary_blocked(self):
        result = FactCheckResult(
            total_claims=5, verified_count=3, unverified_count=2
        )
        assert "BLOCKED" in result.summary()
        assert "3/5" in result.summary()
