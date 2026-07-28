#!/usr/bin/env bash
set -euo pipefail
# Production certification test
cd "$(dirname "$0")/.."

echo "=== Production Certification ==="
source venv/bin/activate

# Ensure server is running
if ! curl -s -o /dev/null -w "" http://127.0.0.1:8000/health/ 2>/dev/null; then
    echo "Starting server…"
    uvicorn Servease_Backend.asgi:application --host 127.0.0.1 --port 8000 &
    sleep 3
fi

python /tmp/production_cert.py
