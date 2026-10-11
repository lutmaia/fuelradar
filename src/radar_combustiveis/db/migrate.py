"""Migrações em SQL puro, versionadas por arquivo e conferidas por SHA-256.

Cada arquivo `migrations/NNNN_nome.sql` roda numa única transação, junto do seu registro em
`schema_migration`. Um arquivo já aplicado que mude de conteúdo é erro: corrija com uma
migração nova, nunca editando a antiga.
"""

import hashlib
from pathlib import Path
import re

from .connection import SCHEMA

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
_NAME = re.compile(r"\d{4}_[a-z0-9_]+\.sql")
_LOCK_KEY = 7_204_001  # advisory lock: duas execuções simultâneas não migram ao mesmo tempo


class MigrationError(Exception):
    pass


def list_migrations(directory=MIGRATIONS_DIR):
    files = sorted(Path(directory).glob("*.sql"))
    bad = [f.name for f in files if not _NAME.fullmatch(f.name)]
    if bad:
        raise MigrationError(f"Nome de migração fora do padrão NNNN_nome.sql: {bad}")
    return files


def apply_migrations(conn, directory=MIGRATIONS_DIR):
    """Aplica as migrações pendentes em ordem. Devolve os nomes aplicados nesta chamada."""
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migration (
                version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())""")
        applied = dict(conn.execute("SELECT version, sha256 FROM schema_migration").fetchall())
    done = []
    for path in list_migrations(directory):
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if path.name in applied:
            if applied[path.name] != digest:
                raise MigrationError(f"Migração já aplicada foi alterada: {path.name}")
            continue
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
            conn.execute(text)
            conn.execute("INSERT INTO schema_migration (version, sha256) VALUES (%s, %s)", (path.name, digest))
        done.append(path.name)
    return done
