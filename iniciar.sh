#!/usr/bin/env bash
# Sobe banco, API e painel no macOS ou no Linux (o mesmo que o iniciar.ps1 faz no Windows): ./iniciar.sh
# Painel em http://127.0.0.1:8501. Ctrl+C para a API e o painel; o banco continua no Docker.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -f .env ] || { echo "Crie o .env a partir do .env.example e defina POSTGRES_PASSWORD." >&2; exit 1; }

docker compose up -d --wait

pw=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
export DATABASE_URL="postgresql://radar:$pw@127.0.0.1:54329/radar"
export RADAR_TEST_DATABASE_URL="postgresql://radar:$pw@127.0.0.1:54329/postgres"
RADAR_API_PASSWORD=$(openssl rand -hex 16)
export RADAR_API_PASSWORD
"$PY" scripts/create_api_role.py
export API_DATABASE_URL="postgresql://radar_api:$RADAR_API_PASSWORD@127.0.0.1:54329/radar"

"$PY" scripts/run_dashboard.py &
dashboard=$!
trap 'kill "$dashboard" 2>/dev/null' EXIT
if command -v open >/dev/null; then open http://127.0.0.1:8501; elif command -v xdg-open >/dev/null; then xdg-open http://127.0.0.1:8501; fi

"$PY" scripts/run_api.py
