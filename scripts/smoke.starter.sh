#!/usr/bin/env bash
# smoke.starter.sh — Three-check smoke test (assumes containers are already running)
# Usage: BASE_URL=http://financial-agent-api.localhost.com bash scripts/smoke.starter.sh
set -euo pipefail

# Project API endpoint is exposed through nginx by default.
# `./start` ensures /etc/hosts includes financial-agent-api.localhost.com.
BASE_URL="${BASE_URL:-http://financial-agent-api.localhost.com}"

echo "=== Smoke test: $BASE_URL ==="
echo "Tip: if host resolution fails, run ./start once to bootstrap /etc/hosts."

echo "[1/3] GET /healthz"
curl -fsS "$BASE_URL/healthz" | python3 -m json.tool
echo ""

echo "[2/3] GET /readyz"
curl -fsS "$BASE_URL/readyz" | python3 -m json.tool
echo ""

echo "[3/3] POST /agent/query"
curl -fsS -X POST "$BASE_URL/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is an overdraft fee?"}' | python3 -m json.tool
echo ""

echo "=== All checks passed ==="
