"""Ficha do conjunto de dados, em português e inglês, a partir do banco.

Uso: python scripts/dataset_card.py [--report-dir reports/dataset] [--docs docs]
Lê com DATABASE_URL. Grava reports/dataset/ficha.json e fontes.csv (arquivos de origem com SHA-256)
e os textos docs/ficha-dados.md e docs/en/dataset-card.md. Sem CNPJ, razão social nem endereço.
"""

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis import dataset_card  # noqa: E402
from radar_combustiveis.config import load_excluded_sources  # noqa: E402
from radar_combustiveis.db.connection import connect, database_url  # noqa: E402


def write(report_dir, docs_dir, card, header, rows):
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "ficha.json").write_text(json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    with open(report_dir / "fontes.csv", "w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    (docs_dir / "en").mkdir(parents=True, exist_ok=True)
    (docs_dir / "ficha-dados.md").write_text(dataset_card.markdown(card, "pt"), encoding="utf-8")
    (docs_dir / "en" / "dataset-card.md").write_text(dataset_card.markdown(card, "en"), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "dataset")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    args = parser.parse_args(argv)
    with connect(database_url()) as conn:
        excluded = load_excluded_sources(ROOT / "config" / "excluded_sources.json")
        card = dataset_card.collect(conn, excluded)
        header, rows = dataset_card.sources(conn, excluded)
    write(args.report_dir, args.docs, card, header, rows)
    c = card["coverage"]
    print(f"Ficha: {c['first_week']} a {c['last_week']}, {c['weeks_with_data']} semanas, "
          f"{c['municipalities']} municípios, {card['observations']['current']} observações; "
          f"{len(rows)} arquivos de origem em fontes.csv")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
