-- 007: Add short description to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS descrizione_breve TEXT;
