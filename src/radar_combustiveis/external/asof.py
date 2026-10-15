"""Alinhamento *as-of*: o valor de uma série externa que já podia ser conhecido numa data.

Uma previsão feita a partir da semana W (domingo) só pode usar valores com `available_at` até o
sábado de W, o último dia da semana de origem. É a regra que impede olhar para o futuro (desenho, 4.3).
"""

from bisect import bisect_right
from datetime import timedelta


def as_of(observations, when):
    """A observação mais recente (pelo fim do período) já disponível em `when`, ou None.

    `observations`: dicts com `period_end`, `available_at` e `value` de uma única série."""
    known = [o for o in observations if o["available_at"] <= when]
    return max(known, key=lambda o: o["period_end"], default=None)


def weekly_as_of(observations, origin_weeks):
    """{semana de origem: observação disponível no sábado dela} para várias origens de uma série.

    Ordena uma vez e percorre as origens em ordem; equivale a chamar `as_of` para cada uma."""
    by_available = sorted(observations, key=lambda o: o["available_at"])
    days = [o["available_at"] for o in by_available]
    result, best, used = {}, None, 0
    for week in sorted(origin_weeks):
        cutoff = week + timedelta(days=6)
        upto = bisect_right(days, cutoff)
        for o in by_available[used:upto]:
            if best is None or o["period_end"] > best["period_end"]:
                best = o
        used = max(used, upto)
        result[week] = best
    return result
