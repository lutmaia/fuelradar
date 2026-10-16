"""Backtest, decisão e publicação das previsões (Marco 7).

Uso: python scripts/run_forecasts.py [--step 4] [--no-store] [--report-dir reports/forecasting]
Lê as agregações semanais do PostgreSQL (DATABASE_URL), roda o backtest com origem deslizante
dos baselines e do candidato LightGBM, aplica a regra de aprovação (seção 14.8) e grava o
modelo publicado, suas previsões e as variações incomuns. Escreve o relatório reproduzível em
`reports/forecasting/`. Se o candidato não passar, o baseline permanece publicado.
"""

import argparse
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
# Sem instalação do pacote, o script enxerga `src` por este caminho (docs/decisions/0001).
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.db.connection import connect, database_url  # noqa: E402
from radar_combustiveis.forecasting import evaluate as ev  # noqa: E402
from radar_combustiveis.forecasting.panel import data_hash, load_rows  # noqa: E402
from radar_combustiveis.forecasting.report import write_reports  # noqa: E402
from radar_combustiveis.forecasting.run import compute  # noqa: E402
from radar_combustiveis.forecasting.store import publish  # noqa: E402


def code_sha():
    try:
        run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, check=True, cwd=ROOT).stdout.strip()  # noqa: E731
        # Os próprios relatórios (reports/) não contam como "código alterado".
        return run("rev-parse", "HEAD") + ("-dirty" if run("status", "--porcelain", "--", ".", ":!reports") else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uf", default="SP")
    parser.add_argument("--step", type=int, default=ev.STEP, help="semanas entre origens do backtest")
    parser.add_argument("--no-store", action="store_true", help="não grava no banco; só o relatório")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "forecasting")
    args = parser.parse_args(argv)
    args.report_dir = args.report_dir.resolve()  # o resumo final mostra o caminho relativo à raiz

    started = time.time()
    with connect(database_url()) as conn:
        rows = load_rows(conn, args.uf)
        print(f"{len(rows)} linhas semanais | hash dos dados {data_hash(rows)[:12]}")
        result = compute(rows, code_sha(), step=args.step,
                         progress=lambda origin, n: print(f"  origem {origin}: {n} pontos", flush=True))
        paths = write_reports(result, args.report_dir)
        decision = result["decision"]
        print(f"\nBacktest: {len(result['backtest_origins'])} origens, {result['summary']['points']} pontos avaliados")
        for name, s in result["summary"]["overall"].items():
            print(f"  {name:28s} MAE {s['mae']:.4f} | MAE pond. {s['wmae']:.4f} | viés {s['bias']:+.4f} | "
                  f"cobertura {s['coverage']:.1%} | largura {s['interval_width']:.3f}")
        verdict = "APROVADO" if decision["approved"] else "NÃO aprovado"
        gain = "n/d" if decision["improvement"] is None else f"{decision['improvement']:+.1%}"
        print(f"Candidato {verdict}; ganho sobre {decision['best_baseline']}: {gain}")
        for check, ok in decision["checks"].items():
            print(f"  [{'x' if ok else ' '}] {check}")
        eligible = sum(e["eligible"] for e in result["eligibility"])
        print(f"Modelo publicado: {result['published_model']} | previsões: {len(result['forecasts'])} | "
              f"séries elegíveis: {eligible}/{len(result['eligibility'])} | variações incomuns: {len(result['anomalies'])}")
        if not args.no_store:
            stored = publish(conn, result, args.uf)
            print(f"Gravado: versão {stored['version']} ({stored['forecasts']} previsões, {stored['anomalies']} variações)")
        print(f"Relatórios: {', '.join(str(p.relative_to(ROOT)) for p in paths)} | {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
