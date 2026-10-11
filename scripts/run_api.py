"""Sobe a API de leitura em modo de desenvolvimento.

Uso: python scripts/run_api.py [--host 127.0.0.1] [--port 8000]
A conexão vem de API_DATABASE_URL (usuário somente leitura; ver scripts/create_api_role.py).
Documentação interativa em http://127.0.0.1:8000/docs. Escuta só em loopback por padrão.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from radar_combustiveis.api.app import create_app  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        app = create_app()
    except ValueError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
