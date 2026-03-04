#!/bin/bash
# setup.sh — First-time setup for bandi_researcher
# Run from project root: bash setup.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ENGINE_DIR="$PROJECT_ROOT/engine"

echo ""
echo "🎯 Bandi Researcher — Setup"
echo "================================"

# ── 1. .env ───────────────────────────────────────────────────────────────────
echo ""
echo "📋 Step 1/5 — Environment variables"
if [ ! -f "$ENGINE_DIR/.env" ]; then
    cp "$ENGINE_DIR/.env.example" "$ENGINE_DIR/.env"
    echo "  ✅ Created engine/.env from .env.example"
    echo "  ⚠️  IMPORTANT: edit engine/.env and add your ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN"
else
    echo "  ✅ engine/.env already exists — skipping"
fi

# ── 2. Python deps ────────────────────────────────────────────────────────────
echo ""
echo "🐍 Step 2/5 — Python dependencies"
if command -v pip3 &>/dev/null; then
    pip3 install -r "$ENGINE_DIR/requirements.txt" --quiet
    echo "  ✅ Dependencies installed"
else
    echo "  ❌ pip3 not found — install Python 3.12 first"
    exit 1
fi

# ── 3. Docker ─────────────────────────────────────────────────────────────────
echo ""
echo "🐳 Step 3/5 — Docker services"
if command -v docker &>/dev/null; then
    cd "$ENGINE_DIR"
    docker compose up -d postgres redis
    echo "  ✅ PostgreSQL and Redis started"
    echo "  ⏳ Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 15); do
        if docker compose exec -T postgres pg_isready -U bandi -d bandi_db &>/dev/null; then
            echo "  ✅ PostgreSQL is ready"
            break
        fi
        sleep 2
        if [ $i -eq 15 ]; then
            echo "  ❌ PostgreSQL did not start in time"
            exit 1
        fi
    done
else
    echo "  ❌ Docker not found — install Docker Desktop first"
    exit 1
fi

# ── 4. DB migrations ──────────────────────────────────────────────────────────
echo ""
echo "🗄️  Step 4/5 — Database schema"
cd "$ENGINE_DIR"

source .env 2>/dev/null || true
DB_URL="${DATABASE_URL:-postgresql://bandi:bandi@localhost:5432/bandi_db}"

docker compose exec -T postgres psql -U bandi -d bandi_db \
    -f /dev/stdin < db/migrations/001_init.sql
echo "  ✅ Migration 001_init.sql applied"

docker compose exec -T postgres psql -U bandi -d bandi_db \
    -f /dev/stdin < db/migrations/002_pgvector.sql
echo "  ✅ Migration 002_pgvector.sql applied"

# ── 5. Load company profile ───────────────────────────────────────────────────
echo ""
echo "👤 Step 5/5 — Load company profile into pgvector"
if grep -q "your_api_key_here" "$ENGINE_DIR/.env"; then
    echo "  ⚠️  ANTHROPIC_API_KEY not set — skipping profile load"
    echo "     → Edit engine/.env then run: python3 -m engine.db.load_profile"
else
    cd "$PROJECT_ROOT"
    python3 -m engine.db.load_profile && echo "  ✅ Company profile loaded into pgvector"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit engine/.env and add ANTHROPIC_API_KEY + TELEGRAM_BOT_TOKEN"
echo "  2. Start Streamlit:  cd engine && streamlit run ui/app.py"
echo "  3. Start Prefect UI: cd engine && docker compose up -d prefect"
echo "  4. Run first scan:   cd engine && scrapy crawl invitalia"
echo ""
