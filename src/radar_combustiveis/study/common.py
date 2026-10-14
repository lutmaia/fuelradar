"""Peças comuns às três análises: rótulos, porte, Holm, bootstrap em blocos de semanas e sobrevivência."""

import math

import numpy as np
from scipy import stats

from ..forecasting import protocol

PRIMARY_PRODUCT = "GASOLINA_COMUM"
SECONDARY_PRODUCTS = ("GASOLINA_ADITIVADA", "ETANOL_HIDRATADO", "DIESEL_COMUM", "DIESEL_S10", "GNV")
WHITE = "BRANCA"
BRAND_ALIASES = {"VIBRA ENERGIA": "VIBRA", "ALESAT": "ALE"}
ALPHA = 0.05


def normalize_brand(brand):
    text = (brand or "").strip().upper()
    return BRAND_ALIASES.get(text, text) or None


def size_class(median_stations):
    """Porte pela mediana semanal de postos com gasolina comum (protocolo, seção 1)."""
    if median_stations >= 20:
        return "grande"
    if median_stations >= 8:
        return "medio"
    if median_stations >= 3:
        return "pequeno"
    return None


def check_window(weeks):
    """Toda entrada de análise passa por aqui: recusa o teste final e semanas antes dos dados."""
    weeks = list(weeks)
    protocol.assert_no_holdout(weeks)
    early = [w for w in weeks if w < protocol.STUDY_START]
    if early:
        raise ValueError(f"semana {min(early)} anterior ao início do estudo")


def in_period(frame, period, column="week_start"):
    start, end = period
    return frame[(frame[column] >= start) & (frame[column] <= end)]


def holm(pvalues):
    """p-valores ajustados por Holm, na ordem recebida; NaN fica NaN e não conta como teste."""
    p = np.asarray(pvalues, dtype=float)
    out = np.full(p.shape, np.nan)
    idx = np.flatnonzero(~np.isnan(p))
    m = len(idx)
    running = 0.0
    for rank, i in enumerate(idx[np.argsort(p[idx], kind="stable")]):
        running = max(running, min(1.0, (m - rank) * p[i]))
        out[i] = running
    return out


def same_sign(*values):
    """Verdadeiro se todos os valores são finitos, diferentes de zero e com o mesmo sinal."""
    signs = {math.copysign(1, v) for v in values if v is not None and np.isfinite(v) and v != 0}
    finite = all(v is not None and np.isfinite(v) and v != 0 for v in values)
    return finite and len(signs) == 1


# -- Bootstrap em blocos móveis de semanas ----------------------------------------------------


def block_bootstrap(groups, statistic, reps=protocol.BOOTSTRAP_REPS, block=protocol.BOOTSTRAP_BLOCK_WEEKS,
                    seed=protocol.SEED):
    """Reamostra semanas em blocos móveis consecutivos e aplica `statistic` a cada reamostra.

    `groups` é a lista, em ordem cronológica, do que cada semana com dado contribui (qualquer
    objeto); `statistic` recebe uma lista desses objetos (com repetição) e devolve um número.
    Devolve o vetor das `reps` estatísticas; reamostras em que a estatística não existe dão NaN.
    """
    n = len(groups)
    if n == 0:
        return np.full(reps, np.nan)
    block = min(block, n)
    blocks = math.ceil(n / block)
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for r in range(reps):
        starts = rng.integers(0, n - block + 1, size=blocks)
        positions = (starts[:, None] + np.arange(block)).ravel()[:n]
        out[r] = statistic([groups[i] for i in positions])
    return out


def percentile_ci(draws, level=0.95):
    draws = np.asarray(draws, dtype=float)
    draws = draws[np.isfinite(draws)]
    if len(draws) == 0:
        return (math.nan, math.nan)
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(draws, [tail, 100 - tail])
    return (float(low), float(high))


def bootstrap_pvalue(draws):
    """p-valor bilateral do percentil: duas vezes a menor fração de reamostras de cada lado do zero."""
    draws = np.asarray(draws, dtype=float)
    draws = draws[np.isfinite(draws)]
    if len(draws) == 0:
        return math.nan
    return float(min(1.0, 2 * min((draws <= 0).mean(), (draws >= 0).mean())))


# -- Sobrevivência (tempo discreto, em semanas) -----------------------------------------------


def kaplan_meier(durations, events):
    """Curva de Kaplan–Meier. Censurado no tempo c continua em risco em c (convenção usual).

    Devolve (tempos de evento, sobrevivência logo depois de cada tempo, mediana); a mediana é o
    primeiro tempo com sobrevivência ≤ 0,5, ou NaN se a curva não chega lá.
    """
    d = np.asarray(durations, dtype=float)
    e = np.asarray(events, dtype=bool)
    times = np.unique(d[e])
    surv, s = [], 1.0
    for t in times:
        at_risk = np.sum(d >= t)
        deaths = np.sum((d == t) & e)
        s *= 1 - deaths / at_risk
        surv.append(s)
    surv = np.array(surv)
    below = np.flatnonzero(surv <= 0.5)
    median = float(times[below[0]]) if len(below) else math.nan
    return times, surv, median


def logrank(durations_a, events_a, durations_b, events_b):
    """Teste log-rank de duas curvas; devolve o p-valor (qui-quadrado com 1 grau de liberdade)."""
    da, ea = np.asarray(durations_a, float), np.asarray(events_a, bool)
    db, eb = np.asarray(durations_b, float), np.asarray(events_b, bool)
    times = np.unique(np.concatenate([da[ea], db[eb]]))
    observed_minus_expected, variance = 0.0, 0.0
    for t in times:
        na, nb = np.sum(da >= t), np.sum(db >= t)
        oa, ob = np.sum((da == t) & ea), np.sum((db == t) & eb)
        n, o = na + nb, oa + ob
        if n < 2:
            continue
        observed_minus_expected += oa - o * na / n
        variance += o * (na / n) * (nb / n) * (n - o) / (n - 1)
    if variance <= 0:
        return math.nan
    return float(stats.chi2.sf(observed_minus_expected ** 2 / variance, 1))
