-- Migration 001 — Main tables
-- Run: psql $DATABASE_URL -f migrations/001_init.sql

CREATE TABLE IF NOT EXISTS bandi (
    id                    SERIAL PRIMARY KEY,
    uuid                  UUID UNIQUE DEFAULT gen_random_uuid(),
    titolo                TEXT NOT NULL,
    ente_erogatore        TEXT,
    url_fonte             TEXT,
    portale               TEXT,
    data_pubblicazione    DATE,
    data_scadenza         DATE,
    budget_totale         NUMERIC(15,2),
    importo_max           NUMERIC(15,2),
    tipo_beneficiario     TEXT[],
    regioni_ammesse       TEXT[],
    fatturato_minimo      NUMERIC(15,2),
    dipendenti_minimi     INT,
    anzianita_minima_anni INT,
    soa_richiesta         BOOLEAN DEFAULT FALSE,
    certificazioni_richieste TEXT[],
    settori_ateco         TEXT[],
    score                 INT,
    stato                 TEXT DEFAULT 'nuovo'
                          CHECK (stato IN ('nuovo','analisi','idoneo','scartato',
                                           'lavorazione','pronto','inviato','archiviato')),
    motivo_scarto         TEXT,
    dedup_hash            TEXT UNIQUE,
    parent_bando_id       INT REFERENCES bandi(id),
    first_seen_at         TIMESTAMPTZ DEFAULT NOW(),
    data_invio            TIMESTAMPTZ,
    protocollo_ricevuto   TEXT,
    raw_text              TEXT,
    metadata              JSONB,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bando_documenti (
    id             SERIAL PRIMARY KEY,
    bando_id       INT REFERENCES bandi(id) ON DELETE CASCADE,
    tipo           TEXT,
    filename       TEXT,
    file_path      TEXT,
    testo_estratto TEXT,
    parsed_at      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bando_requisiti (
    id                    SERIAL PRIMARY KEY,
    bando_id              INT REFERENCES bandi(id) ON DELETE CASCADE,
    tipo                  TEXT CHECK (tipo IN ('hard','soft','bonus')),
    categoria             TEXT,
    descrizione_originale TEXT,
    valore_richiesto      TEXT,
    soddisfatto           BOOLEAN,
    semaforo              TEXT CHECK (semaforo IN ('verde','giallo','rosso')),
    fonte_evidenza        TEXT,
    nota                  TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bando_documenti_generati (
    id              SERIAL PRIMARY KEY,
    bando_id        INT REFERENCES bandi(id) ON DELETE CASCADE,
    tipo_documento  TEXT,
    filename        TEXT,
    versione        INT DEFAULT 1,
    stato           TEXT DEFAULT 'bozza'
                    CHECK (stato IN ('bozza','approvato','da_firmare','firmato')),
    note_revisione  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at on bandi
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bandi_updated_at ON bandi;
CREATE TRIGGER bandi_updated_at
    BEFORE UPDATE ON bandi
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Unique index on url_fonte (partial: only for non-null URLs)
CREATE UNIQUE INDEX IF NOT EXISTS bandi_url_fonte_idx
    ON bandi(url_fonte) WHERE url_fonte IS NOT NULL;

-- Index for common queries
CREATE INDEX IF NOT EXISTS bandi_stato_idx ON bandi(stato);
CREATE INDEX IF NOT EXISTS bandi_data_scadenza_idx ON bandi(data_scadenza);
CREATE INDEX IF NOT EXISTS bandi_portale_idx ON bandi(portale);
CREATE INDEX IF NOT EXISTS bandi_first_seen_idx ON bandi(first_seen_at);
