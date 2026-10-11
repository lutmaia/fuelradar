"""Cria (ou atualiza a senha d)o usuário de login somente leitura da API: `radar_api`.

Uso: python scripts/create_api_role.py
Conexão administrativa: DATABASE_URL. Senha do novo usuário: RADAR_API_PASSWORD (nunca vem pela
linha de comando nem é impressa). Exige a migração 0003 (papel `radar_reader`): rode antes
scripts/load_db.py --migrate-only. Idempotente.
"""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402
from psycopg.conninfo import conninfo_to_dict  # noqa: E402

from radar_combustiveis.db.connection import database_url  # noqa: E402

ROLE = "radar_api"
GROUP = "radar_reader"


def main():
    password = os.environ.get("RADAR_API_PASSWORD")
    if not password or len(password) < 16:
        print("ERRO: defina RADAR_API_PASSWORD com pelo menos 16 caracteres (use letras e números, "
              "para caber numa URL).", file=sys.stderr)
        return 1
    try:
        url = database_url()
        with psycopg.connect(url, autocommit=True) as conn:
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (GROUP,)).fetchone():
                print(f"ERRO: papel {GROUP} não existe. Rode scripts/load_db.py --migrate-only.", file=sys.stderr)
                return 1
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(sql.SQL("{} ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE")
                         .format(sql.SQL(verb), sql.Identifier(ROLE), sql.Literal(password)))
            conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(GROUP), sql.Identifier(ROLE)))
            conn.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(sql.Identifier(ROLE)))
            info = conninfo_to_dict(url)
    except (ValueError, psycopg.Error) as exc:
        message = exc.diag.message_primary if isinstance(exc, psycopg.Error) and exc.diag.message_primary else exc
        print(f"ERRO: {message}", file=sys.stderr)
        return 1
    print(f"Usuário {ROLE} {'atualizado' if exists else 'criado'} (membro de {GROUP}, somente leitura).")
    print(f"API_DATABASE_URL=postgresql://{ROLE}:<senha>@{info.get('host', '127.0.0.1')}:"
          f"{info.get('port', '5432')}/{info.get('dbname', 'radar')}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
