"""Gera o pacote instantâneo do demonstrativo público (painel sem API nem banco).

Uso: python scripts/build_snapshot.py [--output snapshot/radar-sp.json.gz]
Lê o banco com API_DATABASE_URL (usuário somente leitura): a API roda em processo, sem servidor, e
responde a todas as consultas que o painel faz. Sem CNPJ nem razão social no pacote (ADR 0009).
"""

import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from radar_combustiveis import snapshot  # noqa: E402
from radar_combustiveis.api.app import create_app  # noqa: E402
from radar_combustiveis.api.database import api_database_url  # noqa: E402
from radar_combustiveis.dashboard.client import ApiClient  # noqa: E402
from radar_combustiveis.db.connection import SCHEMA  # noqa: E402

DEFAULT_OUTPUT = ROOT / "snapshot" / "radar-sp.json.gz"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    url = api_database_url()
    started = time.monotonic()
    options = f"-c search_path={SCHEMA} -c default_transaction_read_only=on -c timezone=UTC"
    with TestClient(create_app(url)) as http, psycopg.connect(url, options=options, row_factory=dict_row) as conn:
        package = snapshot.build(ApiClient(http), conn)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = snapshot.write(package, args.output)
    print(f"Pacote: {args.output} · {len(package['calls'])} respostas, {len(package['history'])} séries · "
          f"{raw / 1e6:.1f} MB de JSON, {args.output.stat().st_size / 1e6:.1f} MB compactado · "
          f"semana mais recente {package['latest_week_start']} · {time.monotonic() - started:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
