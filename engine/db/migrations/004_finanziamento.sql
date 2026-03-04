-- Migration 004 — Campi tipo finanziamento (idempotent)
-- Aggiunge info sul tipo di finanziamento e quota a fondo perduto.

ALTER TABLE bandi ADD COLUMN IF NOT EXISTS tipo_finanziamento TEXT
    CHECK (tipo_finanziamento IN (
        'fondo_perduto',
        'prestito_agevolato',
        'mix',
        'contributo_conto_capitale',
        'voucher',
        'altro'
    ));

ALTER TABLE bandi ADD COLUMN IF NOT EXISTS aliquota_fondo_perduto NUMERIC(5,2);
-- Percentuale 0-100 della quota a fondo perduto (es. 50.00 = 50%)
-- NULL = non specificato / non applicabile

CREATE INDEX IF NOT EXISTS bandi_tipo_finanziamento_idx ON bandi(tipo_finanziamento);
