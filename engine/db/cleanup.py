"""
Database Cleanup — archive expired bandi and maintain DB health.

Tasks:
1. Archive bandi expired > ARCHIVE_AFTER_DAYS ago (stato → archiviato)
2. Remove bandi scartati > 90 days old (not idoneo+)
3. Vacuum/analyze for performance

Usage:
    python -m engine.db.cleanup         # run all cleanup tasks
    python -m engine.db.cleanup --dry   # dry run (show what would be done)

Called from Prefect flow as a weekly maintenance task.
"""
from __future__ import annotations
import logging
import sys
from datetime import date, timedelta

import psycopg2

from engine.config import DATABASE_URL, ARCHIVE_AFTER_DAYS

logger = logging.getLogger(__name__)


def archive_expired_bandi(dry_run: bool = False) -> int:
    """
    Set stato='archiviato' for bandi expired > ARCHIVE_AFTER_DAYS days ago
    that are still in stato 'nuovo', 'analisi', or 'idoneo'.

    Bandi in 'lavorazione', 'pronto', 'inviato' are NEVER auto-archived
    (they require manual action).

    Returns number of bandi archived.
    """
    cutoff = date.today() - timedelta(days=ARCHIVE_AFTER_DAYS)
    archivable_states = ("nuovo", "analisi", "idoneo", "scartato")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Count first
        cur.execute("""
            SELECT COUNT(*) FROM bandi
            WHERE data_scadenza < %s
              AND stato = ANY(%s)
        """, (cutoff, list(archivable_states)))
        count = cur.fetchone()[0]

        if dry_run:
            logger.info(f"[DRY RUN] Would archive {count} bandi")
            cur.close()
            conn.close()
            return count

        if count == 0:
            logger.info("No bandi to archive")
            cur.close()
            conn.close()
            return 0

        cur.execute("""
            UPDATE bandi
            SET stato = 'archiviato', updated_at = NOW()
            WHERE data_scadenza < %s
              AND stato = ANY(%s)
        """, (cutoff, list(archivable_states)))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Archived {count} expired bandi (cutoff: {cutoff})")
        return count

    except Exception as e:
        logger.error(f"Archive task failed: {e}")
        return 0


def purge_old_scartati(days: int = 90, dry_run: bool = False) -> int:
    """
    Delete bandi that have been 'scartato' or 'archiviato' for > `days` days.
    Keeps bandi that were ever in a higher state (lavorazione+) for audit trail.

    Returns number of deleted bandi.
    """
    cutoff = date.today() - timedelta(days=days)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*) FROM bandi
            WHERE stato IN ('scartato', 'archiviato')
              AND updated_at < %s
              AND id NOT IN (
                  SELECT DISTINCT bando_id FROM bando_documenti_generati
              )
        """, (cutoff,))
        count = cur.fetchone()[0]

        if dry_run:
            logger.info(f"[DRY RUN] Would delete {count} old scartati/archiviati")
            cur.close()
            conn.close()
            return count

        if count == 0:
            cur.close()
            conn.close()
            return 0

        cur.execute("""
            DELETE FROM bandi
            WHERE stato IN ('scartato', 'archiviato')
              AND updated_at < %s
              AND id NOT IN (
                  SELECT DISTINCT bando_id FROM bando_documenti_generati
              )
        """, (cutoff,))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Deleted {count} old scartati/archiviati (older than {days} days)")
        return count

    except Exception as e:
        logger.error(f"Purge task failed: {e}")
        return 0


def vacuum_db() -> bool:
    """Run VACUUM ANALYZE on the bandi table for performance."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_isolation_level(0)  # AUTOCOMMIT required for VACUUM
        cur = conn.cursor()
        cur.execute("VACUUM ANALYZE bandi")
        cur.execute("VACUUM ANALYZE bando_documenti_generati")
        cur.close()
        conn.close()
        logger.info("VACUUM ANALYZE completed")
        return True
    except Exception as e:
        logger.error(f"VACUUM failed: {e}")
        return False


def run_all(dry_run: bool = False) -> dict[str, int]:
    """Run all cleanup tasks. Returns summary."""
    logger.info(f"Starting cleanup (dry_run={dry_run})")

    archived = archive_expired_bandi(dry_run=dry_run)
    purged = purge_old_scartati(dry_run=dry_run)

    if not dry_run:
        vacuum_db()

    summary = {
        "archived": archived,
        "purged": purged,
    }
    logger.info(f"Cleanup complete: {summary}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dry = "--dry" in sys.argv
    result = run_all(dry_run=dry)
    print(f"Cleanup {'(DRY RUN) ' if dry else ''}complete: {result}")
