-- Migration 006: Extended bandi fields + GIN indexes for advanced filters
-- Sprint 6: UI Redesign + Repository 360°

-- Fields extracted by parser (schema.py) but previously not stored in dedicated columns
ALTER TABLE bandi ADD COLUMN IF NOT EXISTS criteri_valutazione JSONB;
ALTER TABLE bandi ADD COLUMN IF NOT EXISTS documenti_da_allegare TEXT[];
ALTER TABLE bandi ADD COLUMN IF NOT EXISTS parsing_confidence TEXT;
ALTER TABLE bandi ADD COLUMN IF NOT EXISTS parsing_notes TEXT;

-- GIN indexes for efficient array filtering (used by advanced sidebar filters)
CREATE INDEX IF NOT EXISTS idx_bandi_regioni_gin ON bandi USING GIN (regioni_ammesse);
CREATE INDEX IF NOT EXISTS idx_bandi_tipo_ben_gin ON bandi USING GIN (tipo_beneficiario);
CREATE INDEX IF NOT EXISTS idx_bandi_ateco_gin ON bandi USING GIN (settori_ateco);
CREATE INDEX IF NOT EXISTS idx_bandi_tipo_fin ON bandi (tipo_finanziamento);
