"""Gate G1 (protocolo, seção 5): passa com ao menos dois achados estáveis entre Q1, Q2 e Q3."""

MIN_STABLE = 2


def g1(results):
    """`results` é {"q1": ..., "q2": ..., "q3": ...}, cada um com a chave `stable`."""
    stable = sorted(q for q, r in results.items() if r["stable"])
    return dict(stable=stable, passed=len(stable) >= MIN_STABLE, required=MIN_STABLE)
