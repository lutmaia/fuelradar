"""Formatos brasileiros e rótulos em português. Sem Streamlit: testável isoladamente."""

from datetime import date, datetime, timedelta

ND = "N/D"

COVERAGE_LABELS = {
    "ok": "Cobertura normal",
    "low": "Cobertura baixa",
    "no_history": "Sem histórico para comparar",
    "not_applicable": "Agregado estadual",
    "no_data": "Sem dados na semana",
}
CHANGE_REASONS = {
    "NO_PREVIOUS_WEEK": "sem semana anterior",
    "LOW_COVERAGE": "cobertura insuficiente",
}
UNIT_LABELS = {"BRL/L": "R$/litro", "BRL/M3": "R$/m³", "BRL/13KG": "R$/botijão de 13 kg"}


def _br_number(value, decimals):
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def number_br(value):
    return ND if value is None else _br_number(value, 0)


def decimal_br(value, decimals=2):
    return ND if value is None else _br_number(value, decimals)


def brl(value, decimals=2):
    return ND if value is None else f"R$ {_br_number(value, decimals)}"


def signed_brl(value, decimals=2):
    if value is None:
        return ND
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}R$ {_br_number(abs(value), decimals)}"


def percent(value, decimals=1, signed=True):
    """Fração (0,0123) em porcentagem brasileira: +1,2%."""
    if value is None:
        return ND
    pct = value * 100
    sign = "+" if signed and round(pct, decimals) > 0 else "−" if round(pct, decimals) < 0 else ""
    return f"{sign}{_br_number(abs(pct), decimals)}%"


def date_br(value):
    if value is None:
        return ND
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%d/%m/%Y")


def datetime_br(value):
    """Instante ISO 8601 em UTC → 08/10/2026 19:25 UTC."""
    if value is None:
        return ND
    moment = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return moment.strftime("%d/%m/%Y %H:%M") + " UTC"


def week_range_br(week_start):
    start = date.fromisoformat(week_start)
    return f"{date_br(start)} a {date_br(start + timedelta(days=6))}"


def change_text(weekly_change):
    """Variação semanal da API: +1,2% ou 'N/D (motivo)'."""
    if weekly_change.get("value") is not None:
        return percent(weekly_change["value"])
    reason = CHANGE_REASONS.get(weekly_change.get("reason"))
    return f"{ND} ({reason})" if reason else ND


def coverage_label(status):
    return COVERAGE_LABELS.get(status, status)


def unit_label(unit):
    return UNIT_LABELS.get(unit, unit)


def retrieved_text(value):
    """`source_retrieved_at` nulo é um fato a mostrar, não um campo vazio."""
    return datetime_br(value) if value else "sem registro de download"


def retrieved_short(value):
    """Versão curta para cartões estreitos: só a data (o instante completo vai na ajuda)."""
    return date_br(value[:10]) if value else "sem registro"
