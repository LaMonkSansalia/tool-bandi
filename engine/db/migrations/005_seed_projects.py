#!/usr/bin/env python3
"""
Migration 005 — Seed project #1 (La Monica Luciano) from existing JSON files
and migrate bandi evaluation data into project_evaluations.

Usage:
    PYTHONPATH=. venv/bin/python engine/db/migrations/005_seed_projects.py

Must run AFTER 005_multi_project.sql has been applied.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

# Add project root to path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.config import DATABASE_URL, CONTEXT_DIR


# ── Default scoring rules for ICT freelancer (matches current SCORE_RULES) ────

ICT_SCORING_RULES = {
    "version": "1.0",
    "rules": [
        {
            "name": "regione_ammessa",
            "points": 15,
            "type": "region_match",
            "description": "Sicilia / Sud / Mezzogiorno ammessi",
        },
        {
            "name": "ateco_ict",
            "points": 20,
            "type": "ateco_match",
            "description": "ATECO ICT (62.x) prioritario PNRR",
        },
        {
            "name": "zona_zes",
            "points": 10,
            "type": "keyword_and_profile",
            "description": "Zona ZES — bonus automatico",
            "config": {
                "profile_field": "zona_zes",
                "keywords": ["zes", "zona economica speciale", "mezzogiorno", "sud"],
            },
        },
        {
            "name": "under_36",
            "points": 10,
            "type": "profile_age_check",
            "description": "Titolare under 36 — bandi giovani imprenditori",
            "config": {
                "keywords": ["under 35", "under 36", "giovani", "giovane imprenditore", "under35"],
            },
        },
        {
            "name": "nuova_impresa",
            "points": 10,
            "type": "company_age",
            "description": "Impresa attiva da meno di 5 anni",
            "config": {
                "max_years": 5,
                "keywords": ["nuova impresa", "startup", "nuove imprese", "neo-impresa", "neo impresa"],
            },
        },
        {
            "name": "impresa_individuale_ok",
            "points": 5,
            "type": "beneficiary_match",
            "description": "Impresa individuale esplicitamente ammessa",
            "config": {
                "accepted_types": [
                    "impresa_individuale",
                    "impresa_individuale_e_libero_professionista",
                    "tutti",
                    "tutte_le_imprese",
                ],
            },
        },
        {
            "name": "no_certificazioni",
            "points": 5,
            "type": "no_certifications_required",
            "description": "Nessuna certificazione obbligatoria richiesta",
        },
        {
            "name": "micro_impresa_ok",
            "points": 5,
            "type": "beneficiary_match",
            "description": "Micro-impresa ammessa",
            "config": {
                "accepted_types": ["micro_impresa", "pmi", "tutti", "tutte_le_imprese"],
            },
        },
        {
            "name": "pnrr_digitalizzazione",
            "points": 10,
            "type": "keyword_in_title",
            "description": "Bando PNRR digitalizzazione / ICT",
            "config": {
                "keywords": ["pnrr", "digitalizzazione", "digitale", "digital", "ict", "innovazione digitale"],
            },
        },
        {
            "name": "importo_adeguato",
            "points": 10,
            "type": "importo_min",
            "description": "Importo max > 5.000 EUR (significativo)",
            "config": {"min_importo": 5000},
        },
    ],
}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    profile_path = CONTEXT_DIR / "company_profile.json"
    skills_path = CONTEXT_DIR / "skills_matrix.json"

    if not profile_path.exists():
        print(f"ERROR: {profile_path} not found")
        sys.exit(1)

    profilo = load_json(profile_path)
    skills = load_json(skills_path) if skills_path.exists() else None

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            # ── Check if project #1 already exists ──────────────────────────────
            cur.execute("SELECT id FROM projects WHERE slug = 'lamonica'")
            if cur.fetchone():
                print("Project 'lamonica' already exists — skipping insert")
            else:
                # ── Insert project #1 ───────────────────────────────────────────
                cur.execute("""
                    INSERT INTO projects (slug, nome, descrizione, profilo, skills, scoring_rules,
                                         telegram_prefix, attivo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    "lamonica",
                    "La Monica Luciano",
                    "Impresa individuale — Consulenza informatica (ATECO 62.20.10)",
                    Json(profilo),
                    Json(skills) if skills else None,
                    Json(ICT_SCORING_RULES),
                    "[LM]",
                    True,
                ))
                project_id = cur.fetchone()[0]
                print(f"Inserted project #1 (id={project_id}): La Monica Luciano")

            # ── Migrate existing bandi evaluations ──────────────────────────────
            cur.execute("SELECT COUNT(*) FROM project_evaluations WHERE project_id = 1")
            existing_evals = cur.fetchone()[0]
            if existing_evals > 0:
                print(f"Project evaluations already migrated ({existing_evals} rows) — skipping")
            else:
                cur.execute("""
                    INSERT INTO project_evaluations
                        (project_id, bando_id, score, stato, motivo_scarto,
                         data_invio, protocollo_ricevuto, created_at, updated_at)
                    SELECT
                        1, id, score, COALESCE(stato, 'nuovo'), motivo_scarto,
                        data_invio, protocollo_ricevuto, created_at, updated_at
                    FROM bandi
                """)
                migrated = cur.rowcount
                print(f"Migrated {migrated} bandi evaluations to project_evaluations")

            # ── Backfill project_id on related tables ───────────────────────────
            cur.execute("""
                UPDATE bando_documenti_generati SET project_id = 1
                WHERE project_id IS NULL
            """)
            docs_updated = cur.rowcount
            if docs_updated:
                print(f"Backfilled project_id=1 on {docs_updated} bando_documenti_generati rows")

            cur.execute("""
                UPDATE bando_requisiti SET project_id = 1
                WHERE project_id IS NULL
            """)
            req_updated = cur.rowcount
            if req_updated:
                print(f"Backfilled project_id=1 on {req_updated} bando_requisiti rows")

            cur.execute("""
                UPDATE company_embeddings SET project_id = 1
                WHERE project_id IS NULL
            """)
            emb_updated = cur.rowcount
            if emb_updated:
                print(f"Backfilled project_id=1 on {emb_updated} company_embeddings rows")

        conn.commit()
        print("Migration 005 seed completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
