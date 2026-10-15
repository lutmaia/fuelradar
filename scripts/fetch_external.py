"""Baixa, confere e carrega as fontes externas (dólar do BCB, produtores e distribuição da ANP).

Uso: python scripts/fetch_external.py [--no-download] [--no-load]
Brutos em data/raw/external/ (nunca sobrescritos), registro e relatório em data/processed/external/.
A carga usa DATABASE_URL e aplica as migrações pendentes. Sai com 1 se alguma fonte for bloqueada.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.config import load_target_ufs  # noqa: E402
from radar_combustiveis.db.connection import connect, database_url  # noqa: E402
from radar_combustiveis.db.migrate import apply_migrations  # noqa: E402
from radar_combustiveis.external import pipeline  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-download", action="store_true", help="usa só os arquivos já baixados")
    parser.add_argument("--no-load", action="store_true", help="não carrega no banco (só qualidade)")
    args = parser.parse_args(argv)
    raw, processed = ROOT / "data" / "raw", ROOT / "data" / "processed"
    ufs = load_target_ufs()
    if args.no_load:
        report = pipeline.run(raw, processed, ufs, download=not args.no_download)
    else:
        with connect(database_url()) as conn:
            apply_migrations(conn)
            report = pipeline.run(raw, processed, ufs, conn=conn, download=not args.no_download)
    if report["download"]:
        d = report["download"]
        print(f"Download: {len(d['saved'])} novo(s), {len(d['duplicate'])} igual(is) ao já guardado, "
              f"{len(d['errors'])} erro(s)")
        for error in d["errors"]:
            print(f"  erro em {error['name']}: {error['error']}")
    for source_id, result in report["sources"].items():
        load = result.get("load")
        loaded = (f" · carga: {load['inserted']} novas, {load['updated']} alteradas, {load['total']} no banco"
                  if load else "")
        print(f"{source_id}: {result['decision']} · {result['rows']} linhas · até {result['latest_period_end']}{loaded}")
        for item in result["critical"]:
            print(f"  crítico: {item}")
        for item in result["warnings"][:5]:
            print(f"  aviso: {item}")
    return 1 if any(r["decision"] == "bloquear" for r in report["sources"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
