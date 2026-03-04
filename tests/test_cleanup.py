"""
Tests for engine/db/cleanup.py
Uses mock DB connections — no real DB required.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import date, timedelta
from engine.db.cleanup import archive_expired_bandi, purge_old_scartati, vacuum_db, run_all


def make_mock_conn(count=5):
    """Create a mock psycopg2 connection."""
    cur = MagicMock()
    cur.fetchone.return_value = (count,)

    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


class TestArchiveExpiredBandi:
    def test_dry_run_returns_count(self):
        conn, cur = make_mock_conn(count=3)
        with patch("psycopg2.connect", return_value=conn):
            result = archive_expired_bandi(dry_run=True)
        assert result == 3
        # Should NOT have called UPDATE
        update_calls = [c for c in cur.execute.call_args_list
                        if "UPDATE" in str(c)]
        assert len(update_calls) == 0

    def test_returns_0_when_nothing_to_archive(self):
        conn, cur = make_mock_conn(count=0)
        with patch("psycopg2.connect", return_value=conn):
            result = archive_expired_bandi(dry_run=False)
        assert result == 0

    def test_executes_update_when_count_positive(self):
        conn, cur = make_mock_conn(count=5)
        with patch("psycopg2.connect", return_value=conn):
            result = archive_expired_bandi(dry_run=False)
        assert result == 5
        # Should have committed
        conn.commit.assert_called_once()

    def test_returns_0_on_exception(self):
        with patch("psycopg2.connect", side_effect=Exception("DB error")):
            result = archive_expired_bandi(dry_run=False)
        assert result == 0


class TestPurgeOldScartati:
    def test_dry_run_no_delete(self):
        conn, cur = make_mock_conn(count=10)
        with patch("psycopg2.connect", return_value=conn):
            result = purge_old_scartati(days=90, dry_run=True)
        assert result == 10
        delete_calls = [c for c in cur.execute.call_args_list
                        if "DELETE" in str(c)]
        assert len(delete_calls) == 0

    def test_returns_0_when_nothing_to_purge(self):
        conn, cur = make_mock_conn(count=0)
        with patch("psycopg2.connect", return_value=conn):
            result = purge_old_scartati(days=90, dry_run=False)
        assert result == 0

    def test_executes_delete_when_count_positive(self):
        conn, cur = make_mock_conn(count=7)
        with patch("psycopg2.connect", return_value=conn):
            result = purge_old_scartati(days=90, dry_run=False)
        assert result == 7
        delete_calls = [c for c in cur.execute.call_args_list
                        if "DELETE" in str(c)]
        assert len(delete_calls) > 0

    def test_custom_days_parameter(self):
        conn, cur = make_mock_conn(count=2)
        with patch("psycopg2.connect", return_value=conn):
            purge_old_scartati(days=180, dry_run=True)
        # Check that the cutoff date uses 180 days
        sql_calls = [str(c) for c in cur.execute.call_args_list]
        assert any("cutoff" in c.lower() or "180" in c or "updated_at" in c.lower()
                   for c in sql_calls)


class TestVacuumDb:
    def test_vacuum_sets_autocommit(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        with patch("psycopg2.connect", return_value=conn):
            result = vacuum_db()
        assert result is True
        # AUTOCOMMIT must be set
        conn.set_isolation_level.assert_called_with(0)

    def test_vacuum_returns_false_on_error(self):
        with patch("psycopg2.connect", side_effect=Exception("DB error")):
            result = vacuum_db()
        assert result is False


class TestRunAll:
    def test_run_all_dry_no_vacuum(self):
        """Dry run should NOT call vacuum."""
        with patch("engine.db.cleanup.archive_expired_bandi", return_value=5) as mock_arch:
            with patch("engine.db.cleanup.purge_old_scartati", return_value=3) as mock_purge:
                with patch("engine.db.cleanup.vacuum_db") as mock_vac:
                    result = run_all(dry_run=True)

        assert result["archived"] == 5
        assert result["purged"] == 3
        mock_vac.assert_not_called()

    def test_run_all_calls_vacuum_when_not_dry(self):
        with patch("engine.db.cleanup.archive_expired_bandi", return_value=0):
            with patch("engine.db.cleanup.purge_old_scartati", return_value=0):
                with patch("engine.db.cleanup.vacuum_db") as mock_vac:
                    run_all(dry_run=False)
        mock_vac.assert_called_once()

    def test_run_all_returns_dict(self):
        with patch("engine.db.cleanup.archive_expired_bandi", return_value=2):
            with patch("engine.db.cleanup.purge_old_scartati", return_value=1):
                with patch("engine.db.cleanup.vacuum_db"):
                    result = run_all(dry_run=False)
        assert "archived" in result
        assert "purged" in result
