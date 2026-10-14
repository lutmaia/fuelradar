"""Estudo exploratório do Marco 8 (Q1 a Q3) sobre o PostgreSQL carregado.

Uso: python scripts/run_study.py [--uf SP] [--report-dir reports/study] [--reps 2000]
Lê só as semanas de 2022-11-13 a 2026-03-29 (o teste final fica lacrado), roda as análises do
protocolo (docs/estudo/protocolo.md), aplica o gate G1 e escreve os relatórios em `reports/study/`.
"""

import argparse
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.db.connection import connect, database_url  # noqa: E402
from radar_combustiveis.forecasting import protocol  # noqa: E402
from radar_combustiveis.study import gate, q1, q2, q3  # noqa: E402
from radar_combustiveis.study.load import load  # noqa: E402
from radar_combustiveis.study.report import write_reports  # noqa: E402


def git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=ROOT).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def code_sha():
    head = git("rev-parse", "HEAD")
    # Os próprios relatórios (reports/) não contam como "código alterado".
    return head and head + ("-dirty" if git("status", "--porcelain", "--", ".", ":!reports") else "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uf", default="SP")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "study")
    parser.add_argument("--reps", type=int, default=protocol.BOOTSTRAP_REPS, help="reamostras do bootstrap")
    args = parser.parse_args(argv)

    started = time.time()
    with connect(database_url()) as conn:
        obs, city, state, hashes = load(conn, args.uf)
    print(f"{len(obs)} observações, {len(city)} linhas município-semana, {len(state)} estado-semana | "
          f"semanas {obs['week_start'].min()} a {obs['week_start'].max()} | hash {hashes['combined'][:12]}", flush=True)

    results = {}
    for name, run in (("q1", lambda: q1.analyze(obs)), ("q2", lambda: q2.analyze(obs, reps=args.reps)),
                      ("q3", lambda: q3.analyze(city, state))):
        t = time.time()
        results[name] = run()
        print(f"  {name}: {time.time() - t:.0f}s | achado estável: {results[name]['stable']}", flush=True)

    meta = dict(uf=args.uf, code_sha=code_sha(), protocol_commit=git("log", "-1", "--format=%H", "--",
                                                                       "docs/estudo/protocolo.md"),
                data_hashes=hashes, window=[protocol.STUDY_START, protocol.STUDY_END], seed=protocol.SEED,
                bootstrap_reps=args.reps, observations=len(obs),
                weeks_with_data=int(obs["week_start"].nunique()))
    verdict = gate.g1(results)
    paths = write_reports(meta, results, verdict, args.report_dir)
    print(f"G1: {'passou' if verdict['passed'] else 'não passou'} (estáveis: {', '.join(verdict['stable']) or 'nenhum'})")
    print(f"Relatórios: {', '.join(str(p.relative_to(ROOT)) for p in paths)} | {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
