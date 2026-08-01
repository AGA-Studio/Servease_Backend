#!/usr/bin/env bash
set -euo pipefail
# Quick dev start — assumes bootstrap.sh already ran once
cd "$(dirname "$0")/.."

echo "=== Starting dev services ==="
source venv/bin/activate

echo "[1] Postgres + Redis + Supabase…"
docker compose up -d postgres redis supabase-db supabase-kong supabase-auth supabase-rest supabase-realtime supabase-storage supabase-meta supabase-studio

echo "[2] Waiting for Supabase Auth…"
until curl -s -o /dev/null -w "" http://127.0.0.1:54321/auth/v1/settings 2>/dev/null; do sleep 2; done
echo "       Supabase ready"

echo "[3] Django server (uvicorn + reload)…"
uvicorn Servease_Backend.asgi:application --reload --host 0.0.0.0 --port 8000
