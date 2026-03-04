-- Migration 002 — pgvector for company profile embeddings
-- Run AFTER 001_init.sql
-- Requires: PostgreSQL + pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS company_embeddings (
    id         SERIAL PRIMARY KEY,
    categoria  TEXT,
    contenuto  TEXT,
    embedding  vector(1536),
    metadata   JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS company_embeddings_ivfflat
    ON company_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
