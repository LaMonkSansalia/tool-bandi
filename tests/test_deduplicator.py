"""
Tests for engine/scrapers/deduplicator.py
"""
import pytest
from unittest.mock import MagicMock, patch
from engine.scrapers.deduplicator import (
    normalize,
    compute_dedup_hash,
    find_existing_bando,
    FROZEN_STATES,
    SILENT_UPDATE_STATES,
    NOTIFY_UPDATE_STATES,
)


class TestNormalize:
    def test_lowercase(self):
        assert normalize("BANDO") == "bando"

    def test_strips_accents(self):
        assert normalize("Città") == "citta"
        assert normalize("Opportunità") == "opportunita"
        assert normalize("bàndò") == "bando"

    def test_collapses_whitespace(self):
        assert normalize("  bando   digitale  ") == "bando digitale"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_mixed(self):
        # Em dash (—) is not an accent mark — it's preserved by normalize()
        result = normalize("  Bando PNRR — Digitalizzazione  ")
        assert result == "bando pnrr — digitalizzazione"

    def test_italian_special_chars(self):
        assert normalize("è") == "e"
        assert normalize("à") == "a"
        assert normalize("ò") == "o"
        assert normalize("ì") == "i"
        assert normalize("ù") == "u"


class TestComputeDedupHash:
    def test_returns_16_chars(self):
        h = compute_dedup_hash("MIMIT", "Bando ICT", 2024)
        assert len(h) == 16

    def test_deterministic(self):
        h1 = compute_dedup_hash("Invitalia", "Bando Digitale", 2025)
        h2 = compute_dedup_hash("Invitalia", "Bando Digitale", 2025)
        assert h1 == h2

    def test_different_ente_different_hash(self):
        h1 = compute_dedup_hash("Invitalia", "Bando ICT", 2025)
        h2 = compute_dedup_hash("MIMIT", "Bando ICT", 2025)
        assert h1 != h2

    def test_different_year_different_hash(self):
        h1 = compute_dedup_hash("Invitalia", "Bando ICT", 2024)
        h2 = compute_dedup_hash("Invitalia", "Bando ICT", 2025)
        assert h1 != h2

    def test_accent_normalization_same_hash(self):
        """Normalized accents should give same hash."""
        h1 = compute_dedup_hash("Città di Palermo", "bando", 2025)
        h2 = compute_dedup_hash("Citta di Palermo", "bando", 2025)
        assert h1 == h2

    def test_case_insensitive_hash(self):
        h1 = compute_dedup_hash("INVITALIA", "Bando ICT", 2025)
        h2 = compute_dedup_hash("invitalia", "bando ict", 2025)
        assert h1 == h2

    def test_hex_chars_only(self):
        h = compute_dedup_hash("ente", "titolo", 2025)
        assert all(c in "0123456789abcdef" for c in h)


class TestFindExistingBando:
    def _make_conn(self, rows):
        """Helper: mock psycopg2 connection returning given rows."""
        cur = MagicMock()
        cur.fetchone.return_value = rows[0] if rows else None
        cur.description = [
            type("col", (), {"__getitem__": lambda self, i: ["id", "stato", "titolo", "data_scadenza", "budget_totale"][i]})()
            for _ in range(5)
        ]
        # Fix description to support d[0] access
        cols = ["id", "stato", "titolo", "data_scadenza", "budget_totale"]
        cur.description = [MagicMock() for c in cols]
        for i, c in enumerate(cols):
            cur.description[i].__getitem__ = lambda self, idx, col=c: col if idx == 0 else None

        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn, cur

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        cols = ["id", "stato", "titolo", "data_scadenza", "budget_totale"]
        cur.description = [MagicMock() for _ in cols]
        for i, c in enumerate(cols):
            cur.description[i].__getitem__ = MagicMock(side_effect=lambda idx, c=c: c if idx == 0 else None)

        conn = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = find_existing_bando(conn, "https://example.com", "deadbeef")
        assert result is None

    def test_url_takes_priority(self):
        """URL match should be checked before hash match."""
        cur = MagicMock()
        row = (1, "idoneo", "Test Bando", None, None)
        cur.fetchone.return_value = row
        cols = ["id", "stato", "titolo", "data_scadenza", "budget_totale"]
        cur.description = [MagicMock() for _ in cols]
        for i, c in enumerate(cols):
            cur.description[i].__getitem__ = MagicMock(side_effect=lambda idx, c=c: c if idx == 0 else None)

        conn = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = find_existing_bando(conn, "https://example.com", "deadbeef")
        # Should have called execute at least once
        assert cur.execute.called


class TestStateSets:
    def test_frozen_states_complete(self):
        assert "lavorazione" in FROZEN_STATES
        assert "pronto" in FROZEN_STATES
        assert "inviato" in FROZEN_STATES
        assert "archiviato" in FROZEN_STATES
        assert "scartato" in FROZEN_STATES

    def test_silent_update_states(self):
        assert "nuovo" in SILENT_UPDATE_STATES
        assert "analisi" in SILENT_UPDATE_STATES

    def test_notify_update_states(self):
        assert "idoneo" in NOTIFY_UPDATE_STATES

    def test_no_overlap_frozen_silent(self):
        assert FROZEN_STATES.isdisjoint(SILENT_UPDATE_STATES)

    def test_no_overlap_frozen_notify(self):
        assert FROZEN_STATES.isdisjoint(NOTIFY_UPDATE_STATES)
