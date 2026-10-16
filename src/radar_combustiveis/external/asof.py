"""Alinhamento *as-of*: o valor de uma série externa que já podia ser conhecido numa data.

Uma previsão feita a partir da semana W (domingo) só pode usar valores com `available_at` até o
sábado de W, o último dia da semana de origem. É a regra que impede olhar para o futuro (desenho, 4.3).
"""


def as_of(observations, when):
    """A observação mais recente (pelo fim do período) já disponível em `when`, ou None.

    `observations`: dicts com `period_end`, `available_at` e `value` de uma única série."""
    known = [o for o in observations if o["available_at"] <= when]
    return max(known, key=lambda o: o["period_end"], default=None)
