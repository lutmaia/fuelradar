"""Calibração por temperatura (protocolo ao vivo, seção 1): `softmax(log(p) / T)`, um T por horizonte.

T > 1 suaviza (menos confiante), T < 1 acentua. A classe mais provável nunca muda.
"""

import numpy as np
from scipy.optimize import minimize_scalar

from . import metrics

T_BOUNDS = (0.25, 4.0)


def apply(probs, temperature):
    z = np.log(np.clip(np.asarray(probs, dtype=float), 1e-12, 1.0)) / temperature
    z -= z.max(axis=1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(axis=1, keepdims=True)


def fit(probs, labels, bounds=T_BOUNDS):
    """T que minimiza o *log-loss* nos pontos dados (a validação da modelagem v2)."""
    result = minimize_scalar(lambda t: metrics.log_loss(apply(probs, t), labels), bounds=bounds, method="bounded",
                             options={"xatol": 1e-6})
    return float(result.x)
