"""
Database Backup — daily PostgreSQL dump.

Creates compressed SQL dumps in backups/ directory.
Keeps last 30 daily backups, then weekly for 3 months, then monthly.

Usage:
    python -m engine.db.backup          # run now
    python -m engine.db.backup --list   # show available backups
    python -m engine.db.backup --clean  # cleanup old backups

Or call from Prefect flow / cron.
"""
from __future__ import annotations
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from engine.config import DATABASE_URL

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(__file__).parent.parent.parent / "backups"
KEEP_DAILY = 30     # days
KEEP_WEEKLY = 90    # days (after daily window)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _parse_db_url(url: str) -> dict[str, str]:
    """Parse DATABASE_URL into pg_dump parameters."""
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/") or "bandi",
    }


def create_backup(label: str | None = None) -> Path | None:
    """
    Create a compressed PostgreSQL dump.

    Args:
        label: Optional label appended to filename (e.g. "pre-migration")

    Returns:
        Path to created backup file, or None on failure
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    filename = f"bandi_backup_{date_str}{suffix}.sql.gz"
    backup_path = BACKUP_DIR / filename

    db = _parse_db_url(DATABASE_URL)

    cmd = [
        "pg_dump",
        "-h", db["host"],
        "-p", db["port"],
        "-U", db["user"],
        "-d", db["dbname"],
        "--no-password",
        "--compress=9",
        "--format=plain",
        "-f", str(backup_path),
    ]

    env = {"PGPASSWORD": db["password"]} if db["password"] else {}
    import os
    full_env = {**os.environ, **env}

    try:
        logger.info(f"Starting backup: {filename}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, env=full_env
        )
        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr}")
            return None

        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"Backup created: {filename} ({size_mb:.1f} MB)")
        return backup_path

    except FileNotFoundError:
        logger.error("pg_dump not found. Install PostgreSQL client tools.")
        return None
    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out after 5 minutes")
        return None
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return None


def cleanup_old_backups() -> int:
    """
    Remove old backups according to retention policy.
    Returns number of deleted files.
    """
    now = datetime.now()
    deleted = 0

    backups = sorted(BACKUP_DIR.glob("bandi_backup_*.sql.gz"), reverse=True)

    for backup_file in backups:
        # Parse date from filename
        try:
            date_part = backup_file.stem.split("_")[2]  # YYYYMMDD
            backup_date = datetime.strptime(date_part, "%Y%m%d")
        except (IndexError, ValueError):
            continue

        age_days = (now - backup_date).days

        # Keep all backups within KEEP_DAILY days
        if age_days <= KEEP_DAILY:
            continue

        # Keep one per week up to KEEP_WEEKLY days
        if age_days <= KEEP_WEEKLY:
            week_num = age_days // 7
            # Find if there's already a backup for this week
            same_week_kept = any(
                other.stem.split("_")[2] == backup_date.strftime("%Y%m%d")
                for other in backups
                if other != backup_file
            )
            if not same_week_kept:
                continue  # Keep this one as the weekly representative

        # Delete old backups
        try:
            backup_file.unlink()
            logger.info(f"Deleted old backup: {backup_file.name}")
            deleted += 1
        except Exception as e:
            logger.error(f"Could not delete {backup_file.name}: {e}")

    logger.info(f"Cleanup complete: {deleted} backups deleted")
    return deleted


def list_backups() -> list[dict]:
    """List all available backups with metadata."""
    backups = []
    for f in sorted(BACKUP_DIR.glob("bandi_backup_*.sql.gz"), reverse=True):
        size_mb = f.stat().st_size / (1024 * 1024)
        try:
            date_part = f.stem.split("_")[2] + "_" + f.stem.split("_")[3].split(".")[0]
            dt = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
        except (IndexError, ValueError):
            dt = None

        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_mb": round(size_mb, 1),
            "created_at": dt.isoformat() if dt else "unknown",
            "age_days": (datetime.now() - dt).days if dt else None,
        })
    return backups


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--list" in sys.argv:
        backups = list_backups()
        if not backups:
            print("No backups found.")
        for b in backups:
            print(f"{b['filename']}  {b['size_mb']} MB  {b['age_days']}d ago")
    elif "--clean" in sys.argv:
        n = cleanup_old_backups()
        print(f"Deleted {n} old backups.")
    else:
        path = create_backup()
        if path:
            print(f"Backup created: {path}")
        else:
            sys.exit(1)
