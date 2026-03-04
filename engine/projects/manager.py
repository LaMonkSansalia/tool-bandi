"""
Project manager — CRUD operations for multi-project architecture.
Loads project profiles from DB, caches them, provides helpers for
the eligibility engine and UI.
"""
from __future__ import annotations
import logging

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from engine.config import DATABASE_URL

logger = logging.getLogger(__name__)


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def get_active_projects() -> list[dict]:
    """Return all active projects (id, slug, nome, attivo)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, slug, nome, descrizione, descrizione_breve,
                       attivo, telegram_chat_id, telegram_prefix
                FROM projects
                WHERE attivo = TRUE
                ORDER BY id
            """)
            return [dict(row) for row in cur.fetchall()]


def get_project(project_id: int) -> dict | None:
    """Load a full project record by id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_project_by_slug(slug: str) -> dict | None:
    """Load a full project record by slug."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM projects WHERE slug = %s", (slug,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_project_profile(project_id: int) -> dict | None:
    """Load just the profilo JSONB for a project."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT profilo FROM projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            return row["profilo"] if row else None


def get_project_scoring_rules(project_id: int) -> dict | None:
    """Load scoring_rules JSONB for a project."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT scoring_rules FROM projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            return row["scoring_rules"] if row else None


def get_project_skills(project_id: int) -> dict | None:
    """Load skills JSONB for a project."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT skills FROM projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            return row["skills"] if row else None


def create_project(
    slug: str,
    nome: str,
    profilo: dict,
    scoring_rules: dict,
    descrizione: str | None = None,
    descrizione_breve: str | None = None,
    skills: dict | None = None,
    telegram_chat_id: str | None = None,
    telegram_prefix: str | None = None,
) -> int:
    """Create a new project. Returns the new project id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO projects
                    (slug, nome, descrizione, descrizione_breve, profilo, skills,
                     scoring_rules, telegram_chat_id, telegram_prefix)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                slug, nome, descrizione, descrizione_breve,
                Json(profilo), Json(skills) if skills else None,
                Json(scoring_rules),
                telegram_chat_id, telegram_prefix,
            ))
            project_id = cur.fetchone()["id"]
            conn.commit()
            logger.info(f"Created project {slug} (id={project_id})")
            return project_id


def update_project(project_id: int, **fields) -> bool:
    """
    Update project fields. Accepts any combination of:
    nome, descrizione, profilo, skills, scoring_rules,
    telegram_chat_id, telegram_prefix, attivo.
    """
    allowed = {
        "nome", "descrizione", "descrizione_breve", "profilo", "skills",
        "scoring_rules", "telegram_chat_id", "telegram_prefix", "attivo",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    json_fields = {"profilo", "skills", "scoring_rules"}
    set_clauses = []
    params = []
    for k, v in updates.items():
        set_clauses.append(f"{k} = %s")
        params.append(Json(v) if k in json_fields else v)

    params.append(project_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = %s",
                params,
            )
            conn.commit()
            return cur.rowcount > 0


def get_project_stats(project_id: int) -> dict:
    """Get evaluation stats for a project."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as totale,
                    COUNT(*) FILTER (WHERE stato = 'idoneo') as idonei,
                    COUNT(*) FILTER (WHERE stato = 'scartato') as scartati,
                    COUNT(*) FILTER (WHERE stato = 'nuovo') as nuovi,
                    COUNT(*) FILTER (WHERE stato = 'analisi') as in_analisi,
                    COUNT(*) FILTER (WHERE stato IN ('lavorazione','pronto','inviato')) as in_lavorazione,
                    COUNT(*) FILTER (WHERE stato = 'archiviato') as archiviati,
                    ROUND(AVG(score) FILTER (WHERE score IS NOT NULL), 1) as score_medio
                FROM project_evaluations
                WHERE project_id = %s
            """, (project_id,))
            row = cur.fetchone()
            return dict(row) if row else {}


# ── Evaluation CRUD ─────────────────────────────────────────────────────────────

def upsert_evaluation(
    project_id: int,
    bando_id: int,
    score: int | None = None,
    stato: str = "nuovo",
    motivo_scarto: str | None = None,
    hard_stop_reason: str | None = None,
    score_breakdown: dict | None = None,
    gap_analysis: dict | None = None,
    yellow_flags: list | None = None,
) -> int:
    """Insert or update evaluation for a project+bando pair. Returns evaluation id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO project_evaluations
                    (project_id, bando_id, score, stato, motivo_scarto,
                     hard_stop_reason, score_breakdown, gap_analysis,
                     yellow_flags, evaluated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (project_id, bando_id) DO UPDATE SET
                    score = EXCLUDED.score,
                    stato = EXCLUDED.stato,
                    motivo_scarto = EXCLUDED.motivo_scarto,
                    hard_stop_reason = EXCLUDED.hard_stop_reason,
                    score_breakdown = EXCLUDED.score_breakdown,
                    gap_analysis = EXCLUDED.gap_analysis,
                    yellow_flags = EXCLUDED.yellow_flags,
                    evaluated_at = NOW()
                RETURNING id
            """, (
                project_id, bando_id, score, stato,
                motivo_scarto, hard_stop_reason,
                Json(score_breakdown) if score_breakdown else None,
                Json(gap_analysis) if gap_analysis else None,
                Json(yellow_flags) if yellow_flags else None,
            ))
            eval_id = cur.fetchone()["id"]
            conn.commit()
            return eval_id


def get_evaluation(project_id: int, bando_id: int) -> dict | None:
    """Get evaluation for a specific project+bando pair."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM project_evaluations
                WHERE project_id = %s AND bando_id = %s
            """, (project_id, bando_id))
            row = cur.fetchone()
            return dict(row) if row else None


def update_evaluation_stato(project_id: int, bando_id: int, stato: str, motivo: str | None = None) -> bool:
    """Update just the stato (and optionally motivo_scarto) of an evaluation."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if motivo:
                cur.execute("""
                    UPDATE project_evaluations
                    SET stato = %s, motivo_scarto = %s
                    WHERE project_id = %s AND bando_id = %s
                """, (stato, motivo, project_id, bando_id))
            else:
                cur.execute("""
                    UPDATE project_evaluations SET stato = %s
                    WHERE project_id = %s AND bando_id = %s
                """, (stato, project_id, bando_id))
            conn.commit()
            return cur.rowcount > 0
