-- Migration 003 — Schema fixes (idempotent)
-- Run: psql $DATABASE_URL -f migrations/003_fixes.sql
-- Required for installs that ran 001_init.sql before 2026-03-02 fixes.

-- 1. Rename score_compatibilita → score (all code uses 'score')
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='bandi' AND column_name='score_compatibilita'
    ) THEN
        ALTER TABLE bandi RENAME COLUMN score_compatibilita TO score;
        RAISE NOTICE 'Renamed score_compatibilita → score';
    ELSE
        RAISE NOTICE 'Column score already correct — skip';
    END IF;
END $$;

-- 2. Fix bando_documenti_generati schema
--    Old: tipo TEXT, file_path TEXT, bozza BOOLEAN, approvato BOOLEAN
--    New: tipo_documento TEXT, filename TEXT, stato TEXT
DO $$
BEGIN
    -- Add tipo_documento if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='bando_documenti_generati' AND column_name='tipo_documento'
    ) THEN
        ALTER TABLE bando_documenti_generati ADD COLUMN tipo_documento TEXT;
        -- Migrate existing data
        UPDATE bando_documenti_generati SET tipo_documento = tipo WHERE tipo IS NOT NULL;
        RAISE NOTICE 'Added tipo_documento column';
    END IF;

    -- Add filename if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='bando_documenti_generati' AND column_name='filename'
    ) THEN
        ALTER TABLE bando_documenti_generati ADD COLUMN filename TEXT;
        RAISE NOTICE 'Added filename column';
    END IF;

    -- Add stato if missing (replaces bozza/approvato booleans)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='bando_documenti_generati' AND column_name='stato'
    ) THEN
        ALTER TABLE bando_documenti_generati
            ADD COLUMN stato TEXT DEFAULT 'bozza'
            CHECK (stato IN ('bozza','approvato','da_firmare','firmato'));
        -- Migrate existing booleans
        UPDATE bando_documenti_generati
            SET stato = CASE
                WHEN approvato = TRUE THEN 'approvato'
                ELSE 'bozza'
            END;
        RAISE NOTICE 'Added stato column (migrated from bozza/approvato)';
    END IF;
END $$;

-- 3. Add unique index on url_fonte for dedup support
CREATE UNIQUE INDEX IF NOT EXISTS bandi_url_fonte_idx
    ON bandi(url_fonte) WHERE url_fonte IS NOT NULL;

-- 4. Add performance indexes if missing
CREATE INDEX IF NOT EXISTS bandi_stato_idx ON bandi(stato);
CREATE INDEX IF NOT EXISTS bandi_data_scadenza_idx ON bandi(data_scadenza);
CREATE INDEX IF NOT EXISTS bandi_portale_idx ON bandi(portale);
CREATE INDEX IF NOT EXISTS bandi_first_seen_idx ON bandi(first_seen_at);
