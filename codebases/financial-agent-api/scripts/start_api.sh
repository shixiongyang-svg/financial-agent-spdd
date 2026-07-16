#!/usr/bin/env bash
set -euo pipefail

echo "Running data initialization..."
uv run python -m financial_agent_api.scripts.initialize_data

echo "Starting API server..."
exec uv run uvicorn financial_agent_api.main:app --host 0.0.0.0 --port 8000
