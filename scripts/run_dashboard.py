"""Sobe o painel (Streamlit) em modo de desenvolvimento.

Uso: python scripts/run_dashboard.py [--port 8501]
Precisa da API no ar (scripts/run_api.py); o endereço vem de RADAR_API_URL
(padrão http://127.0.0.1:8000). Escuta só em loopback.
"""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "radar_combustiveis" / "dashboard" / "app.py"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args(argv)
    command = [sys.executable, "-m", "streamlit", "run", str(APP), "--server.address", "127.0.0.1",
               "--server.port", str(args.port), "--server.headless", "true",
               "--browser.gatherUsageStats", "false"]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
