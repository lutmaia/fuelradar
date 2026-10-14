"""Q2 — dinâmica do preço no posto (protocolo, seção 3).

Só pares do mesmo posto e produto em semanas consecutivas; mudança quando |Δ| ≥ limiar. A
duração do preço vai de uma mudança observada à seguinte (evento) ou até uma lacuna de
observação ou o fim dos dados (censura).

Entrada: observações com `station_id`, `product`, `week_start` (date), `price` e `extreme`.
"""

import math

import numpy as np
import pandas as pd

from ..forecasting import protocol
from .common import (PRIMARY_PRODUCT, SECONDARY_PRODUCTS, block_bootstrap, bootstrap_pvalue, check_window,
                     holm, in_period, kaplan_meier, logrank, percentile_ci, same_sign)

THRESHOLD = 0.01
ROBUST_THRESHOLD = 0.05
SERIES = ["station_id", "product"]


def _sorted(obs):
    df = obs[SERIES + ["week_start", "price"]].copy()
    df["week"] = (pd.to_datetime(df["week_start"]) - pd.Timestamp(protocol.DEV_START)).dt.days // 7
    df["price"] = df["price"].astype(float)
    return df.sort_values(SERIES + ["week"], kind="stable").reset_index(drop=True)


def pairs(obs):
    """Variações entre semanas consecutivas do mesmo posto e produto (pares com lacuna saem)."""
    df = _sorted(obs)
    same = (df["station_id"] == df["station_id"].shift()) & (df["product"] == df["product"].shift())
    consecutive = same & (df["week"] - df["week"].shift() == 1)
    out = df.loc[consecutive, SERIES + ["week_start", "week"]].copy()
    # Arredondado a 4 casas: 5,99 − 5,98 em ponto flutuante é 0,00999…, e isso não pode virar "sem mudança".
    out["delta"] = (df["price"] - df["price"].shift()).round(4)[consecutive]
    return out.reset_index(drop=True)


def change_stats(p, threshold=THRESHOLD):
    up = p["delta"][p["delta"] >= threshold]
    down = -p["delta"][p["delta"] <= -threshold]
    n = len(p)

    def quantiles(s):
        if s.empty:
            return dict(median=math.nan, p10=math.nan, p90=math.nan)
        return dict(median=float(s.median()), p10=float(s.quantile(0.1)), p90=float(s.quantile(0.9)))

    return dict(pairs=n, changes=len(up) + len(down), ups=len(up), downs=len(down),
                frac_change=(len(up) + len(down)) / n if n else math.nan,
                frac_up=len(up) / n if n else math.nan, frac_down=len(down) / n if n else math.nan,
                size_up=quantiles(up), size_down=quantiles(down))


def _weekly_groups(p, threshold):
    groups = []
    for _, g in p.groupby("week", sort=True):
        d = g["delta"].to_numpy()
        groups.append((d[d >= threshold], -d[d <= -threshold], len(d)))
    return groups


def _asymmetry(groups):
    ups = np.concatenate([g[0] for g in groups]) if groups else np.array([])
    downs = np.concatenate([g[1] for g in groups]) if groups else np.array([])
    if len(ups) == 0 or len(downs) == 0:
        return math.nan
    return float(np.median(ups) - np.median(downs))


def _updown(groups):
    n = sum(g[2] for g in groups)
    return (sum(len(g[0]) for g in groups) - sum(len(g[1]) for g in groups)) / n if n else math.nan


def with_ci(p, statistic, threshold=THRESHOLD, reps=protocol.BOOTSTRAP_REPS):
    groups = _weekly_groups(p, threshold)
    draws = block_bootstrap(groups, statistic, reps=reps)
    return dict(estimate=statistic(groups), ci=percentile_ci(draws), p=bootstrap_pvalue(draws))


def asymmetry(p, threshold=THRESHOLD):
    """Mediana de |Δ| nas altas menos mediana de |Δ| nas quedas (R$/L), sem intervalo."""
    return _asymmetry(_weekly_groups(p, threshold))


def spells(obs, threshold=THRESHOLD):
    """Períodos de preço constante: (produto, sentido da mudança que abriu, duração, evento).

    Começa numa mudança observada; termina na próxima mudança (evento, duração em semanas) ou é
    censurado na última semana observada antes de uma lacuna ou do fim dos dados.
    """
    df = _sorted(obs)
    station, product = df["station_id"].to_numpy(), df["product"].to_numpy()
    week, price = df["week"].to_numpy(), df["price"].to_numpy()
    rows = []
    start = None
    for i in range(len(df)):
        new_series = i == 0 or station[i] != station[i - 1] or product[i] != product[i - 1]
        if new_series or week[i] - week[i - 1] != 1:
            if start is not None:  # lacuna ou nova série: censura no último ponto observado
                rows.append((product[start], direction, int(week[i - 1] - week[start]), False))
            start = None
            continue
        delta = round(price[i] - price[i - 1], 4)
        if abs(delta) >= threshold:
            if start is not None:
                rows.append((product[start], direction, int(week[i] - week[start]), True))
            start, direction = i, 1 if delta > 0 else -1
    if start is not None:
        rows.append((product[start], direction, int(week[len(df) - 1] - week[start]), False))
    return pd.DataFrame(rows, columns=["product", "direction", "duration", "event"])


def analyze(obs, reps=protocol.BOOTSTRAP_REPS):
    check_window(obs["week_start"].unique())
    all_pairs = pairs(obs)
    main_obs = obs[obs["product"] == PRIMARY_PRODUCT]
    main = all_pairs[all_pairs["product"] == PRIMARY_PRODUCT]

    primary = with_ci(main, _asymmetry, reps=reps)
    secondary = {p: with_ci(all_pairs[all_pairs["product"] == p], _asymmetry, reps=reps)
                 for p in SECONDARY_PRODUCTS}
    for p, value in zip(SECONDARY_PRODUCTS, holm([secondary[p]["p"] for p in SECONDARY_PRODUCTS])):
        secondary[p]["p_holm"] = float(value)

    durations = {}
    sp = spells(obs)
    for product, g in sp.groupby("product"):
        durations[product] = dict(spells=len(g), events=int(g["event"].sum()),
                                  median_weeks=kaplan_meier(g["duration"], g["event"])[2])
    main_spells = sp[sp["product"] == PRIMARY_PRODUCT]
    after_up, after_down = main_spells[main_spells["direction"] > 0], main_spells[main_spells["direction"] < 0]
    duration_asymmetry = dict(
        median_after_up=kaplan_meier(after_up["duration"], after_up["event"])[2],
        median_after_down=kaplan_meier(after_down["duration"], after_down["event"])[2],
        p_logrank=logrank(after_up["duration"], after_up["event"], after_down["duration"], after_down["event"]))

    robustness = {
        "limiar_0_05": asymmetry(main, ROBUST_THRESHOLD),
        "sem_preco_extremo": asymmetry(pairs(main_obs[~main_obs["extreme"].astype(bool)])),
    }
    for name, period in zip(("subperiodo_a", "subperiodo_b"), protocol.SUBPERIODS):
        robustness[name] = asymmetry(pairs(in_period(main_obs, period)))

    low, high = primary["ci"]
    excludes_zero = np.isfinite(low) and np.isfinite(high) and (low > 0 or high < 0)
    stable = bool(excludes_zero and same_sign(primary["estimate"], *robustness.values()))
    return dict(primary=primary, secondary=secondary,
                descriptive={p: change_stats(g) for p, g in all_pairs.groupby("product")},
                up_minus_down=with_ci(main, _updown, reps=reps), durations=durations,
                duration_asymmetry=duration_asymmetry, robustness=robustness, stable=stable)
