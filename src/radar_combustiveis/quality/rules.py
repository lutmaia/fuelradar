"""Regras de qualidade por linha e auxiliares puros; limites e motivos em docs/data-contract.md.

Motivos de quarentena retiram a linha da saída publicada, mas ela é preservada com o motivo.
Avisos não retiram a linha: ficam em `quality_flags`. Nada aqui interpreta preço raro como fraude.
"""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import statistics

# Unidade esperada por produto canônico; outra combinação é incompatível.
PRODUCT_UNITS = {
    "GASOLINA_COMUM": "BRL/L", "GASOLINA_ADITIVADA": "BRL/L", "ETANOL_HIDRATADO": "BRL/L",
    "DIESEL_COMUM": "BRL/L", "DIESEL_S10": "BRL/L",
    "GNV": "BRL/M3", "GLP": "BRL/13KG",
}
# GLP é preservado na ingestão, mas está fora do MVP automotivo: não é publicado nem avaliado.
OUT_OF_SCOPE_PRODUCTS = {"GLP"}
VALID_CNPJ_STATUS = {"exact_masked_text", "exact_text", "exact_native_integer", "padded_native_integer"}

EXTREME_IQR_FACTOR = 3          # aviso fora de [Q1 − 3×IQR, Q3 + 3×IQR], a cerca do perfil exploratório
IMPLAUSIBLE_FACTOR = 2          # quarentena abaixo de mediana/2 ou acima de 2×mediana (digitação, unidade)
EXTREME_WINDOW_WEEKS = 8        # semana da coleta mais as oito anteriores, por produto e unidade
EXTREME_MIN_PRICES = 30         # com menos preços na janela, as regras de distribuição não se aplicam


def parse_decimal(text):
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def canonical_price(value):
    """Representação única sem arredondar: 7.3, 7.30 e 7,30 viram "7.30"; 5.999 continua "5.999"."""
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    whole, _, fraction = text.partition(".")
    return f"{whole}.{fraction.ljust(2, '0')}"


def week_start(day):
    """Domingo que abre a semana da ANP (as semanas publicadas vão de domingo a sábado)."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def cnpj_check_digits_ok(cnpj):
    """Dígitos verificadores do CNPJ (módulo 11). Usa o valor ASCII − 48, que também cobre o CNPJ
    alfanumérico; a ingestão ainda só aceita CNPJ numérico."""
    if len(cnpj) != 14 or not cnpj[12:].isdigit():
        return False
    values = [ord(c) - 48 for c in cnpj.upper()]

    def digit(n):
        total = sum(values[n - 1 - i] * (2 + i % 8) for i in range(n))
        rest = total % 11
        return 0 if rest < 2 else 11 - rest

    return digit(12) == values[12] and digit(13) == values[13]


def row_reasons(row, period, as_of):
    """Devolve (motivos de quarentena, avisos) de uma observação já ingerida.

    `period` é (início, fim) do arquivo como `date`, ou (None, None) quando desconhecido.
    """
    reasons, flags = [], []
    price = parse_decimal(row["sale_price"])
    if price is None:
        reasons.append("preco_ausente_ou_ilegivel")
    elif price <= 0:
        reasons.append("preco_nao_positivo")
    try:
        day = date.fromisoformat(row["collection_date"])
    except ValueError:
        reasons.append("data_invalida")
    else:
        if day > as_of:
            reasons.append("data_futura")
        start, end = period
        if start is not None and not start <= day <= end:
            reasons.append("data_fora_do_periodo_do_arquivo")
    if not row["uf"]:
        reasons.append("uf_ausente")
    if not row["municipality_normalized"]:
        reasons.append("municipio_ausente")
    if row["cnpj_status"] == "missing":
        reasons.append("cnpj_ausente")
    elif row["cnpj_status"] not in VALID_CNPJ_STATUS or not row["cnpj"]:
        reasons.append("cnpj_malformado")
    elif not cnpj_check_digits_ok(row["cnpj"]):
        reasons.append("cnpj_digito_verificador_invalido")
    if not row["product"]:
        reasons.append("produto_desconhecido")
    if not row["unit"]:
        reasons.append("unidade_desconhecida")
    elif row["product"] and PRODUCT_UNITS.get(row["product"]) != row["unit"]:
        reasons.append("unidade_incompativel")

    if row["cep_status"] == "missing":
        flags.append("cep_ausente")
    elif not row["cep"]:
        flags.append("cep_ambiguo_ou_invalido")
    for field, flag in (("brand", "bandeira_ausente"), ("legal_name", "razao_social_ausente"),
                        ("address", "endereco_ausente")):
        if not row[field]:
            flags.append(flag)
    return reasons, flags


def price_bounds(prices):
    """Limites da janela: {"plausible": (mín, máx), "fence": (mín, máx)}, ou None quando há
    poucos preços. Fora de `plausible` → quarentena; fora só de `fence` → aviso (preço raro
    pode ser verdadeiro e continua publicado)."""
    if len(prices) < EXTREME_MIN_PRICES:
        return None
    q1, median, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    iqr = q3 - q1
    return {"plausible": (median / IMPLAUSIBLE_FACTOR, median * IMPLAUSIBLE_FACTOR),
            "fence": (q1 - EXTREME_IQR_FACTOR * iqr, q3 + EXTREME_IQR_FACTOR * iqr)}
