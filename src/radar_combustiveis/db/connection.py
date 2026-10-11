"""Conexão com o PostgreSQL. A URL vem de DATABASE_URL e nunca é gravada no repositório."""

import os

import psycopg

SCHEMA = "radar"


def database_url(environ=None):
    environ = os.environ if environ is None else environ
    url = environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL não definida (ex.: postgresql://usuario:senha@localhost:5432/radar)")
    return url


def connect(url):
    """Conexão com search_path no esquema do projeto; confirmação explícita das transações."""
    return psycopg.connect(url, options=f"-c search_path={SCHEMA}")
