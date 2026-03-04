"""
Scrapy pipeline — saves bandi to PostgreSQL with full dedup + state machine logic.
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta

import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json

from engine.config import DATABASE_URL, URGENCY_THRESHOLD_DAYS
from engine.scrapers.deduplicator import (
    compute_dedup_hash,
    find_existing_bando,
    FROZEN_STATES,
    SILENT_UPDATE_STATES,
    NOTIFY_UPDATE_STATES,
)

logger = logging.getLogger(__name__)


class BandiPipeline:
    """Main pipeline: dedup → insert or update → queue parsing."""

    conn = None

    def open_spider(self, spider):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.conn.autocommit = False
        logger.info("DB connection opened")

    def close_spider(self, spider):
        if self.conn:
            self.conn.close()
        logger.info("DB connection closed")

    def process_item(self, item: dict, spider) -> dict:
        """
        Process a single scraped bando item.
        Returns item unchanged (for chaining).
        """
        titolo = item.get("titolo", "").strip()
        ente = item.get("ente_erogatore", "").strip()
        url = item.get("url") or item.get("url_fonte")
        data_scadenza_raw = item.get("data_scadenza")

        if not titolo:
            logger.warning("Skipping item with no title")
            return item

        # Parse scadenza
        data_scadenza = _parse_date(data_scadenza_raw)

        # Compute dedup hash
        anno = data_scadenza.year if data_scadenza else datetime.now().year
        dedup_hash = compute_dedup_hash(ente, titolo, anno)

        try:
            existing = find_existing_bando(self.conn, url, dedup_hash)

            if existing is None:
                # New bando — determine initial stato based on deadline
                stato = _initial_stato(data_scadenza)
                bando_id = self._insert_bando(item, dedup_hash, data_scadenza, stato)
                logger.info(f"Inserted new bando [{stato}]: {titolo[:60]}")

                if stato == "nuovo":
                    # Queue for async parsing
                    item["_db_id"] = bando_id
                    item["_action"] = "inserted"

            else:
                existing_stato = existing["stato"]

                if existing_stato in FROZEN_STATES:
                    logger.debug(f"Skipping frozen bando [{existing_stato}]: {titolo[:60]}")
                    item["_action"] = "skipped"

                elif existing_stato in SILENT_UPDATE_STATES:
                    self._silent_update(existing["id"], item, data_scadenza)
                    logger.info(f"Silent update [{existing_stato}]: {titolo[:60]}")
                    item["_action"] = "updated_silent"

                elif existing_stato in NOTIFY_UPDATE_STATES:
                    changed = self._notify_update(existing, item, data_scadenza)
                    if changed:
                        logger.info(f"Update+notify [{existing_stato}]: {titolo[:60]}")
                        item["_action"] = "updated_notify"
                    else:
                        item["_action"] = "no_change"

                self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Pipeline error on '{titolo[:60]}': {e}")
            raise

        return item

    def _insert_bando(
        self, item: dict, dedup_hash: str, data_scadenza: date | None, stato: str
    ) -> int:
        """Insert new bando row, return id."""
        # Prepare parsed fields (may come from claude_structurer output)
        criteri_raw = item.get("criteri_valutazione")
        criteri_json = Json(criteri_raw) if criteri_raw else None
        docs_allegare = item.get("documenti_da_allegare") or None

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bandi (
                    titolo, ente_erogatore, url_fonte, portale,
                    data_scadenza, importo_max,
                    tipo_finanziamento, aliquota_fondo_perduto,
                    dedup_hash, stato, first_seen_at,
                    raw_text, metadata,
                    criteri_valutazione, documenti_da_allegare,
                    parsing_confidence, parsing_notes
                ) VALUES (
                    %(titolo)s, %(ente)s, %(url)s, %(portale)s,
                    %(scadenza)s, %(importo)s,
                    %(tipo_fin)s, %(aliquota_fp)s,
                    %(dedup_hash)s, %(stato)s, NOW(),
                    %(raw_text)s, %(metadata)s,
                    %(criteri)s, %(docs_allegare)s,
                    %(confidence)s, %(notes)s
                ) RETURNING id
            """, {
                "titolo": item.get("titolo"),
                "ente": item.get("ente_erogatore"),
                "url": item.get("url") or item.get("url_fonte"),
                "portale": item.get("portale"),
                "scadenza": data_scadenza,
                "importo": item.get("importo_max"),
                "tipo_fin": item.get("tipo_finanziamento"),
                "aliquota_fp": item.get("aliquota_fondo_perduto"),
                "dedup_hash": dedup_hash,
                "stato": stato,
                "raw_text": item.get("testo_html", "")[:50000],
                "metadata": None,
                "criteri": criteri_json,
                "docs_allegare": docs_allegare,
                "confidence": item.get("confidence"),
                "notes": item.get("parsing_notes"),
            })
            bando_id = cur.fetchone()[0]
            self.conn.commit()
            return bando_id

    def _silent_update(self, bando_id: int, item: dict, data_scadenza: date | None):
        """Update metadata fields silently (no notification)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE bandi SET
                    data_scadenza = COALESCE(%(scadenza)s, data_scadenza),
                    importo_max   = COALESCE(%(importo)s, importo_max),
                    url_fonte     = COALESCE(%(url)s, url_fonte),
                    updated_at    = NOW()
                WHERE id = %(id)s
            """, {
                "scadenza": data_scadenza,
                "importo": item.get("importo_max"),
                "url": item.get("url") or item.get("url_fonte"),
                "id": bando_id,
            })

    def _notify_update(self, existing: dict, item: dict, data_scadenza: date | None) -> bool:
        """
        Update metadata + return True if key fields changed (caller handles notification).
        """
        old_scadenza = existing.get("data_scadenza")
        old_budget = existing.get("budget_totale")
        new_importo = item.get("importo_max")

        scadenza_changed = data_scadenza and old_scadenza != data_scadenza
        budget_changed = new_importo and old_budget != new_importo

        self._silent_update(existing["id"], item, data_scadenza)

        if scadenza_changed or budget_changed:
            # Store change info for notification system
            item["_notify_changes"] = {
                "bando_id": existing["id"],
                "titolo": existing["titolo"],
                "old_scadenza": str(old_scadenza) if old_scadenza else None,
                "new_scadenza": str(data_scadenza) if data_scadenza else None,
                "old_budget": old_budget,
                "new_budget": new_importo,
                "scadenza_changed": scadenza_changed,
                "budget_changed": budget_changed,
            }
            return True
        return False


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _initial_stato(data_scadenza: date | None) -> str:
    """
    Determine initial stato for a first-seen bando.
    - Already expired → archiviato
    - Expiring within URGENCY_THRESHOLD_DAYS → nuovo (urgent notification after eligibility)
    - Otherwise → nuovo
    """
    if data_scadenza is None:
        return "nuovo"

    today = date.today()
    if data_scadenza < today:
        return "archiviato"

    return "nuovo"   # urgency is handled by notification layer, not stato
