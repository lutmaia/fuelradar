"""Qualidade das fontes externas (desenho, seção 4.4). Falha crítica bloqueia aquela fonte, não as outras.

Críticas: nenhuma linha, chave repetida, valor fora da faixa plausível, período incoerente.
Avisos: lacunas nas séries semanais desde o início do histórico e atraso maior que o esperado.
"""

from collections import defaultdict
from datetime import timedelta

from .sources import DISTRIBUTION, DOLLAR, HISTORY_START, PRODUCERS

PLAUSIBLE = {DOLLAR.source_id: (1.0, 20.0), PRODUCERS.source_id: (0.3, 20.0), DISTRIBUTION.source_id: (0.5, 20.0)}
PERIOD_DAYS = {DOLLAR.source_id: 0, PRODUCERS.source_id: 6, DISTRIBUTION.source_id: 6}
MAX_LAG_DAYS = {DOLLAR.source_id: 7, PRODUCERS.source_id: 21, DISTRIBUTION.source_id: 75}
MAX_LISTED = 20


def key_of(row):
    return row["source_id"], row["product"], row["geo_level"], row["geo"], row["period_start"]


def check(source_id, rows, retrieved_on):
    """Relatório {decision, rows, critical, warnings, latest_period_end}. `decision`: ok, aviso ou bloquear."""
    critical, warnings = [], []
    if not rows:
        critical.append("nenhuma linha lida")
    low, high = PLAUSIBLE[source_id]
    seen, series = {}, defaultdict(list)
    for row in rows:
        key = key_of(row)
        if key in seen:
            critical.append(f"chave repetida: {key[1:]}")
        seen[key] = row
        if not low <= row["value"] <= high:
            critical.append(f"valor fora da faixa {low}–{high}: {row['value']} em {key[1:]}")
        if (row["period_end"] - row["period_start"]).days != PERIOD_DAYS[source_id]:
            critical.append(f"período incoerente: {row['period_start']} a {row['period_end']}")
        series[key[1:4]].append(row["period_start"])
    if PERIOD_DAYS[source_id] == 6:  # semanais: lacunas a partir do início do histórico do projeto
        for name, starts in sorted(series.items()):
            recent = sorted(d for d in starts if d >= HISTORY_START)
            missing = sum((b - a).days // 7 - 1 for a, b in zip(recent, recent[1:]) if (b - a).days != 7)
            if missing and name[1] != "municipio":  # municípios têm lacunas por natureza (sem venda na semana)
                warnings.append(f"{missing} semana(s) sem valor em {name}")
    latest = max((r["period_end"] for r in rows), default=None)
    if latest is not None and (retrieved_on - latest).days > MAX_LAG_DAYS[source_id]:
        warnings.append(f"dado mais recente de {latest}, {(retrieved_on - latest).days} dias antes do download")
    decision = "bloquear" if critical else "aviso" if warnings else "ok"
    return {"source_id": source_id, "decision": decision, "rows": len(rows), "latest_period_end": latest,
            "critical": critical[:MAX_LISTED], "critical_total": len(critical),
            "warnings": warnings[:MAX_LISTED], "warnings_total": len(warnings)}


def lag_days(latest, retrieved_on):
    return None if latest is None else (retrieved_on - latest).days


def week_of(day):
    """Domingo da semana da ANP (domingo a sábado) que contém o dia."""
    return day - timedelta(days=(day.weekday() + 1) % 7)
