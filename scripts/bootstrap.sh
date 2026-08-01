#!/usr/bin/env bash
set -euo pipefail
# Servease Backend — one-command development bootstrap
# Usage: bash scripts/bootstrap.sh
# Prerequisites: Docker, Python 3.13+ (Docker Compose v2)

cd "$(dirname "$0")/.."

echo "=== Servease Backend — Bootstrap ==="

# 1. Python virtual env + deps
if [ ! -d venv ]; then
    echo "[1/5] Creating virtual environment…"
    python3 -m venv venv
fi
source venv/bin/activate
echo "[2/5] Installing Python dependencies…"
pip install -q -r requirements.txt

# 2. .env
if [ ! -f .env ]; then
    echo "[3/5] Creating .env from .env.example…"
    cp .env.example .env
fi

# 3. Docker infra (Postgres + Redis + Supabase)
echo "[4/5] Starting Postgres + Redis + Supabase (Docker Compose)…"
docker compose up -d postgres redis supabase-db supabase-kong supabase-auth supabase-rest supabase-realtime supabase-storage supabase-meta supabase-studio
echo "       Waiting for services…"
until docker compose exec -T postgres pg_isready -U servease_dev >/dev/null 2>&1; do sleep 2; done
echo "       Postgres ready"
until docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do sleep 1; done
echo "       Redis ready"
until curl -s -o /dev/null -w "" http://127.0.0.1:54321/auth/v1/settings 2>/dev/null; do sleep 3; done
echo "       Supabase Auth ready"

# 4. Django migrate + seed
echo "[5/5] Running migrations + seed…"
python manage.py migrate --noinput
python manage.py seed

echo ""
echo "=== Done! ==="
echo "   Backend:       http://localhost:8000"
echo "   Health:        http://localhost:8000/health/"
echo "   API Docs:      http://localhost:8000/api/docs/"
echo "   Supabase Auth: http://localhost:54321/auth/v1"
echo "   Supabase Studio: http://localhost:54323"
echo ""
echo "   Dev server with hot reload:"
echo "     just dev"
echo "     # or: source venv/bin/activate && uvicorn Servease_Backend.asgi:application --reload --host 0.0.0.0 --port 8000"
