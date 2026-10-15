"""Rotina semanal em um comando (Marco 12, etapa B3): decide se há semana nova e roda as etapas em ordem.

Cada etapa é um script já existente e idempotente; a rotina para na primeira falha e diz qual foi.
"Em dia" quer dizer que o pacote do demonstrativo, último passo, já tem a semana mais recente da
página da ANP. Assim uma execução que falhou no meio é refeita por inteiro na próxima, sem marcador
extra, e as etapas que já tinham terminado não duplicam nada.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import time

from .ingestion.download import parse_weekly_links

FORECAST_REPORTS = Path("data") / "processed" / "forecasting-semanal"


@dataclass(frozen=True)
class Stage:
    name: str
    script: str
    args: tuple = ()


STAGES = (
    Stage("baixar a ANP", "fetch_anp.py"),
    Stage("ingerir", "ingest_local.py"),
    Stage("qualidade", "check_quality.py"),
    Stage("carregar no banco", "load_db.py"),
    Stage("fontes externas", "fetch_external.py"),
    # O relatório do backtest commitado (reports/forecasting) é o registro do Marco 7 e fica parado.
    Stage("previsões de valor e variações incomuns", "run_forecasts.py", ("--report-dir", str(FORECAST_REPORTS))),
    Stage("previsão ao vivo e placar", "run_live.py"),
    Stage("pacote do demonstrativo", "build_snapshot.py"),
)


def latest_page_week(html):
    """Início da semana mais recente listada na página da ANP, ou None se não houver links."""
    links = parse_weekly_links(html)
    return max((link.week_start for link in links), default=None)


def snapshot_week(path):
    """Semana mais recente do pacote do demonstrativo, ou None se ele não existir ou não puder ser lido."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream).get("latest_week_start")
    except (OSError, ValueError):
        return None


def run(stages, runner, clock=time.monotonic):
    """Roda as etapas em ordem com `runner(stage) -> código de saída`; para na primeira falha."""
    results = []
    for stage in stages:
        start = clock()
        code = runner(stage)
        results.append({"stage": stage.name, "code": code, "seconds": round(clock() - start, 1)})
        if code != 0:
            break
    failed = next((r["stage"] for r in results if r["code"] != 0), None)
    return {"status": "falhou" if failed else "concluído", "failed_stage": failed, "stages": results}


def record(log_path, entry, now=None):
    """Acrescenta uma linha ao histórico das execuções (JSON por linha)."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"finished_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), **entry}
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry
