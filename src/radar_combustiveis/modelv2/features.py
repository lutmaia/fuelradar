"""Alvos de classe e variáveis por camada (protocolo, seções 3 e 4). Tudo olha só para trás.

L1: variáveis da própria série (as do backtest de valor). L2: sinais do estado no mesmo produto. L3: dólar
e preço de produtores, só com valores já disponíveis (`available_at`) no sábado da semana de origem.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from ..forecasting.models import FEATURES as L1_NAMES, _series_features
from ..forecasting.panel import STATE
from .spec import EVENT_THRESHOLD, MOVE_THRESHOLD, PRODUCER_OF, SIZE_LARGE, SIZE_MEDIUM, SIZE_SMALL, SIZE_WINDOW, TAU, \
    WEEKS_SINCE_CAP

L2_NAMES = ["state_d1", "state_d4", "share_up", "share_down"]
L3_NAMES = ["usd_d1", "usd_d4", "prod_d1", "prod_d4", "prod_event", "prod_weeks_since"]
LAYER_COLUMNS = {"L1": L1_NAMES, "L2": L1_NAMES + L2_NAMES, "L3": L1_NAMES + L2_NAMES + L3_NAMES}


def labels(panel, horizon, tau=TAU):
    """Matriz (séries, semanas): classe de y[t + h] − y[t] na origem t (−1 sem um dos dois)."""
    y = panel.y
    out = np.full(y.shape, -1, dtype=int)
    delta = y[:, horizon:] - y[:, :-horizon]
    cls = np.where(delta <= -tau + 1e-9, 0, np.where(delta >= tau - 1e-9, 2, 1))
    out[:, :-horizon] = np.where(np.isnan(delta), -1, cls)
    return out


def size_of(panel, s, i):
    """Porte pela mediana de postos nas 26 semanas até a origem (protocolo do estudo, seção 1)."""
    if panel.is_state(s):
        return "estado"
    recent = panel.stations[s, max(0, i + 1 - SIZE_WINDOW): i + 1]
    recent = recent[np.isfinite(recent)]
    median = float(np.median(recent)) if recent.size else 0.0
    return ("grande" if median >= SIZE_LARGE else "medio" if median >= SIZE_MEDIUM
            else "pequeno" if median >= SIZE_SMALL else "menor")


# -- Fontes externas, alinhadas na data de origem -------------------------------------------


def _usd_levels(daily, cutoffs):
    """Média do dólar nos 7 dias até cada corte, só com cotações já disponíveis nele."""
    if not daily:
        return np.full(len(cutoffs), np.nan)
    ends = np.array([o["period_end"].toordinal() for o in daily])
    avail = np.array([o["available_at"].toordinal() for o in daily])
    values = np.array([float(o["value"]) for o in daily])
    out = []
    for cut in cutoffs:
        c = cut.toordinal()
        mask = (ends > c - 7) & (ends <= c) & (avail <= c)
        out.append(values[mask].mean() if mask.any() else np.nan)
    return np.array(out)


def _producer_features(weekly, cutoffs):
    """(Δ1, Δ4, evento, semanas desde o evento) por corte, com as semanas já publicadas nele."""
    rows = sorted(weekly, key=lambda o: o["period_end"])
    avail = [o["available_at"] for o in rows]
    out = np.full((len(cutoffs), 4), np.nan)
    for k, cut in enumerate(cutoffs):
        known = [o for o, a in zip(rows, avail) if a <= cut]
        if len(known) < 2:
            continue
        values = [float(o["value"]) for o in known]
        d1 = values[-1] / values[-2] - 1
        d4 = values[-1] / values[-5] - 1 if len(values) >= 5 else np.nan
        since = WEEKS_SINCE_CAP
        for j in range(len(values) - 1, 0, -1):
            if abs(values[j] / values[j - 1] - 1) >= EVENT_THRESHOLD:
                since = min(WEEKS_SINCE_CAP, (cut - known[j]["period_end"]).days / 7)
                break
        out[k] = (d1, d4, float(abs(d1) >= EVENT_THRESHOLD), since)
    return out


class Features:
    """Variáveis de todas as séries e origens, calculadas uma vez por painel.

    `external`: {"usd": [observações diárias], "producers": {código: [observações semanais]}}, cada
    observação com `period_end`, `available_at` e `value`. Sem `external`, L3 fica ausente (NaN)."""

    def __init__(self, panel, external=None):
        self.panel = panel
        keys = panel.keys
        self.products = sorted({k[1] for k in keys})
        self.product_code = np.array([self.products.index(k[1]) for k in keys])
        self.state_flag = np.array([float(panel.is_state(s)) for s in range(len(keys))])
        frames = [_series_features(panel.y[s], panel.stations[s], panel.low[s]) for s in range(len(keys))]
        self.l1 = np.stack([f[L1_NAMES].to_numpy(dtype=float) for f in frames])     # (S, T, F1)
        self.by_product = self._state_signals()                                      # produto -> (T, 4)
        self.external = self._external(external or {})                               # produto -> (T, 6)

    def _state_signals(self):
        panel, out = self.panel, {}
        y, low = panel.y, panel.low
        for product in self.products:
            state = [s for s, k in enumerate(panel.keys) if k == (STATE, product)]
            cities = [s for s, k in enumerate(panel.keys) if k[1] == product and k[0] != STATE]
            signals = np.full((y.shape[1], 4), np.nan)
            if state:
                sy = y[state[0]]
                signals[1:, 0] = sy[1:] - sy[:-1]
                signals[4:, 1] = sy[4:] - sy[:-4]
            if cities:
                cy, cl = y[cities], low[cities]
                delta = cy[:, 1:] - cy[:, :-1]
                usable = ~np.isnan(delta) & ~cl[:, 1:] & ~cl[:, :-1]
                count = usable.sum(axis=0)
                with np.errstate(invalid="ignore", divide="ignore"):
                    signals[1:, 2] = np.where(count > 0, ((delta >= MOVE_THRESHOLD) & usable).sum(axis=0) / count, np.nan)
                    signals[1:, 3] = np.where(count > 0, ((delta <= -MOVE_THRESHOLD) & usable).sum(axis=0) / count, np.nan)
            out[product] = signals
        return out

    def _external(self, external):
        cutoffs = [w + timedelta(days=6) for w in self.panel.weeks]   # sábado de cada semana de origem
        usd = _usd_levels(external.get("usd", []), cutoffs)
        usd_feats = np.full((len(cutoffs), 2), np.nan)
        usd_feats[1:, 0] = usd[1:] / usd[:-1] - 1
        usd_feats[4:, 1] = usd[4:] / usd[:-4] - 1
        producers = {code: _producer_features(rows, cutoffs) for code, rows in external.get("producers", {}).items()}
        out = {}
        for product in self.products:
            prod = producers.get(PRODUCER_OF.get(product), np.full((len(cutoffs), 4), np.nan))
            out[product] = np.hstack([usd_feats, prod])
        return out

    def frame(self, layer, series, origins, horizon):
        """DataFrame de modelo (camada, pares série × origem, horizonte), com produto e calendário."""
        series, origins = np.asarray(series), np.asarray(origins)
        data = pd.DataFrame(self.l1[series, origins], columns=L1_NAMES)
        if layer in ("L2", "L3"):
            l2 = np.array([self.by_product[self.products[c]][i] for c, i in zip(self.product_code[series], origins)])
            data[L2_NAMES] = l2.reshape(len(series), len(L2_NAMES))
        if layer == "L3":
            l3 = np.array([self.external[self.products[c]][i] for c, i in zip(self.product_code[series], origins)])
            data[L3_NAMES] = l3.reshape(len(series), len(L3_NAMES))
        targets = pd.DatetimeIndex([self.panel.weeks[0] + timedelta(weeks=int(i) + horizon) for i in origins])
        data["target_week_of_year"] = targets.isocalendar()["week"].to_numpy().astype(float)
        data["target_month"] = targets.month.to_numpy().astype(float)
        data["product"] = self.product_code[series]
        data["is_state"] = self.state_flag[series]
        return data
