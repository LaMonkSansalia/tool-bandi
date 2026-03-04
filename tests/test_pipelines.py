"""
Tests for engine/scrapers/pipelines.py
Tests the _parse_date and _initial_stato helpers without DB.
"""
import pytest
from datetime import date, timedelta
from engine.scrapers.pipelines import _parse_date, _initial_stato


class TestParseDate:
    def test_iso_format(self):
        result = _parse_date("2025-12-31")
        assert result == date(2025, 12, 31)

    def test_italian_format_slash(self):
        result = _parse_date("31/12/2025")
        assert result == date(2025, 12, 31)

    def test_italian_format_dash(self):
        result = _parse_date("31-12-2025")
        assert result == date(2025, 12, 31)

    def test_none_input(self):
        assert _parse_date(None) is None

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_date_object_passthrough(self):
        d = date(2025, 6, 15)
        assert _parse_date(d) == d

    def test_invalid_string(self):
        assert _parse_date("not a date") is None

    def test_strips_whitespace(self):
        result = _parse_date("  2025-12-31  ")
        assert result == date(2025, 12, 31)


class TestInitialStato:
    def test_none_scadenza_returns_nuovo(self):
        assert _initial_stato(None) == "nuovo"

    def test_future_scadenza_returns_nuovo(self):
        future = date.today() + timedelta(days=30)
        assert _initial_stato(future) == "nuovo"

    def test_past_scadenza_returns_archiviato(self):
        past = date.today() - timedelta(days=1)
        assert _initial_stato(past) == "archiviato"

    def test_today_scadenza_returns_nuovo(self):
        """Scadenza on today itself is not yet expired."""
        today = date.today()
        assert _initial_stato(today) == "nuovo"

    def test_far_future(self):
        far_future = date(2030, 1, 1)
        assert _initial_stato(far_future) == "nuovo"

    def test_far_past(self):
        far_past = date(2020, 1, 1)
        assert _initial_stato(far_past) == "archiviato"
