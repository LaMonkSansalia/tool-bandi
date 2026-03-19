"""
Migration 010 — Seed soggetti table from company_profile.json.

Runs AFTER 008_soggetti.sql and 009_workspace_fields.sql are applied.

Steps:
1. Insert La Monica Luciano P.IVA into soggetti
2. Update projects.soggetto_id for all existing projects
3. Update project_evaluations.soggetto_id for all evaluations
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

# Allow running from repo root or engine/ directory
ROOT = Path(__file__).resolve().parents[4]  # CodiceCodice/tool-bandi
sys.path.insert(0, str(ROOT / "tool-bandi"))

import psycopg
from engine.config import DATABASE_URL

CONTEXT_DIR = ROOT / "tool-bandi" / "context"
PROFILE_PATH = CONTEXT_DIR / "company_profile.json"


def build_soggetto_profilo(profile: dict) -> dict:
    """Convert company_profile.json structure to soggetti.profilo JSONB format."""
    ana = profile.get("anagrafica", {})
    sede = profile.get("sede", {})
    att = profile.get("attivita", {})
    dim = profile.get("dimensione", {})
    cert = profile.get("certificazioni", {})
    elig = profile.get("eligibility_constraints", {})
    contatti = profile.get("contatti", {})

    return {
        # Anagrafica
        "denominazione": ana.get("denominazione"),
        "titolare": ana.get("titolare"),
        "data_nascita": ana.get("data_nascita"),
        "luogo_nascita": ana.get("luogo_nascita"),
        "codice_fiscale": ana.get("codice_fiscale"),
        "partita_iva": ana.get("partita_iva"),
        "forma_giuridica": ana.get("forma_giuridica"),
        "qualifica_registro": ana.get("qualifica_registro"),
        "regime_fiscale": ana.get("regime_fiscale"),
        "numero_rea": ana.get("numero_rea"),
        "camera_commercio": ana.get("camera_commercio"),
        # Sede
        "indirizzo": sede.get("indirizzo"),
        "cap": sede.get("cap"),
        "comune": sede.get("comune"),
        "provincia": sede.get("provincia"),
        "regione": sede.get("regione"),
        "area_geografica": sede.get("area_geografica"),
        "zona_zes": sede.get("zona_zes", False),
        "zona_mezzogiorno": sede.get("zona_mezzogiorno", False),
        # Contatti
        "pec": contatti.get("pec"),
        # Attività
        "data_inizio": att.get("data_inizio"),
        "anni_attivita": att.get("anni_attivita"),
        "ateco": att.get("ateco_2025"),
        "ateco_descrizione": att.get("ateco_descrizione"),
        "settore_principale": att.get("settore_principale"),
        # Dimensione
        "dipendenti": dim.get("dipendenti", 0),
        "micro_impresa": dim.get("micro_impresa", True),
        "fatturato_max": dim.get("fatturato_stimato_max", 85000),
        # Certificazioni
        "soa": cert.get("soa"),
        "iso_9001": cert.get("iso_9001", False),
        "iso_27001": cert.get("iso_27001", False),
        # Eligibility (hard stops e vantaggi)
        "hard_stops": elig.get("HARD_STOP", []),
        "yellow_flags": elig.get("YELLOW_FLAG", []),
        "vantaggi": elig.get("VANTAGGI", []),
    }


def run(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        # ── 1. Insert La Monica Luciano P.IVA ──────────────────────────────────
        print("Inserimento soggetto: La Monica Luciano P.IVA...")

        profile_data = json.loads(PROFILE_PATH.read_text())
        soggetto_profilo = build_soggetto_profilo(profile_data)
        ana = profile_data.get("anagrafica", {})

        cur.execute("""
            INSERT INTO soggetti (slug, nome, forma_giuridica, regime_fiscale, profilo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                nome            = EXCLUDED.nome,
                forma_giuridica = EXCLUDED.forma_giuridica,
                regime_fiscale  = EXCLUDED.regime_fiscale,
                profilo         = EXCLUDED.profilo,
                updated_at      = NOW()
            RETURNING id
        """, (
            "lamonica_piva",
            "La Monica Luciano — P.IVA",
            ana.get("forma_giuridica", "impresa individuale"),
            ana.get("regime_fiscale", "forfettario"),
            json.dumps(soggetto_profilo),
        ))
        soggetto_id = cur.fetchone()[0]
        print(f"  → soggetto_id = {soggetto_id}")

        # ── 2. Update projects.soggetto_id ─────────────────────────────────────
        print("Aggiornamento projects.soggetto_id...")
        cur.execute("""
            UPDATE projects
            SET soggetto_id = %s
            WHERE soggetto_id IS NULL
            RETURNING id, slug, nome
        """, (soggetto_id,))
        updated_projects = cur.fetchall()
        for row in updated_projects:
            print(f"  → project {row[0]} ({row[2]}) → soggetto_id = {soggetto_id}")

        # ── 3. Update project_evaluations.soggetto_id ─────────────────────────
        print("Aggiornamento project_evaluations.soggetto_id...")
        cur.execute("""
            UPDATE project_evaluations pe
            SET soggetto_id = p.soggetto_id
            FROM projects p
            WHERE pe.project_id = p.id
              AND pe.soggetto_id IS NULL
              AND p.soggetto_id IS NOT NULL
        """)
        print(f"  → {cur.rowcount} project_evaluations aggiornati")


def main() -> None:
    print(f"Connessione a: {DATABASE_URL.split('@')[-1]}")  # no credenziali in output
    with psycopg.connect(DATABASE_URL) as conn:
        run(conn)
        conn.commit()
    print("Migration 010 completata.")


if __name__ == "__main__":
    main()
