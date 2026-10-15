"""Previsão de classe ao vivo (Marcos 10b e 11): calibração, registro imutável, pontuação e placar.

Uso:
  python scripts/run_live.py --fit-calibration   # uma vez: T por horizonte na validação do Marco 10
  python scripts/run_live.py                     # toda semana: prevê a semana mais recente e pontua
Lê o banco com DATABASE_URL. Registro em reports/ledger/ (commitar toda semana), calibração em
reports/modelv2/calibracao.json. Protocolo: docs/estudo/protocolo-ao-vivo.md.
"""

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.db.connection import connect, database_url  # noqa: E402
from radar_combustiveis.db.migrate import apply_migrations  # noqa: E402
from radar_combustiveis.forecasting.panel import build_panel, load_rows  # noqa: E402
from radar_combustiveis.modelv2 import data, live, report, store  # noqa: E402
from radar_combustiveis.modelv2.features import Features  # noqa: E402

LEDGER = ROOT / "reports" / "ledger"
CALIBRATION = ROOT / "reports" / "modelv2" / "calibracao.json"
VALIDATION_POINTS = ROOT / "data" / "processed" / "modelv2" / "validacao.csv.gz"


def fit_calibration():
    if CALIBRATION.exists():
        print(f"{CALIBRATION.name} já existe: a calibração é ajustada uma única vez (protocolo, seção 1).")
        return 1
    points = pd.read_csv(VALIDATION_POINTS)
    result = live.fit_temperatures(points)
    CALIBRATION.write_text(report.dumps({"model": live.MODEL_KEY, "source": "validação do Marco 10",
                                         "horizons": result}), encoding="utf-8")
    for h, r in result.items():
        print(f"h={h}: T = {r['temperature']:.4f} · erro de calibração {r['ece_before']:.4f} → {r['ece_after']:.4f} "
              f"(na própria validação; otimista) · {r['points']} pontos")
    return 0


def weekly():
    if not CALIBRATION.exists():
        print("Falta a calibração: rode antes com --fit-calibration.")
        return 1
    temperatures = {int(h): r["temperature"] for h, r in json.loads(CALIBRATION.read_text("utf-8"))["horizons"].items()}
    problems = live.check_manifest(LEDGER)
    if problems:
        print(f"Registro alterado depois de gravado: {problems}. Nada foi feito.")
        return 1
    with connect(database_url()) as conn:
        apply_migrations(conn)
        panel = build_panel(load_rows(conn, "SP"))
        features = Features(panel, data.load_external(conn))
        forecasts = live.predict(panel, features, live.train(panel, features), temperatures)
        written = live.write_ledger(forecasts, LEDGER)
        if written["status"] == "gravado":
            print(f"Previsões da semana {panel.weeks[-1]}: {written['rows']} linhas em {written['path'].name}")
        else:
            print(f"A semana {panel.weeks[-1]} já estava registrada; o registro não foi alterado.")
        ledger = live.read_ledgers(LEDGER)
        print(f"Banco: {store.save_forecasts(conn, ledger)} previsão(ões) nova(s)")
        scored = live.score(ledger, panel)
        board = live.scoreboard(scored)
        board.update({"ledger_origins": sorted({w.isoformat() for w in ledger["origin_week"]}),
                      "latest_data_week": panel.weeks[-1]})
        store.save_scoreboard(conn, board)
    (LEDGER / "placar.json").write_text(report.dumps(board), encoding="utf-8")
    h2 = board["horizons"].get(2)
    print(f"Placar: {board['decision']['origins_matured']} origem(ns) vencida(s) em h = 2 de "
          f"{live.DECISION_ORIGINS} para a decisão" + (f"; BSS até aqui {h2['estimate']:+.3f}" if h2 else ""))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fit-calibration", action="store_true")
    args = parser.parse_args(argv)
    return fit_calibration() if args.fit_calibration else weekly()


if __name__ == "__main__":
    raise SystemExit(main())
