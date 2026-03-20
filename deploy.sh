#!/bin/bash
set -euo pipefail

echo "=== Tool Bandi — Deploy ==="

# 1. Pull ultimo codice
echo "1/5 Pulling latest code..."
git pull origin main

# 2. Build containers
echo "2/5 Building containers..."
docker compose build --no-cache

# 3. Avvia DB (se non running)
echo "3/5 Starting DB..."
docker compose up -d db
echo "Waiting for DB healthcheck..."
sleep 5

# 4. Esegui migrazioni SQL (idempotent)
echo "4/5 Running migrations..."
DB_USER="${DB_USER:-bandi}"
DB_NAME="${DB_NAME:-bandi_db}"

for f in engine/db/migrations/0{01,02,03,04,05,06,07,08,09,10}*.sql; do
    if [ -f "$f" ]; then
        BASENAME=$(basename "$f")
        echo "  → $BASENAME"
        docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -f "/migrations/$BASENAME" 2>/dev/null || true
    fi
done

# Python seed scripts
for f in engine/db/migrations/0{05,10}*.py; do
    if [ -f "$f" ]; then
        echo "  → $(basename $f) (Python — run manually if needed)"
    fi
done

echo "  Note: Migrations 011-014 are NOT auto-deployed (new tables). Run manually if needed."

# 5. Avvia/riavvia web
echo "5/5 Starting web..."
docker compose up -d web

# 6. Smoke test
echo "Waiting for web startup..."
sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "✅ Deploy OK — http://localhost:8000 (HTTP $HTTP_CODE)"
else
    echo "❌ Deploy FAILED — HTTP $HTTP_CODE"
    docker compose logs web --tail 50
    exit 1
fi

echo "=== Deploy completato ==="
