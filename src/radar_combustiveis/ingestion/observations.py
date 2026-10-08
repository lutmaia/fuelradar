"""Normalização de uma linha individual da ANP para uma observação, sem decidir qualidade.

Só são rejeitadas (e enviadas a data/quarantine) linhas cuja UF, preço de venda ou data não
podem ser interpretados. Preço não positivo, produto/unidade desconhecidos e CNPJ inválido
seguem na observação, com o valor normalizado vazio, para o Marco 3 avaliar.
"""

import hashlib
import json

from .normalize import (
    is_missing, normalize_identifier, normalize_product, normalize_text, normalize_uf,
    normalize_unit, parse_date, parse_money,
)

OBSERVATION_COLUMNS = [
    "uf", "region", "municipality_original", "municipality_normalized",
    "legal_name", "trade_name", "brand",
    "cnpj", "cnpj_status", "address", "address_number", "address_complement", "neighborhood",
    "cep", "cep_status",
    "product_original", "product", "product_category", "unit_original", "unit",
    "collection_date", "sale_price", "purchase_price", "row_key",
    "source_file_id", "source_sha256", "source_member", "source_sheet", "source_row_number",
    "source_row_hash", "ingestion_run_id",
]
REJECTED_COLUMNS = ["source_row_number", "reason", "original_values"]


def _text(value):
    return None if is_missing(value) else str(value).strip()


def _decimal(value):
    return None if value is None else format(value, "f")


def row_hash(values):
    return hashlib.sha256(json.dumps(values, default=str, ensure_ascii=False).encode()).hexdigest()


def normalize_row(table, values, target_ufs):
    """Devolve ("out_of_scope", None, None), ("rejected", None, motivo) ou ("accepted", dict, None)."""
    get = lambda key: values[table.mapping[key]] if key in table.mapping else None
    uf = normalize_uf(get("uf"))
    if uf is None:
        return "rejected", None, "uf_invalida_ou_ausente"
    if uf not in target_ufs:
        return "out_of_scope", None, None
    try:
        sale_price = parse_money(get("sale_price"))
    except ValueError:
        return "rejected", None, "preco_de_venda_invalido"
    if sale_price is None:
        return "rejected", None, "preco_de_venda_ausente"
    try:
        collection_date = parse_date(get("collection_date"))
    except ValueError:
        return "rejected", None, "data_da_coleta_invalida"
    if collection_date is None:
        return "rejected", None, "data_da_coleta_ausente"
    try:
        purchase_price = parse_money(get("purchase_price"))
    except ValueError:
        purchase_price = None  # campo opcional e fora do primeiro modelo
    cnpj, cnpj_status = normalize_identifier(get("cnpj"), 14)
    cep, cep_status = normalize_identifier(get("postal_code"), 8)
    municipality = _text(get("municipality"))
    municipality_normalized = normalize_text(municipality)
    product = normalize_product(get("product"))
    unit = normalize_unit(get("unit"))
    category = "desconhecido" if product is None else "glp" if product == "GLP" else "automotivo"
    complete = cnpj and product and unit and municipality_normalized
    row_key = "|".join([uf, municipality_normalized, cnpj or "", product or "", unit or "",
                        collection_date.isoformat()]) if complete else ""
    return "accepted", {
        "uf": uf, "region": _text(get("region")),
        "municipality_original": municipality, "municipality_normalized": municipality_normalized,
        "legal_name": _text(get("legal_name")), "trade_name": _text(get("trade_name")),
        "brand": _text(get("brand")),
        "cnpj": cnpj, "cnpj_status": cnpj_status,
        "address": _text(get("address")), "address_number": _text(get("address_number")),
        "address_complement": _text(get("address_complement")), "neighborhood": _text(get("neighborhood")),
        "cep": cep, "cep_status": cep_status,
        "product_original": _text(get("product")), "product": product, "product_category": category,
        "unit_original": _text(get("unit")), "unit": unit,
        "collection_date": collection_date.isoformat(),
        "sale_price": _decimal(sale_price), "purchase_price": _decimal(purchase_price),
        "row_key": row_key,
    }, None
