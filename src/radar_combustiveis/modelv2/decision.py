"""Seleção do candidato na validação e regra de decisão no teste (protocolo, seção 6).

O desfecho primário é o *Brier skill score* da classe em h = 2 contra a taxa-base, sobre todos os
pontos da janela, com IC por *bootstrap* em blocos de 4 origens.
"""

import numpy as np

from . import metrics
from .experiment import probabilities
from .spec import LAYERS, MAX_ECE, MIN_GROUP_BSS, MIN_GROUP_POINTS, MODELS, PRIMARY_HORIZON


def model_keys(layers=LAYERS, models=MODELS):
    return [f"{layer}_{model}" for layer in layers for model in models]


def brier(points, key):
    return metrics.brier_points(probabilities(points, key), points["label"].to_numpy())


def primary(points, key, horizon=PRIMARY_HORIZON, **bootstrap):
    """BSS em h contra a taxa-base, com IC e p-valor; `n` pontos e `origins` origens."""
    part = points[points["horizon"] == horizon]
    if part.empty:
        return {"n": 0}
    result = metrics.bootstrap_skill(part["origin"].to_numpy(), brier(part, key), brier(part, "base"), **bootstrap)
    return {**result, "n": int(len(part)), "origins": int(part["origin"].nunique())}


def select_candidate(valid_points, keys=None, **bootstrap):
    """Na validação: o de maior BSS entre os que têm limite inferior do IC maior que zero (critério a)."""
    keys = keys or model_keys()
    table = {key: primary(valid_points, key, **bootstrap) for key in keys}
    passing = [k for k, r in table.items() if r.get("n") and r["ci"][0] > 0]
    candidate = max(passing, key=lambda k: table[k]["estimate"]) if passing else None
    return {"candidate": candidate, "validation": table}


def group_skills(points, key, horizon=PRIMARY_HORIZON):
    """BSS por produto, porte e horizonte (grupos com pelo menos 200 pontos), para o critério (c)."""
    out = {}
    for column in ("product", "size"):
        part = points[points["horizon"] == horizon]
        for value, group in part.groupby(column):
            if len(group) >= MIN_GROUP_POINTS:
                out[f"{column}:{value}"] = metrics.skill(brier(group, key), brier(group, "base"))
    for h, group in points.groupby("horizon"):
        if len(group) >= MIN_GROUP_POINTS:
            out[f"horizon:{h}"] = metrics.skill(brier(group, key), brier(group, "base"))
    return out


def decide(test_points, candidate, reproducible, **bootstrap):
    """Critérios (b) a (e) para o candidato escolhido na validação. Sem candidato, nada é publicado."""
    if candidate is None:
        return {"approved": False, "candidate": None, "checks": {}, "reason": "nenhum modelo passou o critério (a)"}
    result = primary(test_points, candidate, **bootstrap)
    groups = group_skills(test_points, candidate)
    part = test_points[test_points["horizon"] == PRIMARY_HORIZON]
    calibration = metrics.ece(probabilities(part, candidate), part["label"].to_numpy()) if len(part) else None
    checks = {
        "b_ganho_confirmado_no_teste": bool(result.get("n") and result["estimate"] > 0 and result["ci"][0] > 0),
        "c_sem_piora_em_grupo": bool(groups) and all(v >= MIN_GROUP_BSS for v in groups.values()),
        "d_calibracao": calibration is not None and calibration <= MAX_ECE,
        "e_reprodutivel": bool(reproducible),
    }
    return {"approved": all(checks.values()), "candidate": candidate, "checks": checks, "test": result,
            "groups": groups, "ece": calibration,
            "worst_group": min(groups.items(), key=lambda kv: kv[1]) if groups else None}


def calibration_of(points, key, horizon=PRIMARY_HORIZON):
    part = points[points["horizon"] == horizon]
    return metrics.ece(probabilities(part, key), part["label"].to_numpy()) if len(part) else None


def finite(values):
    return [v for v in values if v is not None and np.isfinite(v)]
