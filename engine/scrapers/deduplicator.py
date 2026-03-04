"""
Deduplication logic for bandi.
Key: url_fonte (primary) → dedup_hash (fallback).
dedup_hash = sha256(normalize(ente) | normalize(titolo) | anno)[:16]
"""
from __future__ import annotations
import hashlib
import unicodedata


def normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def compute_dedup_hash(ente: str, titolo: str, anno: int) -> str:
    key = f"{normalize(ente)}|{normalize(titolo)}|{anno}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def find_existing_bando(conn, url: str | None, dedup_hash: str) -> dict | None:
    """
    Search DB for existing bando.
    URL check first (exact match), hash as fallback.

    Args:
        conn: psycopg2 connection
        url: source URL (may be None)
        dedup_hash: computed hash

    Returns:
        dict with bando row or None
    """
    with conn.cursor() as cur:
        if url:
            cur.execute(
                "SELECT id, stato, titolo, data_scadenza, budget_totale FROM bandi WHERE url_fonte = %s",
                [url],
            )
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

        cur.execute(
            "SELECT id, stato, titolo, data_scadenza, budget_totale FROM bandi WHERE dedup_hash = %s",
            [dedup_hash],
        )
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    return None


# States where we must not touch the bando
FROZEN_STATES = {"lavorazione", "pronto", "inviato", "archiviato", "scartato"}

# States where we silently update metadata
SILENT_UPDATE_STATES = {"nuovo", "analisi"}

# States where we update + notify if key fields changed
NOTIFY_UPDATE_STATES = {"idoneo"}
