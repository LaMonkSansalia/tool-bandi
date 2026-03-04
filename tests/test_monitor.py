"""
Tests for engine/pipeline/monitor.py
Tests use file fallback only (no DB required).
"""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestRunMonitor:
    def test_context_manager_enter_exit(self, tmp_path):
        """RunMonitor should be usable as context manager."""
        with patch("engine.pipeline.monitor.LOG_FILE", tmp_path / "runs.jsonl"):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import RunMonitor
                with RunMonitor(spiders=["invitalia"]) as monitor:
                    assert monitor is not None
                    monitor.set_result({"scraped": 10, "inserted": 3, "notified": 1})

    def test_set_result_and_log(self, tmp_path):
        """set_result should be reflected in the logged run data."""
        log_file = tmp_path / "runs.jsonl"
        with patch("engine.pipeline.monitor.LOG_FILE", log_file):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import RunMonitor
                with RunMonitor(spiders=["invitalia", "mimit"]) as monitor:
                    monitor.set_result({
                        "scraped": 50,
                        "inserted": 5,
                        "updated": 2,
                        "notified": 3,
                        "spider_failures": 0,
                    })

        assert log_file.exists()
        line = json.loads(log_file.read_text().strip())
        assert line["scraped"] == 50
        assert line["inserted"] == 5
        assert line["notified"] == 3
        assert "invitalia" in line["spiders_run"]
        assert "mimit" in line["spiders_run"]

    def test_add_error(self, tmp_path):
        """Errors added via add_error should appear in log."""
        log_file = tmp_path / "runs.jsonl"
        with patch("engine.pipeline.monitor.LOG_FILE", log_file):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import RunMonitor
                with RunMonitor() as monitor:
                    monitor.add_error("Test error message")
                    monitor.set_result({"scraped": 0})

        line = json.loads(log_file.read_text().strip())
        assert "Test error message" in line["errors"]

    def test_duration_recorded(self, tmp_path):
        """Duration in seconds should be a non-negative integer."""
        log_file = tmp_path / "runs.jsonl"
        with patch("engine.pipeline.monitor.LOG_FILE", log_file):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import RunMonitor
                with RunMonitor() as monitor:
                    monitor.set_result({"scraped": 1})

        line = json.loads(log_file.read_text().strip())
        assert isinstance(line["duration_seconds"], int)
        assert line["duration_seconds"] >= 0

    def test_exception_does_not_swallow(self, tmp_path):
        """RunMonitor must not suppress exceptions."""
        log_file = tmp_path / "runs.jsonl"
        with patch("engine.pipeline.monitor.LOG_FILE", log_file):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import RunMonitor
                with pytest.raises(ValueError, match="test_error"):
                    with RunMonitor() as monitor:
                        raise ValueError("test_error")


class TestLogRun:
    def test_file_fallback_when_db_unavailable(self, tmp_path):
        """log_run should write to file when DB is unavailable."""
        log_file = tmp_path / "pipeline_runs.jsonl"
        with patch("engine.pipeline.monitor.LOG_FILE", log_file):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import log_run
                log_run({
                    "started_at": datetime.now(),
                    "scraped": 10,
                    "inserted": 2,
                })

        assert log_file.exists()
        content = log_file.read_text().strip()
        assert content  # not empty

    def test_multiple_runs_appended(self, tmp_path):
        """Multiple log_run calls should append, not overwrite."""
        log_file = tmp_path / "pipeline_runs.jsonl"
        with patch("engine.pipeline.monitor.LOG_FILE", log_file):
            with patch("engine.pipeline.monitor._try_db_log", return_value=False):
                from engine.pipeline.monitor import log_run
                log_run({"started_at": datetime.now(), "scraped": 1})
                log_run({"started_at": datetime.now(), "scraped": 2})

        lines = [l for l in log_file.read_text().strip().split("\n") if l]
        assert len(lines) == 2


class TestGetLastRunSummary:
    def test_returns_none_when_no_file(self, tmp_path):
        """Returns None if no DB and no log file."""
        with patch("engine.pipeline.monitor.LOG_FILE", tmp_path / "nonexistent.jsonl"):
            with patch("engine.pipeline.monitor._try_db_log", side_effect=Exception("no db")):
                from importlib import reload
                import engine.pipeline.monitor as m
                with patch.object(m, "LOG_FILE", tmp_path / "nonexistent.jsonl"):
                    # Patch to avoid actual DB call
                    with patch("psycopg2.connect", side_effect=Exception("no db")):
                        result = m.get_last_run_summary()
                        assert result is None

    def test_reads_last_run_from_file(self, tmp_path):
        """Returns last line from JSONL file."""
        log_file = tmp_path / "pipeline_runs.jsonl"
        run1 = {"scraped": 10, "inserted": 1}
        run2 = {"scraped": 20, "inserted": 5}
        log_file.write_text(json.dumps(run1) + "\n" + json.dumps(run2) + "\n")

        import engine.pipeline.monitor as m
        with patch.object(m, "LOG_FILE", log_file):
            with patch("psycopg2.connect", side_effect=Exception("no db")):
                result = m.get_last_run_summary()
                assert result["scraped"] == 20
