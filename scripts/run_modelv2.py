"""Modelagem v2: validação e, com --read-test, a leitura única do teste final.

Uso: python scripts/run_modelv2.py [--read-test --purpose "texto"]
Lê o banco com DATABASE_URL (a leitura do teste grava em holdout_access). Relatórios em
reports/modelv2/; pontos detalhados em data/processed/modelv2/ (fora do Git).
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.db.connection import connect, database_url  # noqa: E402
from radar_combustiveis.db.migrate import apply_migrations  # noqa: E402
from radar_combustiveis.forecasting import protocol  # noqa: E402
from radar_combustiveis.forecasting.panel import build_panel, data_hash  # noqa: E402
from radar_combustiveis.modelv2 import data, decision, experiment, report, spec  # noqa: E402
from radar_combustiveis.modelv2.features import Features  # noqa: E402

REPORTS = ROOT / "reports" / "modelv2"
POINTS = ROOT / "data" / "processed" / "modelv2"


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def meta_of(rows, panel):
    dirty = bool(git("status", "--porcelain", "--", "src", "scripts", "migrations"))
    sha = git("rev-parse", "HEAD")
    return {"data_hash": data_hash(rows), "series": len(panel.keys), "first_week": panel.weeks[0],
            "last_week": panel.weeks[-1], "code_sha": f"{sha}{'+alterado' if dirty else ''}" if sha else None,
            "protocol_commit": git("log", "-1", "--format=%H", "--", "docs/estudo/protocolo-modelagem.md"),
            "seed": spec.SEED, "bootstrap_reps": spec.BOOTSTRAP_REPS,
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def index_of(panel, week):
    return panel.index_of(week)


def progress(h, cutoff, layer, n):
    print(f"  h={h} corte={cutoff} {layer}: {n} pontos", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-test", action="store_true", help="lê o teste final (uma vez; fica registrado)")
    parser.add_argument("--purpose", help="finalidade da leitura do teste, gravada em holdout_access")
    parser.add_argument("--report-dir", type=Path, default=REPORTS, help="só a validação (scripts/reproduce.py)")
    parser.add_argument("--points-dir", type=Path, default=POINTS)
    args = parser.parse_args(argv)
    if args.read_test and (args.report_dir != REPORTS or args.points_dir != POINTS):
        parser.error("--read-test grava só nas pastas padrão: a leitura do teste é única")
    reports, points = args.report_dir, args.points_dir
    if args.read_test and not args.purpose:
        parser.error("--read-test exige --purpose")
    reports.mkdir(parents=True, exist_ok=True)
    points.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with connect(database_url()) as conn:
        apply_migrations(conn)
        external = data.load_external(conn)
        rows = data.load_panel_rows(conn)
        panel = build_panel(rows)
        features = Features(panel, external)
        valid_origins = list(range(index_of(panel, protocol.VALID_START), index_of(panel, protocol.VALID_END) + 1))
        print(f"Validação: {len(valid_origins)} origens, {len(panel.keys)} séries", flush=True)
        valid = experiment.run_window(panel, features, valid_origins, index_of(panel, protocol.VALID_END),
                                      index_of(panel, protocol.DEV_END), progress=progress)
        valid.to_csv(points / "validacao.csv.gz", index=False)
        selection = decision.select_candidate(valid)
        summary = report.validation_summary(valid, selection, meta_of(rows, panel))
        (reports / "validacao.json").write_text(report.dumps(summary), encoding="utf-8")
        (reports / "validacao.md").write_text(report.validation_markdown(summary), encoding="utf-8")
        print(f"Candidato na validação: {selection['candidate']} ({time.monotonic() - started:.0f} s)")
        if not args.read_test:
            return 0

        rows_all = data.load_panel_rows(conn, read_test=True, purpose=args.purpose,
                                        code_sha=summary["meta"]["code_sha"])
        panel_all = build_panel(rows_all)
        features_all = Features(panel_all, external)
        first_test = index_of(panel_all, protocol.TEST_START)
        test_origins = list(range(first_test, panel_all.last))
        cutoff = index_of(panel_all, protocol.VALID_END)
        print(f"Teste: {len(test_origins)} origens", flush=True)
        test = experiment.run_window(panel_all, features_all, test_origins, panel_all.last, cutoff, progress=progress)
        test.to_csv(POINTS / "teste.csv.gz", index=False)
        candidate = selection["candidate"]
        sensitivity, reproducible = {}, False
        if candidate:
            layer, model = candidate.split("_", 1)
            h2 = test[test["horizon"] == spec.PRIMARY_HORIZON]
            last_cut = experiment.cutoffs_for(cutoff, max(test_origins))[-1]
            reproducible = experiment.reproducible(panel_all, features_all, layer, model, spec.PRIMARY_HORIZON,
                                                   last_cut, h2["series"].to_numpy(), h2["origin"].to_numpy())
            for tau in spec.TAU_SENSITIVITY:
                extra = experiment.run_window(panel_all, features_all, test_origins, panel_all.last, cutoff,
                                              layers=(layer,), models=(model,), tau=tau,
                                              horizons=(spec.PRIMARY_HORIZON,), value=False)
                sensitivity[str(tau)] = decision.primary(extra, candidate)
        verdict = decision.decide(test, candidate, reproducible)
        reads = [dict(zip(("access_id", "accessed_at", "code_sha", "purpose", "data_hash", "row_count"), r))
                 for r in data.holdout_reads(conn)]
        final = report.final_summary(test, summary, verdict, sensitivity, valid, reads, meta_of(rows_all, panel_all))
        (REPORTS / "final.json").write_text(report.dumps(final), encoding="utf-8")
        (REPORTS / "final.md").write_text(report.final_markdown(final), encoding="utf-8")
        print(f"Decisão: {'aprovado' if verdict['approved'] else 'não aprovado'} "
              f"({time.monotonic() - started:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
