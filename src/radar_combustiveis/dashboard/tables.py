"""Tabelas do painel: valores tipados para ordenar, texto brasileiro só para exibir.

Uma coluna de datas guardada como texto `31/08/2026` ordena pelo dia antes do mês (31/08 vem antes
de 30/09 e depois de 31/03). Aqui cada coluna guarda o valor de verdade (`date`, número) e um
formatador cuida apenas de como ele aparece; o Streamlit ordena pelo valor, não pelo texto.
"""

from datetime import date

import pandas as pd

from . import formatting as fmt


def percent0(value):
    return fmt.percent(value, 0, signed=False)


def decimal1(value):
    return fmt.decimal_br(value, 1)


def rank(value):
    return str(int(value))


def money3(value):
    return fmt.brl(value, 3)


def day(value):
    return fmt.date_br(value)


def to_date(value):
    """Data ISO da API (`2026-09-28`) → `date`; nulo continua nulo."""
    return date.fromisoformat(value[:10]) if value else None


def styled(rows, formats=None, na_rep=None):
    """DataFrame tipado + exibição. `formats` mapeia coluna → função; `na_rep`, coluna → texto do vazio."""
    frame = pd.DataFrame(rows)
    styler = frame.style
    for column, formatter in (formats or {}).items():
        if column in frame.columns:
            styler = styler.format(formatter, subset=[column], na_rep=(na_rep or {}).get(column, fmt.ND))
    return styler
