#!/bin/sh
# Starts the engine API (port 8000) and the frontend (http://localhost:8080) from a fresh clone.
# Needs python3 (3.12) and node >= 20. Ctrl+C stops both. Other ports: API_PORT=8001 PORT=8081 scripts/start.sh
#
# The frontend runs on Vite's server: it forwards /api to the API (frontend/vite.config.ts,
# ARENA_API_URL), which a static build would not do.
set -eu
API_PORT=${API_PORT:-8000}
PORT=${PORT:-8080}
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-api.txt
(cd frontend && npm ci --no-audit --no-fund)
.venv/bin/uvicorn api.main:app --port "$API_PORT" &
api=$!
trap 'kill $api 2>/dev/null || true' EXIT INT TERM
cd frontend && ARENA_API_URL="http://127.0.0.1:$API_PORT" npm run dev -- --port "$PORT"
