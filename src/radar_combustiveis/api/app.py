"""Fábrica da aplicação FastAPI. Uso: `uvicorn` via scripts/run_api.py ou `create_app()` nos testes."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..config import load_target_ufs
from .database import (DEFAULT_POOL_SIZE, DEFAULT_POOL_TIMEOUT_S, DEFAULT_STATEMENT_TIMEOUT_MS, api_database_url,
                       open_pool)
from .errors import RequestIdMiddleware, install_error_handlers
from .routes import health_router, router

DESCRIPTION = """
Consultas de **leitura** sobre os preços de revenda de combustíveis pesquisados pela ANP, hoje
somente **São Paulo**.

* Os preços são da **pesquisa semanal da ANP**: amostra de postos, não o universo de revendedores
  nem preços em tempo real.
* Toda resposta de dados informa `data_as_of` (última coleta) e, quando há registro,
  `source_retrieved_at` (download do arquivo). O indicador principal é a **mediana** semanal.
* `coverage_status` indica se a amostra da semana é comparável com as anteriores.
* Erros seguem um formato único: `{"error": {"code", "message", "request_id"}}`.
"""


def create_app(database_url=None, target_ufs=None, pool_size=DEFAULT_POOL_SIZE,
               statement_timeout_ms=DEFAULT_STATEMENT_TIMEOUT_MS, pool_timeout=DEFAULT_POOL_TIMEOUT_S):
    url = database_url or api_database_url()  # falha logo, e com mensagem, se não configurada
    ufs = tuple(target_ufs) if target_ufs else load_target_ufs()

    @asynccontextmanager
    async def lifespan(app):
        app.state.pool = open_pool(url, pool_size, statement_timeout_ms, pool_timeout)
        try:
            yield
        finally:
            app.state.pool.close(timeout=2)

    app = FastAPI(title="Radar de Combustíveis SP — API", version="1.0.0", description=DESCRIPTION,
                  lifespan=lifespan)
    app.state.target_ufs = ufs
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(router)
    return app
