"""Demonstrativo público (Streamlit Community Cloud): o painel lendo o pacote instantâneo.

Ponto de entrada configurado na hospedagem. Sem API nem banco: `RADAR_SNAPSHOT` aponta para o
pacote commitado em `snapshot/`, gerado por `scripts/build_snapshot.py`. Localmente:
    streamlit run demo/streamlit_app.py
"""

import os
from pathlib import Path
import runpy
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "radar_combustiveis"
SNAPSHOT = ROOT / "snapshot" / "radar-sp.json.gz"
os.environ.setdefault("RADAR_SNAPSHOT", str(SNAPSHOT))


def _version():
    """Assinatura do código e do pacote: muda quando um push atualiza qualquer um dos dois."""
    files = [*SRC.rglob("*.py"), Path(os.environ["RADAR_SNAPSHOT"])]
    return tuple(sorted((str(f), f.stat().st_mtime_ns) for f in files if f.exists()))


# O Streamlit só recarrega módulos da pasta do ponto de entrada (demo/); o painel está em src/.
# Depois de um push, o app rodaria o app.py novo com módulos e pacote antigos na memória
# (AttributeError em views). Se algo mudou, descarta módulos e caches antes de rodar.
version = _version()
if getattr(sys, "_radar_demo_version", None) != version:  # primeira vez: limpa também
    for name in [m for m in sys.modules if m == "radar_combustiveis" or m.startswith("radar_combustiveis.")]:
        del sys.modules[name]
    st.cache_data.clear()
    st.cache_resource.clear()
sys._radar_demo_version = version

runpy.run_path(str(SRC / "dashboard" / "app.py"), run_name="__main__")
