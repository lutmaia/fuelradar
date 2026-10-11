"""Aplica as migrações e carrega no PostgreSQL o conjunto publicado pela qualidade.

Uso: python scripts/load_db.py [--out data/processed] [--quarantine data/quarantine] [--migrate-only]
A conexão vem de DATABASE_URL. Rode antes scripts/ingest_local.py e scripts/check_quality.py.
Retorno 0 em sucesso; 1 quando a carga é recusada ou falha (nada é alterado no banco).
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Sem instalação do pacote, o script enxerga `src` por este caminho (docs/decisions/0001).
sys.path.insert(0, str(ROOT / "src"))

import psycopg  # noqa: E402

from radar_combustiveis.db.connection import connect, database_url  # noqa: E402
from radar_combustiveis.db.load import LoadError, load_database  # noqa: E402
from radar_combustiveis.db.migrate import MigrationError, apply_migrations  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--quarantine", type=Path, default=ROOT / "data" / "quarantine")
    parser.add_argument("--migrate-only", action="store_true", help="só aplica as migrações pendentes")
    args = parser.parse_args(argv)
    try:
        url = database_url()
        with connect(url) as conn:
            applied = apply_migrations(conn)
        print(f"Migrações aplicadas: {', '.join(applied) if applied else 'nenhuma (esquema em dia)'}")
        if args.migrate_only:
            return 0
        summary = load_database(url, args.out, args.quarantine)
    except (ValueError, LoadError, MigrationError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        print(f"ERRO de banco: {exc.diag.message_primary or exc}", file=sys.stderr)
        return 1
    print(f"Execução {summary['run_id']} | {summary['status']} | qualidade {summary['quality_decision']}")
    print(f"  publicadas {summary['rows_staged']} | quarentena {summary['rows_quarantined']} | "
          f"inseridas {summary['inserted']} | atualizadas {summary['updated']} | "
          f"sem mudança {summary['unchanged']} | deixaram de ser vigentes {summary['retired']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
