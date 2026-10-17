"""Rotina semanal em um comando (Marco 12, etapa B3).

Uso: python scripts/weekly_refresh.py [--dry-run] [--force]
Lê a página da ANP; se o pacote do demonstrativo já tem a semana mais recente, sai sem fazer nada.
Senão roda, em ordem: baixar a ANP, ingerir, qualidade, carregar, fontes externas, previsões de valor,
previsão ao vivo e pacote. Para na primeira falha. Exige DATABASE_URL e API_DATABASE_URL (o
atualizar.sh ou o atualizar.ps1 prepara as duas). Histórico das execuções em data/processed/weekly_runs.jsonl.
Retorno 0 quando conclui ou já está em dia; 1 quando algo falha. Com RADAR_INJECT_FAILURE=<etapa>,
essa etapa falha de propósito (teste de detecção e recuperação). No CI, grava new_week em GITHUB_OUTPUT.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis import weekly  # noqa: E402
from radar_combustiveis.ingestion.download import DEFAULT_PAGE, DownloadError, fetch_to_file  # noqa: E402

SNAPSHOT = ROOT / "snapshot" / "radar-sp.json.gz"
LOG = ROOT / "data" / "processed" / "weekly_runs.jsonl"


def read_page():
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "pagina.html"
        fetch_to_file(DEFAULT_PAGE, page, timeout=60, retries=3)
        return page.read_text(encoding="utf-8", errors="replace")


def run_script(stage):
    print(f"\n=== {stage.name} ===", flush=True)
    return subprocess.run([sys.executable, str(ROOT / "scripts" / stage.script), *stage.args], cwd=ROOT).returncode


def finish(entry):
    weekly.record(LOG, entry)
    if entry["status"] == "falhou":
        print(f"\nFALHOU em: {entry['failed_stage']}. Nada foi publicado; rode de novo depois de corrigir "
              "(as etapas que já terminaram não duplicam nada).", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="só diz se há semana nova")
    parser.add_argument("--force", action="store_true", help="roda mesmo com o pacote em dia")
    args = parser.parse_args(argv)

    try:
        page_week = weekly.latest_page_week(read_page())
    except DownloadError as exc:
        print(f"Não consegui ler a página da ANP: {exc}", file=sys.stderr)
        return finish({"status": "falhou", "failed_stage": "ler a página da ANP", "stages": []})
    if page_week is None:
        print("Nenhum link semanal na página da ANP (a página pode ter mudado).", file=sys.stderr)
        return finish({"status": "falhou", "failed_stage": "ler a página da ANP", "stages": []})
    current = weekly.snapshot_week(SNAPSHOT)
    print(f"Semana mais recente na ANP: {page_week} · no pacote: {current or 'nenhuma'}")
    new_week = current != page_week or args.force
    if os.environ.get("GITHUB_OUTPUT"):  # no CI, os passos seguintes só rodam se houver semana nova
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(f"new_week={'true' if new_week else 'false'}\npage_week={page_week}\n")
    if not new_week:
        print("Em dia: nada a fazer.")
        if not args.dry_run:
            weekly.record(LOG, {"status": "em dia", "page_week": page_week})
        return 0
    if args.dry_run:
        print("Há semana nova. Etapas: " + " → ".join(stage.name for stage in weekly.STAGES))
        return 0
    missing = [name for name in ("DATABASE_URL", "API_DATABASE_URL") if not os.environ.get(name)]
    if missing:
        print(f"Faltam variáveis: {', '.join(missing)} (use ./atualizar.sh ou .\\atualizar.ps1).", file=sys.stderr)
        return finish({"status": "falhou", "failed_stage": "configuração", "page_week": page_week, "stages": []})

    inject = os.environ.get("RADAR_INJECT_FAILURE") or None
    if inject:
        if inject not in {stage.name for stage in weekly.STAGES}:
            print(f"RADAR_INJECT_FAILURE não é uma etapa: {inject!r}", file=sys.stderr)
            return 1
        print(f"Falha injetada de propósito na etapa: {inject}")
    report = weekly.run(weekly.STAGES, run_script, inject=inject)
    built = weekly.snapshot_week(SNAPSHOT)
    if report["status"] == "concluído" and built != page_week:
        report.update(status="falhou", failed_stage=f"conferência final (pacote em {built}, ANP em {page_week})")
    for item in report["stages"]:
        print(f"  {'ok ' if item['code'] == 0 else 'ERRO'} {item['stage']} ({item['seconds']:.0f} s)")
    if report["status"] == "concluído":
        print(f"\nConcluído: pacote na semana {built}. Falta commitar reports/ledger/ e snapshot/.")
    return finish({**report, "page_week": page_week})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
