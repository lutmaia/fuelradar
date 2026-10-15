"""Avaliação numa janela (validação ou teste) com retreino a cada 13 semanas e janela crescente.

Cada ponto é (série elegível, origem, horizonte) com alvo observado e dentro do limite da janela.
O modelo que prevê uma origem foi treinado num corte anterior ou igual a ela, só com pares cujo
alvo já era conhecido no corte (protocolo, seção 2).
"""

import numpy as np
import pandas as pd

from ..forecasting.panel import eligibility
from .features import LAYER_COLUMNS, Features, labels, size_of
from .models import CLASS_MODELS, BaseRate, LightGBMValue
from .spec import HORIZONS, LAYERS, MIN_ORIGIN, MIN_TRAIN_ROWS, MODELS, RETRAIN_EVERY, TAU


def cutoffs_for(first_cutoff, last_origin, every=RETRAIN_EVERY):
    out, c = [], first_cutoff
    while c <= last_origin:
        out.append(c)
        c += every
    return out


def training_pairs(label_matrix, horizon, cutoff):
    """Pares (série, origem) com classe conhecida no corte: origem ≥ MIN_ORIGIN e origem + h ≤ corte."""
    last = cutoff - horizon
    if last < MIN_ORIGIN:
        return np.array([], dtype=int), np.array([], dtype=int)
    block = label_matrix[:, MIN_ORIGIN: last + 1]
    s, i = np.nonzero(block >= 0)
    return s, i + MIN_ORIGIN


def _moving_average(y, s, i):
    block = y[s, max(0, i - 3): i + 1]
    return float(np.nanmean(block)) if np.isfinite(block).sum() >= 3 else np.nan


def _model_columns(layer):
    return LAYER_COLUMNS[layer] + ["target_week_of_year", "target_month", "product", "is_state"]


def run_window(panel, features, origins, target_limit, first_cutoff, layers=LAYERS, models=MODELS, tau=TAU,
               horizons=HORIZONS, value=True, progress=None):
    """DataFrame com um ponto por linha e as probabilidades de cada camada × modelo (e o valor)."""
    eligible = {}
    for i in origins:
        for s in range(len(panel.keys)):
            eligible[(s, i)] = eligibility(panel, s, i)[0]
    records = []
    for h in horizons:
        lab = labels(panel, h, tau)
        schedule = cutoffs_for(first_cutoff, max(origins))
        for k, cutoff in enumerate(schedule):
            nxt = schedule[k + 1] if k + 1 < len(schedule) else max(origins) + 1
            serve = [i for i in origins if cutoff <= i < nxt]
            pts = [(s, i) for i in serve for s in range(len(panel.keys))
                   if eligible[(s, i)] and i + h <= target_limit and lab[s, i] >= 0]
            if not pts:
                continue
            ps, pi = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
            ts, ti = training_pairs(lab, h, cutoff)
            if len(ts) < MIN_TRAIN_ROWS:
                continue
            y_train = lab[ts, ti]
            base_frame_train = features.frame("L1", ts, ti, h)
            base_frame_pred = features.frame("L1", ps, pi, h)
            base = BaseRate().fit(base_frame_train["product"], base_frame_train["target_month"], y_train)
            out = {"origin": pi, "series": ps, "horizon": np.full(len(ps), h), "label": lab[ps, pi],
                   "actual": panel.y[ps, pi + h], "last": panel.y[ps, pi],
                   "ma4": np.array([_moving_average(panel.y, s, i) for s, i in zip(ps, pi)]),
                   "cutoff": np.full(len(ps), cutoff)}
            probs = base.predict(base_frame_pred["product"], base_frame_pred["target_month"])
            product_only = base.predict_product(base_frame_pred["product"])
            for c in range(3):
                out[f"base_p{c}"] = probs[:, c]
                out[f"base_produto_p{c}"] = product_only[:, c]
            delta_train = panel.y[ts, ti + h] - panel.y[ts, ti]
            for layer in layers:
                cols = _model_columns(layer)
                train = features.frame(layer, ts, ti, h)[cols]
                pred = features.frame(layer, ps, pi, h)[cols]
                for name in models:
                    model = CLASS_MODELS[name]()
                    if name == "logistica":
                        model.products = len(features.products)
                    p = model.fit(train, y_train).predict(pred)
                    for c in range(3):
                        out[f"{layer}_{name}_p{c}"] = p[:, c]
                if value:
                    out[f"{layer}_valor"] = panel.y[ps, pi] + LightGBMValue().fit(train, delta_train).predict(pred)
                if progress:
                    progress(h, cutoff, layer, len(ps))
            records.append(pd.DataFrame(out))
    frame = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    if not frame.empty:
        frame["week"] = [panel.weeks[i] for i in frame["origin"]]
        frame["product"] = [panel.keys[s][1] for s in frame["series"]]
        frame["size"] = [size_of(panel, s, i) for s, i in zip(frame["series"], frame["origin"])]
    return frame


def probabilities(points, key):
    """Matriz (n, 3) de probabilidades de um modelo (`base` ou `<camada>_<modelo>`)."""
    return points[[f"{key}_p0", f"{key}_p1", f"{key}_p2"]].to_numpy()


def reproducible(panel, features, layer, model, horizon, cutoff, series, origins, tau=TAU):
    """Dois treinos com os mesmos dados e semente: as probabilidades têm de ser idênticas."""
    lab = labels(panel, horizon, tau)
    ts, ti = training_pairs(lab, horizon, cutoff)
    cols = _model_columns(layer)
    train, pred = features.frame(layer, ts, ti, horizon)[cols], features.frame(layer, series, origins, horizon)[cols]
    runs = []
    for _ in range(2):
        m = CLASS_MODELS[model]()
        if model == "logistica":
            m.products = len(features.products)
        runs.append(m.fit(train, lab[ts, ti]).predict(pred))
    return bool(np.array_equal(runs[0], runs[1]))


__all__ = ["Features", "run_window", "probabilities", "reproducible", "cutoffs_for", "training_pairs"]
