"""Resultados congelados do estudo (Marco 8 e 8b), lidos dos relatórios versionados em `reports/study/`.

Não vêm da API de propósito: são um artefato do estudo, amarrado ao commit do código e ao hash dos
dados, e não mudam quando a ANP publica semanas novas. O painel só lê e formata (ADR 0005, adendo de 2026-10-14).
"""

import json
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "study"
REPO_URL = "https://github.com/lutmaia/fuelradar"


def load(directory=None):
    """{"results": resultados.json, "descriptive": descritivo.json}, ou None se faltar algum dos dois."""
    directory = REPORTS if directory is None else directory
    try:
        return {"results": json.loads((Path(directory) / "resultados.json").read_text(encoding="utf-8")),
                "descriptive": json.loads((Path(directory) / "descritivo.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return None


def report_url(name):
    return f"{REPO_URL}/blob/main/reports/study/{name}"
