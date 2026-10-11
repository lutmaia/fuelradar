"""Formato único de erro (arquitetura 15.5) e identificador de requisição.

Toda falha sai como {"error": {"code", "message", "request_id"}}. `details` aparece só nos erros
de validação, para indicar o parâmetro. Detalhes internos (SQL, URL do banco, pilha) nunca saem.
"""

import logging
import re
import uuid

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import psycopg
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("radar.api")

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class ApiError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


def request_id_of(request):
    return request.scope.get("state", {}).get("request_id") or uuid.uuid4().hex


def error_response(request, status_code, code, message, details=None):
    request_id = request_id_of(request)
    body = {"code": code, "message": message, "request_id": request_id}
    if details:
        body["details"] = details
    return JSONResponse({"error": body}, status_code=status_code, headers={REQUEST_ID_HEADER: request_id})


class RequestIdMiddleware:
    """ASGI puro: aceita um X-Request-ID válido do cliente, senão gera um; devolve no cabeçalho."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = next((v.decode("latin-1") for k, v in scope["headers"] if k == b"x-request-id"), "")
        request_id = supplied if _VALID_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_id)


def install_error_handlers(app):
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "query"), "message": e["msg"]}
                   for e in jsonable_encoder(exc.errors())]
        return error_response(request, 422, "VALIDATION_ERROR", "Parâmetros inválidos.", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        message = {404: "Recurso não encontrado.", 405: "Método não permitido."}.get(exc.status_code, "Requisição recusada.")
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(PoolTimeout)
    async def pool_timeout(request: Request, exc: PoolTimeout):
        log.warning("sem conexão disponível no pool (request_id=%s)", request_id_of(request))
        return error_response(request, 503, "DATABASE_UNAVAILABLE", "Banco de dados indisponível no momento.")

    @app.exception_handler(psycopg.errors.QueryCanceled)
    async def query_timeout(request: Request, exc: psycopg.errors.QueryCanceled):
        log.warning("consulta cancelada por tempo (request_id=%s)", request_id_of(request))
        return error_response(request, 503, "QUERY_TIMEOUT", "A consulta demorou mais que o limite permitido.")

    @app.exception_handler(psycopg.OperationalError)
    async def database_down(request: Request, exc: psycopg.OperationalError):
        log.error("erro operacional do banco (request_id=%s): %s", request_id_of(request), type(exc).__name__)
        return error_response(request, 503, "DATABASE_UNAVAILABLE", "Banco de dados indisponível no momento.")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("erro inesperado (request_id=%s)", request_id_of(request))
        return error_response(request, 500, "INTERNAL_ERROR", "Erro interno. Informe o request_id ao responsável.")
