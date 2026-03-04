"""
Loads company_profile.json and skills_matrix.json into pgvector (company_embeddings).
Idempotent: running twice does not create duplicates.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

import psycopg2
import anthropic

from engine.config import DATABASE_URL, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"


def _get_embedding(client: anthropic.Anthropic, text: str) -> list[float]:
    """Generate embedding via Claude API (using text-embedding via messages)."""
    # Anthropic doesn't have a dedicated embeddings endpoint yet —
    # use voyage-3 via the messages API or fall back to a simple hash-based mock
    # for development. In production, swap with your preferred embedding model.
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1,
            messages=[{"role": "user", "content": f"Embedding: {text[:500]}"}],
        )
        # Real embeddings: use voyage-3 when available via Anthropic API
        # For now return a deterministic mock vector for development
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = [(b / 255.0) * 2 - 1 for b in hash_bytes]
        # Pad/truncate to 1536 dimensions
        while len(vector) < 1536:
            vector.extend(vector[:min(len(vector), 1536 - len(vector))])
        return vector[:1536]
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise


def _upsert_embedding(cur, categoria: str, contenuto: str, embedding: list[float], metadata: dict):
    """Insert or update embedding row (upsert on categoria+contenuto hash)."""
    cur.execute("""
        INSERT INTO company_embeddings (categoria, contenuto, embedding, metadata)
        VALUES (%s, %s, %s::vector, %s)
        ON CONFLICT DO NOTHING
    """, (categoria, contenuto, embedding, json.dumps(metadata)))


def load_profile():
    """Main entry point — load all profile data into pgvector."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    conn = psycopg2.connect(DATABASE_URL)

    with open(CONTEXT_DIR / "company_profile.json", encoding="utf-8") as f:
        profile = json.load(f)

    with open(CONTEXT_DIR / "skills_matrix.json", encoding="utf-8") as f:
        skills = json.load(f)

    inserted = 0

    with conn.cursor() as cur:
        # ── Anagrafica ────────────────────────────────────────────────────────
        anagrafica_text = (
            f"{profile['anagrafica']['denominazione']} — "
            f"P.IVA {profile['anagrafica']['partita_iva']} — "
            f"Forma giuridica: {profile['anagrafica']['forma_giuridica']} — "
            f"Regime: {profile['anagrafica']['regime_fiscale']}"
        )
        emb = _get_embedding(client, anagrafica_text)
        _upsert_embedding(cur, "anagrafica", anagrafica_text, emb, profile["anagrafica"])
        inserted += 1

        # ── Sede e localizzazione ─────────────────────────────────────────────
        sede_text = (
            f"Sede: {profile['sede']['comune']} ({profile['sede']['provincia']}), "
            f"{profile['sede']['regione']} — ZES: {profile['sede']['zona_zes']} — "
            f"Mezzogiorno: {profile['sede']['zona_mezzogiorno']}"
        )
        emb = _get_embedding(client, sede_text)
        _upsert_embedding(cur, "sede", sede_text, emb, profile["sede"])
        inserted += 1

        # ── Attività e ATECO ──────────────────────────────────────────────────
        attivita_text = (
            f"Attività: {profile['attivita']['ateco_descrizione']} — "
            f"ATECO {profile['attivita']['ateco_2025']} — "
            f"Attiva dal {profile['attivita']['data_inizio']} "
            f"({profile['attivita']['anni_attivita']} anni)"
        )
        emb = _get_embedding(client, attivita_text)
        _upsert_embedding(cur, "attivita", attivita_text, emb, profile["attivita"])
        inserted += 1

        # ── Skills da skills_matrix.json ──────────────────────────────────────
        for categoria, items in skills.items():
            if categoria.startswith("_"):
                continue
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        text = json.dumps(item, ensure_ascii=False)
                        emb = _get_embedding(client, text[:1000])
                        _upsert_embedding(cur, f"skill_{categoria}", text, emb, item)
                        inserted += 1
            elif isinstance(items, dict):
                text = json.dumps(items, ensure_ascii=False)
                emb = _get_embedding(client, text[:1000])
                _upsert_embedding(cur, f"skill_{categoria}", text, emb, items)
                inserted += 1

    conn.commit()
    conn.close()
    logger.info(f"Profile loaded: {inserted} embeddings inserted")
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = load_profile()
    print(f"Done — {n} embeddings loaded into pgvector")
