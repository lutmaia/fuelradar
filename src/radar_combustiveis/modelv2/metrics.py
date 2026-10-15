"""Métricas de classe e de valor, *bootstrap* em blocos de origens, Holm e Diebold–Mariano.

Classes codificadas 0 (queda), 1 (estável), 2 (alta); probabilidades em matrizes (n, 3).
"""

import math

import numpy as np
from scipy import stats

from .spec import BOOTSTRAP_BLOCK_WEEKS, BOOTSTRAP_REPS, CALIBRATION_BINS, DM_LAGS, SEED


def one_hot(labels, k=3):
    out = np.zeros((len(labels), k))
    out[np.arange(len(labels)), np.asarray(labels, dtype=int)] = 1.0
    return out


def brier_points(probs, labels):
    """Brier multiclasse de cada ponto: soma, nas classes, de (probabilidade − indicadora)²."""
    return ((np.asarray(probs) - one_hot(labels, np.asarray(probs).shape[1])) ** 2).sum(axis=1)


def skill(model_loss, reference_loss):
    """1 − perda média do modelo ÷ perda média da referência (nos mesmos pontos)."""
    return 1.0 - float(np.sum(model_loss)) / float(np.sum(reference_loss))


def log_loss(probs, labels, eps=1e-12):
    p = np.clip(np.asarray(probs)[np.arange(len(labels)), np.asarray(labels, dtype=int)], eps, 1.0)
    return float(-np.log(p).mean())


def balanced_accuracy(probs, labels):
    predicted = np.asarray(probs).argmax(axis=1)
    labels = np.asarray(labels, dtype=int)
    recalls = [float((predicted[labels == k] == k).mean()) for k in np.unique(labels)]
    return float(np.mean(recalls))


def ece(probs, labels, bins=CALIBRATION_BINS):
    """Erro esperado de calibração por classe (faixas iguais de probabilidade), médio nas classes."""
    probs, truth = np.asarray(probs), one_hot(labels, np.asarray(probs).shape[1])
    edges = np.linspace(0.0, 1.0, bins + 1)
    errors = []
    for k in range(probs.shape[1]):
        p, y = probs[:, k], truth[:, k]
        which = np.clip(np.digitize(p, edges[1:-1], right=True), 0, bins - 1)
        total = 0.0
        for b in range(bins):
            mask = which == b
            if mask.any():
                total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
        errors.append(total)
    return float(np.mean(errors))


# -- Bootstrap em blocos de origens -----------------------------------------------------------


def _origin_sums(origins, *losses):
    """Soma de cada perda por origem (semana), na ordem das origens."""
    keys = np.unique(origins)
    index = np.searchsorted(keys, origins)
    sums = [np.bincount(index, weights=np.asarray(loss, dtype=float), minlength=len(keys)) for loss in losses]
    return keys, sums


def block_resamples(n, block=BOOTSTRAP_BLOCK_WEEKS, reps=BOOTSTRAP_REPS, seed=SEED):
    """Índices de origens para `reps` reamostragens em blocos móveis de `block` origens consecutivas."""
    rng = np.random.default_rng(seed)
    starts_max = max(n - block, 0)
    blocks = math.ceil(n / block)
    starts = rng.integers(0, starts_max + 1, size=(reps, blocks))
    idx = (starts[:, :, None] + np.arange(min(block, n))[None, None, :]).reshape(reps, -1)[:, :n]
    return idx


def bootstrap_skill(origins, model_loss, reference_loss, reps=BOOTSTRAP_REPS, seed=SEED):
    """Estimativa, IC de 95% e p-valor (bilateral) do *skill* com reamostragem de blocos de origens."""
    _, (m, r) = _origin_sums(origins, model_loss, reference_loss)
    estimate = 1.0 - m.sum() / r.sum()
    idx = block_resamples(len(m), reps=reps, seed=seed)
    draws = 1.0 - m[idx].sum(axis=1) / r[idx].sum(axis=1)
    return _summary(estimate, draws)


def bootstrap_gain(origins, loss_a, loss_b, reference_loss, reps=BOOTSTRAP_REPS, seed=SEED):
    """Ganho de *skill* de B sobre A (mesma referência): (perda A − perda B) ÷ perda da referência."""
    _, (a, b, r) = _origin_sums(origins, loss_a, loss_b, reference_loss)
    estimate = (a.sum() - b.sum()) / r.sum()
    idx = block_resamples(len(a), reps=reps, seed=seed)
    draws = (a[idx].sum(axis=1) - b[idx].sum(axis=1)) / r[idx].sum(axis=1)
    return _summary(estimate, draws)


def _summary(estimate, draws):
    lo, hi = np.percentile(draws, [2.5, 97.5])
    p = min(1.0, 2 * min(float((draws <= 0).mean()), float((draws >= 0).mean())))
    return {"estimate": float(estimate), "ci": [float(lo), float(hi)], "p": p}


def holm(pvalues):
    """p-valores ajustados por Holm, na ordem recebida (dict ou lista)."""
    items = list(pvalues.items()) if isinstance(pvalues, dict) else list(enumerate(pvalues))
    order = sorted(items, key=lambda kv: kv[1])
    m, running, adjusted = len(order), 0.0, {}
    for rank, (key, p) in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[key] = running
    return adjusted if isinstance(pvalues, dict) else [adjusted[i] for i in range(len(items))]


def diebold_mariano(origins, loss_a, loss_b, lags=DM_LAGS):
    """Teste de Diebold–Mariano sobre a diferença média de perda por origem (HAC de Newey–West)."""
    keys, (a, b) = _origin_sums(origins, loss_a, loss_b)
    _, (count,) = _origin_sums(origins, np.ones(len(origins)))
    d = (a - b) / count
    n = len(d)
    if n < 3:
        return {"statistic": None, "p": None, "n": n}
    centered = d - d.mean()
    variance = centered @ centered / n
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1 - lag / (lags + 1)
        variance += 2 * weight * (centered[lag:] @ centered[:-lag]) / n
    if variance <= 0:
        return {"statistic": None, "p": None, "n": n}
    statistic = d.mean() / math.sqrt(variance / n)
    return {"statistic": float(statistic), "p": float(2 * stats.norm.sf(abs(statistic))), "n": n}
