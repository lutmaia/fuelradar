"""Normalização de valores da ANP; regras do contrato em docs/data-contract.md."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata


def normalize_text(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).upper().split())


UF_NAMES = dict(zip(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(),
    "ACRE|ALAGOAS|AMAPA|AMAZONAS|BAHIA|CEARA|DISTRITO FEDERAL|ESPIRITO SANTO|GOIAS|MARANHAO|MATO GROSSO|MATO GROSSO DO SUL|MINAS GERAIS|PARA|PARAIBA|PARANA|PERNAMBUCO|PIAUI|RIO DE JANEIRO|RIO GRANDE DO NORTE|RIO GRANDE DO SUL|RONDONIA|RORAIMA|SANTA CATARINA|SAO PAULO|SERGIPE|TOCANTINS".split("|"),
))
UF_CODES = {name: code for code, name in UF_NAMES.items()}
PRODUCTS = {
    "GASOLINA": "GASOLINA_COMUM", "GASOLINA COMUM": "GASOLINA_COMUM",
    "GASOLINA ADITIVADA": "GASOLINA_ADITIVADA",
    "ETANOL": "ETANOL_HIDRATADO", "ETANOL HIDRATADO": "ETANOL_HIDRATADO",
    "DIESEL S500": "DIESEL_S500", "OLEO DIESEL": "DIESEL_S500",
    "DIESEL S10": "DIESEL_S10", "OLEO DIESEL S10": "DIESEL_S10",
    # A fonte histórica não especifica S500 neste rótulo: não fundir por suposição.
    "DIESEL": "DIESEL_NAO_ESPECIFICADO",
    "GNV": "GNV", "GLP": "GLP",
}
MISSING = {"", "-", "NA", "N/A", "NULL"}


def is_missing(value):
    return value is None or (isinstance(value, str) and normalize_text(value) in MISSING)


def normalize_uf(value):
    text = normalize_text(value)
    return text if text in UF_NAMES else UF_CODES.get(text)


def normalize_product(value):
    return PRODUCTS.get(normalize_text(value))


def normalize_unit(value):
    text = normalize_text(value).replace(" ", "")
    return {"R$/L": "BRL/L", "R$/LITRO": "BRL/L", "R$/M3": "BRL/M3",
            "R$/13KG": "BRL/13KG"}.get(text)


def parse_money(value):
    if is_missing(value):
        return None
    if isinstance(value, bool):
        raise ValueError("Booleano não é preço")
    text = str(value).strip()
    if "," in text:
        if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+),\d+", text):
            raise ValueError(f"Valor monetário inválido: {value!r}")
        text = text.replace(".", "").replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {value!r}") from exc
    if not result.is_finite():
        raise ValueError("Valor monetário não finito")
    return result


def parse_date(value):
    if is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Data inválida (esperado data Excel, DD/MM/AAAA ou ISO): {value!r}")


def normalize_identifier(value, width):
    """Retorna (texto, status). Não adivinha dígitos de texto curto/científico.

    Inteiros nativos Excel de até 14 dígitos têm precisão representável;
    completar sua largura fixa é reversível. Isso não valida o cadastro.
    """
    if is_missing(value):
        return None, "missing"
    if isinstance(value, bool):
        return None, "invalid"
    if isinstance(value, int):
        if 0 < value < 10 ** width:
            text = str(value)
            return text.zfill(width), "padded_native_integer" if len(text) < width else "exact_native_integer"
        return None, "invalid"
    if not isinstance(value, str):
        return None, "ambiguous_numeric"
    text = value.strip()
    mask = r"[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}" if width == 14 else r"[0-9]{5}-[0-9]{3}"
    if re.fullmatch(mask, text):
        return re.sub(r"[./-]", "", text), "exact_masked_text"
    if re.fullmatch(r"[0-9]{" + str(width) + r"}", text):
        return text, "exact_text"
    if re.fullmatch(r"[0-9]{1," + str(width - 1) + r"}", text):
        return None, "ambiguous_short_text"
    if re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?[eE][+-]?[0-9]+", text) or re.fullmatch(r"[0-9]+[.,][0-9]+", text):
        return None, "ambiguous_numeric_text"
    return None, "invalid"


def normalize_cnpj(value):
    return normalize_identifier(value, 14)[0]
