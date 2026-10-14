"""Demonstrativo público (Streamlit Community Cloud): o painel lendo o pacote instantâneo.

Ponto de entrada configurado na hospedagem. Sem API nem banco: `RADAR_SNAPSHOT` aponta para o
pacote commitado em `snapshot/`, gerado por `scripts/build_snapshot.py`. Localmente:
    streamlit run demo/streamlit_app.py
"""

import os
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("RADAR_SNAPSHOT", str(ROOT / "snapshot" / "radar-sp.json.gz"))
runpy.run_path(str(ROOT / "src" / "radar_combustiveis" / "dashboard" / "app.py"), run_name="__main__")
