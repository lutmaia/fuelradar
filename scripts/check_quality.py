"""Qualidade e normalização das observações já ingeridas; não lê nem altera data/raw.

Uso: python scripts/check_quality.py [--out data/processed] [--quarantine data/quarantine] [--as-of AAAA-MM-DD]
     [--excluded config/excluded_sources.json]
Retorno 0 para publicar ou publicar com aviso; 1 quando uma falha crítica bloqueia a publicação.
"""

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Sem instalação do pacote, o script enxerga `src` por este caminho (docs/decisions/0001).
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.config import load_excluded_sources  # noqa: E402
from radar_combustiveis.quality.pipeline import run_quality  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--quarantine", type=Path, default=ROOT / "data" / "quarantine")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None,
                        help="data de referência para datas futuras e atraso (padrão: hoje, UTC)")
    parser.add_argument("--excluded", type=Path, default=ROOT / "config" / "excluded_sources.json",
                        help="arquivos da fonte com defeito conhecido, ignorados pela qualidade (por SHA-256)")
    args = parser.parse_args(argv)
    try:
        report = run_quality(args.out, args.quarantine, args.as_of, load_excluded_sources(args.excluded))
    except ValueError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    rec = report["reconciliation"]
    print(f"Execução {report['run_id']} | referência {report['as_of']} | decisão: {report['decision']}")
    print(f"  ingeridas {rec['rows_ingested']} = publicadas {rec['rows_published']} + quarentena "
          f"{rec['rows_quarantined']} + cópias idênticas {rec['rows_duplicate_removed']} + fora do escopo "
          f"{rec['rows_out_of_scope_product']} | reconciliado: {rec['balanced']}")
    for key, value in report["counts"].items():
        if key.startswith(("reason:", "flag:")):
            print(f"  {key}: {value}")
    for failure in report["critical_failures"]:
        print(f"  CRÍTICO {failure['rule']}: {failure['source_file_id']}", file=sys.stderr)
    for warning in report["warnings"]:
        print(f"  aviso: {warning}")
    cov = report["coverage"]
    print(f"  última semana {cov['latest_week']}, última coleta {cov['last_collection_date']} "
          f"({cov['delay_days']} dias); dias úteis sem coleta: {', '.join(cov['weekdays_without_collection']) or 'nenhum'}")
    print(f"  saídas regravadas: {[k for k, v in report['outputs_written'].items() if v] or 'nenhuma'}")
    return 1 if report["decision"] == "bloquear" else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
