"""Backtesting com origem deslizante, intervalos calibrados, métricas e regra de aprovação.

Sem divisão aleatória: a cada origem o candidato é treinado só com alvos já conhecidos naquela
semana (seção 14.5) e avaliado nas quatro semanas seguintes. Os intervalos usam resíduos de
origens anteriores (seção 14.9), nunca da própria origem avaliada.
"""

import numpy as np
import pandas as pd

from .models import BASELINES, CANDIDATE, HORIZONS, baseline_forecast, candidate_forecast, train_candidate
from .panel import eligibility

MODELS = BASELINES + (CANDIDATE,)
STEP = 4                  # semanas entre origens do backtest
MIN_ORIGIN = 60           # nenhuma série tem 52 semanas de dado antes disso
BURN_IN = 8               # primeiras origens só alimentam a calibração dos intervalos
LOWER_Q, UPPER_Q = 0.10, 0.90          # intervalo de 80%
ANOMALY_LOWER_Q, ANOMALY_UPPER_Q = 0.005, 0.995  # intervalo de 99%: "incomum" tem de ser raro
MIN_POOL = 30             # resíduos mínimos por grupo; abaixo disso usa o grupo mais geral
ANOMALY_MIN_POOL = 200    # quantis de cauda pedem mais resíduos
INTERVAL_LEVEL = UPPER_Q - LOWER_Q

# Regra de aprovação (seção 14.8). Os limites de viés e de cobertura são escolhas deste projeto.
MIN_IMPROVEMENT = 0.05
MAX_GROUP_REGRESSION = 0.05
MAX_BIAS_SHARE_OF_MAE = 0.25
COVERAGE_RANGE = (0.70, 0.90)


def size_group(panel, s, i):
    if panel.is_state(s):
        return "estado"
    recent = panel.stations[s, max(0, i - 25): i + 1]
    median = float(np.nanmedian(recent)) if np.isfinite(recent).any() else 0.0
    return "pequeno (<10 postos)" if median < 10 else "medio (10 a 29)" if median < 30 else "grande (30+)"


def origins_for(panel, step=STEP, min_origin=MIN_ORIGIN):
    found, i = [], panel.last - max(HORIZONS)
    while i >= min_origin:
        found.append(i)
        i -= step
    return sorted(found)


def _scale(panel, s, i):
    steps = np.abs(np.diff(panel.y[s, : i + 1]))
    steps = steps[~np.isnan(steps)]
    return float(steps.mean()) if steps.size else np.nan


def collect_points(panel, features, origins, with_candidate=True, progress=None):
    """Uma linha por (origem, série, horizonte) elegível com alvo observado, com a previsão de cada modelo."""
    base = {(name, h): baseline_forecast(panel, name, h) for name in BASELINES for h in HORIZONS}
    records = []
    for origin in origins:
        eligible = [s for s in range(len(panel.keys)) if eligibility(panel, s, origin)[0]]
        if not eligible:
            continue
        model = train_candidate(features, origin) if with_candidate else None
        groups = {s: size_group(panel, s, origin) for s in eligible}
        scales = {s: _scale(panel, s, origin) for s in eligible}
        s_arr = np.array(eligible)
        for h in HORIZONS:
            target = origin + h
            if target > panel.last:
                continue
            actual = panel.y[s_arr, target]
            forecasts = {name: base[(name, h)][s_arr, origin] for name in BASELINES}
            forecasts[CANDIDATE] = (candidate_forecast(model, features, s_arr, origin, h)
                                    if model is not None else np.full(len(s_arr), np.nan))
            for k, s in enumerate(eligible):
                if np.isnan(actual[k]):
                    continue
                records.append({
                    "origin": origin, "target": target, "horizon": h, "series": s,
                    "level": "estado" if panel.is_state(s) else "municipio",
                    "product": panel.keys[s][1], "group": groups[s], "scale": scales[s],
                    "weight": panel.stations[s, target] if np.isfinite(panel.stations[s, target]) else 1.0,
                    "actual": actual[k], **{name: forecasts[name][k] for name in MODELS}})
        if progress:
            progress(origin, len(records))
    return pd.DataFrame.from_records(records)


def _pool_quantiles(pool, models, q_lo, q_hi):
    """Quantis de resíduo (real - previsão) por (nível, produto, horizonte) e por (nível, horizonte)."""
    out = {}
    for m in models:
        resid = (pool["actual"] - pool[m]).dropna()
        frame = pool.loc[resid.index, ["level", "product", "horizon"]].assign(r=resid)
        for keys, cols in (("fine", ["level", "product", "horizon"]), ("coarse", ["level", "horizon"])):
            grouped = frame.groupby(cols)["r"]
            quant = grouped.quantile([q_lo, q_hi]).unstack()
            count = grouped.size()
            for key in quant.index:
                out[(m, keys, key if isinstance(key, tuple) else (key,))] = (
                    float(quant.loc[key, q_lo]), float(quant.loc[key, q_hi]), int(count.loc[key]))
    return out


def _lookup(table, m, level, product, horizon, min_pool=MIN_POOL):
    fine = table.get((m, "fine", (level, product, horizon)))
    if fine and fine[2] >= min_pool:
        return fine[:2]
    coarse = table.get((m, "coarse", (level, horizon)))
    if coarse and coarse[2] >= min_pool:
        return coarse[:2]
    return None


def add_intervals(points, models=MODELS, q_lo=LOWER_Q, q_hi=UPPER_Q):
    """Colunas `<modelo>_lo`/`_hi`: previsão + quantis dos resíduos de origens anteriores (sem vazamento)."""
    points = points.copy()
    for m in models:
        points[f"{m}_lo"], points[f"{m}_hi"] = np.nan, np.nan
    for origin in sorted(points["origin"].unique()):
        pool = points[points["target"] <= origin]  # alvos já conhecidos na semana da origem
        if pool.empty:
            continue
        table = _pool_quantiles(pool, models, q_lo, q_hi)
        current = points["origin"] == origin
        for idx in points.index[current]:
            row = points.loc[idx]
            for m in models:
                bounds = _lookup(table, m, row["level"], row["product"], row["horizon"])
                if bounds and np.isfinite(row[m]):
                    points.at[idx, f"{m}_lo"] = row[m] + bounds[0]
                    points.at[idx, f"{m}_hi"] = row[m] + bounds[1]
    return points


def score(frame, model):
    """Métricas de um modelo sobre `frame` (cada linha é um ponto previsto e observado)."""
    if frame.empty:
        return {"n": 0}
    error = frame[model] - frame["actual"]  # positivo = superestimou
    abs_error = error.abs()
    weight = frame["weight"]
    scaled = (abs_error / frame["scale"]).replace([np.inf, -np.inf], np.nan).dropna()
    has_interval = frame[f"{model}_lo"].notna() if f"{model}_lo" in frame else pd.Series(False, index=frame.index)
    inside = ((frame["actual"] >= frame[f"{model}_lo"]) & (frame["actual"] <= frame[f"{model}_hi"]))[has_interval]
    width = (frame[f"{model}_hi"] - frame[f"{model}_lo"])[has_interval]
    return {
        "n": int(len(frame)),
        "mae": float(abs_error.mean()),
        "wmae": float((abs_error * weight).sum() / weight.sum()),
        "wape": float(abs_error.sum() / frame["actual"].abs().sum()),
        "mase": float(scaled.mean()) if len(scaled) else None,
        "bias": float(error.mean()),
        "coverage": float(inside.mean()) if len(inside) else None,
        "interval_width": float(width.mean()) if len(width) else None,
        "interval_n": int(has_interval.sum()),
    }


def common_set(points, models=MODELS):
    """Pontos em que todos os modelos têm previsão: comparação justa entre eles."""
    return points.dropna(subset=list(models))


def summarize(points, models=MODELS, burn_in=BURN_IN):
    """Métricas gerais e por grupo, sobre as origens posteriores ao período de calibração."""
    origins = sorted(points["origin"].unique())
    evaluated = set(origins[burn_in:])
    frame = common_set(points[points["origin"].isin(evaluated)], models)
    summary = {"origins": [int(o) for o in origins], "evaluated_origins": [int(o) for o in sorted(evaluated)],
               "points": int(len(frame)), "overall": {m: score(frame, m) for m in models}}
    for name, column in (("by_horizon", "horizon"), ("by_product", "product"), ("by_level", "level"),
                         ("by_group", "group")):
        summary[name] = {str(key): {m: score(part, m) for m in models} for key, part in frame.groupby(column)}
    return summary, frame


def decide(summary, reproducible):
    """Regra 14.8: devolve {approved, best_baseline, checks, improvement}. Sem ganho, o baseline fica."""
    overall = summary["overall"]
    best = min(BASELINES, key=lambda m: overall[m].get("wmae", np.inf))
    cand, base = overall[CANDIDATE], overall[best]
    if not cand.get("n"):
        return {"approved": False, "best_baseline": best, "improvement": None,
                "checks": {"candidato_avaliado": False}}
    improvement = 1 - cand["wmae"] / base["wmae"]
    regressions = []
    for part in ("by_product", "by_level", "by_horizon", "by_group"):
        for key, scores in summary[part].items():
            if scores[CANDIDATE].get("n", 0) >= 30 and scores[best]["wmae"] > 0:
                if scores[CANDIDATE]["wmae"] / scores[best]["wmae"] - 1 > MAX_GROUP_REGRESSION:
                    regressions.append(f"{part}:{key}")
    coverage = cand.get("coverage")
    checks = {
        "melhora_minima_de_5pct_no_mae_ponderado": bool(improvement >= MIN_IMPROVEMENT),
        "sem_regressao_grave_em_grupo": not regressions,
        "vies_aceitavel": bool(abs(cand["bias"]) <= MAX_BIAS_SHARE_OF_MAE * cand["mae"]),
        "cobertura_do_intervalo_na_faixa": bool(coverage is not None and COVERAGE_RANGE[0] <= coverage <= COVERAGE_RANGE[1]),
        "reprodutivel": bool(reproducible),
    }
    return {"approved": all(checks.values()), "best_baseline": best, "improvement": float(improvement),
            "checks": checks, "regressions": regressions}
