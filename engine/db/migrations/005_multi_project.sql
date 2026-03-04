-- Migration 005 — Multi-project architecture (idempotent)
-- Adds projects table + project_evaluations for per-project bando assessment.
-- Existing bandi data (score, stato) is migrated to project_evaluations for project #1.

-- ── 1. Projects table ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id               SERIAL PRIMARY KEY,
    slug             TEXT UNIQUE NOT NULL,
    nome             TEXT NOT NULL,
    descrizione      TEXT,
    profilo          JSONB NOT NULL,
    skills           JSONB,
    scoring_rules    JSONB NOT NULL,
    telegram_chat_id TEXT,
    telegram_prefix  TEXT,
    attivo           BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

DROP TRIGGER IF EXISTS projects_updated_at ON projects;
CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 2. Project evaluations table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_evaluations (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    bando_id            INT NOT NULL REFERENCES bandi(id) ON DELETE CASCADE,
    score               INT,
    stato               TEXT DEFAULT 'nuovo'
                        CHECK (stato IN ('nuovo','analisi','idoneo','scartato',
                                         'lavorazione','pronto','inviato','archiviato')),
    motivo_scarto       TEXT,
    hard_stop_reason    TEXT,
    score_breakdown     JSONB,
    gap_analysis        JSONB,
    yellow_flags        JSONB,
    data_invio          TIMESTAMPTZ,
    protocollo_ricevuto TEXT,
    evaluated_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, bando_id)
);

DROP TRIGGER IF EXISTS pe_updated_at ON project_evaluations;
CREATE TRIGGER pe_updated_at
    BEFORE UPDATE ON project_evaluations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX IF NOT EXISTS idx_pe_project_stato ON project_evaluations(project_id, stato);
CREATE INDEX IF NOT EXISTS idx_pe_bando ON project_evaluations(bando_id);
CREATE INDEX IF NOT EXISTS idx_pe_score ON project_evaluations(project_id, score);

-- ── 3. Add project_id to related tables ────────────────────────────────────────
ALTER TABLE bando_documenti_generati ADD COLUMN IF NOT EXISTS project_id INT REFERENCES projects(id);
ALTER TABLE bando_requisiti ADD COLUMN IF NOT EXISTS project_id INT REFERENCES projects(id);
ALTER TABLE company_embeddings ADD COLUMN IF NOT EXISTS project_id INT REFERENCES projects(id);

-- ── 4. Deprecation comments on bandi columns ──────────────────────────────────
COMMENT ON COLUMN bandi.score IS 'DEPRECATED: Use project_evaluations.score';
COMMENT ON COLUMN bandi.stato IS 'DEPRECATED: Use project_evaluations.stato';
COMMENT ON COLUMN bandi.motivo_scarto IS 'DEPRECATED: Use project_evaluations.motivo_scarto';
COMMENT ON COLUMN bandi.data_invio IS 'DEPRECATED: Use project_evaluations.data_invio';
COMMENT ON COLUMN bandi.protocollo_ricevuto IS 'DEPRECATED: Use project_evaluations.protocollo_ricevuto';
