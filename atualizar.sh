#!/usr/bin/env bash
# Atualização semanal em um comando no macOS ou no Linux (o mesmo que o atualizar.ps1): ./atualizar.sh
# Precisa do Docker aberto. Sobe o banco, prepara as conexões e roda scripts/weekly_refresh.py; se a ANP
# ainda não publicou semana nova, termina sem mudar nada. Argumentos extras vão para o script (ex.: --dry-run).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -f .env ] || { echo "Crie o .env a partir do .env.example e defina POSTGRES_PASSWORD." >&2; exit 1; }

if ! docker compose up -d --wait; then
    echo "O banco não subiu. O Docker está aberto?" >&2
    exit 1
fi

pw=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
export DATABASE_URL="postgresql://radar:$pw@127.0.0.1:54329/radar"
# Senha nova a cada execução, como no iniciar.sh; se a API estiver aberta, reinicie-a depois.
RADAR_API_PASSWORD=$(openssl rand -hex 16)
export RADAR_API_PASSWORD
"$PY" scripts/create_api_role.py
export API_DATABASE_URL="postgresql://radar_api:$RADAR_API_PASSWORD@127.0.0.1:54329/radar"

exec "$PY" scripts/weekly_refresh.py "$@"
