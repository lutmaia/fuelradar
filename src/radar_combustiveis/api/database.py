"""Pool de conexões somente leitura da API.

A URL vem de API_DATABASE_URL (usuário `radar_api`, membro de `radar_reader`; ver
scripts/create_api_role.py). Não há retorno a DATABASE_URL: o usuário de escrita do pipeline não
deve servir a API. Mesmo com um usuário mais forte, a sessão é aberta somente leitura.
"""

import os

from psycopg import IsolationLevel
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..db.connection import SCHEMA

DEFAULT_POOL_SIZE = 5
DEFAULT_STATEMENT_TIMEOUT_MS = 5000
DEFAULT_POOL_TIMEOUT_S = 5


def api_database_url(environ=None):
    environ = os.environ if environ is None else environ
    url = environ.get("API_DATABASE_URL")
    if not url:
        raise ValueError(
            "API_DATABASE_URL não definida. Crie o usuário somente leitura com "
            "scripts/create_api_role.py e use postgresql://radar_api:<senha>@127.0.0.1:54329/radar")
    return url


def _configure(conn):
    # Todas as consultas de uma requisição enxergam o mesmo instantâneo, mesmo que uma carga
    # termine no meio dela.
    conn.isolation_level = IsolationLevel.REPEATABLE_READ


def open_pool(url, max_size=DEFAULT_POOL_SIZE, statement_timeout_ms=DEFAULT_STATEMENT_TIMEOUT_MS,
              pool_timeout=DEFAULT_POOL_TIMEOUT_S):
    """Abre o pool sem esperar o banco: /health/live responde mesmo com o banco fora, e
    /health/ready informa a indisponibilidade."""
    options = (f"-c search_path={SCHEMA} -c default_transaction_read_only=on "
               f"-c statement_timeout={int(statement_timeout_ms)} -c timezone=UTC")
    pool = ConnectionPool(url, min_size=1, max_size=max_size, open=False, timeout=pool_timeout,
                          check=ConnectionPool.check_connection, configure=_configure,
                          kwargs={"options": options, "row_factory": dict_row})
    pool.open(wait=False)
    return pool
