"""Configuração mínima: UFs publicadas (TARGET_UFS) e arquivos da fonte excluídos por defeito conhecido."""

import json
import os
from pathlib import Path
import re

from .ingestion.normalize import UF_NAMES

DEFAULT_TARGET_UFS = ("SP",)


def parse_target_ufs(text):
    """Valida uma lista JSON de siglas, como '["SP"]'. Rejeita lista vazia, UF desconhecida e repetição."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TARGET_UFS deve ser uma lista JSON, como [\"SP\"]: {text!r}") from exc
    if not isinstance(value, list) or not value or not all(isinstance(uf, str) for uf in value):
        raise ValueError(f"TARGET_UFS deve ser uma lista JSON não vazia de siglas: {text!r}")
    unknown = [uf for uf in value if uf not in UF_NAMES]
    if unknown:
        raise ValueError(f"TARGET_UFS com sigla desconhecida: {unknown}")
    if len(set(value)) != len(value):
        raise ValueError(f"TARGET_UFS com sigla repetida: {value}")
    return tuple(value)


def load_excluded_sources(path):
    """Lê a lista de arquivos da ANP que a qualidade deve ignorar, identificados pelo SHA-256.

    Cada item: {"sha256", "file", "reason"}. Devolve {sha256: item}. Arquivo ausente = lista vazia.
    Um arquivo corrigido pela ANP tem outro hash e deixa de ser excluído sozinho (ADR 0006)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        items = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: JSON inválido ({exc})") from exc
    if not isinstance(items, list):
        raise ValueError(f"{path}: esperada uma lista de objetos")
    excluded = {}
    for item in items:
        if (not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", "")))
                or not str(item.get("file", "")).strip() or not str(item.get("reason", "")).strip()):
            raise ValueError(f"{path}: cada item precisa de sha256 (64 hex), file e reason: {item!r}")
        if item["sha256"] in excluded:
            raise ValueError(f"{path}: sha256 repetido: {item['sha256']}")
        excluded[item["sha256"]] = item
    return excluded


def load_target_ufs(environ=None):
    environ = os.environ if environ is None else environ
    text = environ.get("TARGET_UFS")
    return DEFAULT_TARGET_UFS if text is None else parse_target_ufs(text)
