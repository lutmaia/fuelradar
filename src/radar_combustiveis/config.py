"""Configuração mínima: UFs publicadas, lidas da variável de ambiente TARGET_UFS."""

import json
import os

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


def load_target_ufs(environ=None):
    environ = os.environ if environ is None else environ
    text = environ.get("TARGET_UFS")
    return DEFAULT_TARGET_UFS if text is None else parse_target_ufs(text)
