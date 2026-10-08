"""Ingestão local dos arquivos da ANP em data/raw; não baixa nada nem altera os originais.

Uso: python scripts/ingest_local.py [--raw data/raw] [--out data/processed]
UFs publicadas: variável TARGET_UFS (lista JSON), padrão ["SP"].
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Sem instalação do pacote, o script enxerga `src` por este caminho (docs/decisions/0001).
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.config import load_target_ufs  # noqa: E402
from radar_combustiveis.ingestion.pipeline import run_ingestion  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--quarantine", type=Path, default=ROOT / "data" / "quarantine")
    args = parser.parse_args(argv)
    try:
        report = run_ingestion(args.raw, args.out, args.quarantine, load_target_ufs())
    except (ValueError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    print(f"Execução {report['run_id']} | UFs: {','.join(report['target_ufs'])}")
    for event in report["events"]:
        print(f"  {event['event']}: {event['paths'][0]} (revisão {event['revision']}, {','.join(event['kinds'])})")
    for item in report["ingested"]:
        print(f"  ingerido {item['path']}: lidas {item['rows_read']}, aceitas {item['rows_accepted']}, "
              f"fora do escopo {item['rows_out_of_scope']}, rejeitadas {item['rows_rejected']}, "
              f"chaves repetidas {item['duplicate_keys']}")
    for error in report["errors"]:
        print(f"  ERRO ({error['stage']}) {error['path']}: {error['error']}", file=sys.stderr)
    print(f"Raw inalterado: {report['raw_unchanged']} | manifesto gravado: {report['manifest_written']}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
