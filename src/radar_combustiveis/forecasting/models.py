"""Baselines obrigatórios e candidato LightGBM global (arquitetura, seções 14.3 e 14.4).

Toda previsão é "feita na semana de origem `i`": só usa dados de `0..i`. O alvo é a mediana
da semana `i + h`. O candidato prevê a *diferença* para o último valor observado e soma de volta.
"""

import numpy as np
import pandas as pd

HORIZONS = (1, 2, 3, 4)
BASELINES = ("ultimo_valor", "media_movel_4", "mesma_semana_ano_anterior")
CANDIDATE = "lightgbm_global"
SEASON = 52

LAGS = (1, 2, 4, 8, 13, 26, 52)
WINDOWS = (4, 8, 13)

# Parâmetros fixos antes de ver o resultado do backtest: não há busca de hiperparâmetros, que
# faria a avaliação ficar otimista. L1 porque a métrica principal é o MAE.
LGB_PARAMS = {
    "objective": "l1", "learning_rate": 0.05, "num_leaves": 31, "min_data_in_leaf": 40,
    "bagging_fraction": 0.8, "bagging_freq": 1, "feature_fraction": 0.8, "seed": 7,
    "num_threads": 1, "deterministic": True, "force_row_wise": True, "verbose": -1,
}
LGB_ROUNDS = 300


def baseline_forecast(panel, name, h):
    """Matriz (séries, semanas) com a previsão de `y[i + h]` feita na origem `i` (NaN se não existe)."""
    y = panel.y
    if name == "ultimo_valor":
        return y.copy()
    if name == "media_movel_4":
        out = np.full(y.shape, np.nan)
        for i in range(3, y.shape[1]):
            block = y[:, i - 3: i + 1]
            count = (~np.isnan(block)).sum(axis=1)
            with np.errstate(all="ignore"):
                mean = np.nanmean(block, axis=1)
            out[:, i] = np.where(count >= 3, mean, np.nan)  # exige 3 das 4 semanas
        return out
    if name == "mesma_semana_ano_anterior":
        out = np.full(y.shape, np.nan)
        for i in range(y.shape[1]):
            j = i + h - SEASON
            if 0 <= j <= i:
                out[:, i] = y[:, j]
        return out
    raise ValueError(f"baseline desconhecido: {name}")


def _series_features(values, stations, low):
    """Features de uma série para todas as origens (linhas = semanas). Só olham o passado."""
    s = pd.Series(values)
    st = pd.Series(stations)
    cols = {"level": s}
    for lag in LAGS:
        cols[f"d{lag}"] = s.shift(lag) - s
    for w in WINDOWS:
        roll = s.rolling(w, min_periods=2)
        cols[f"mean{w}"] = roll.mean() - s
        cols[f"std{w}"] = s.rolling(w, min_periods=3).std()
    cols["median8"] = s.rolling(8, min_periods=2).median() - s
    cols["stations"] = st
    cols["station_ratio"] = st / st.rolling(8, min_periods=3).median().shift(1)
    cols["low_coverage"] = pd.Series(low.astype(float))
    return pd.DataFrame(cols)


FEATURES = ["level"] + [f"d{lag}" for lag in LAGS] + [f"mean{w}" for w in WINDOWS] + \
           [f"std{w}" for w in WINDOWS] + ["median8", "stations", "station_ratio", "low_coverage"]
MODEL_COLUMNS = FEATURES + ["horizon", "target_week_of_year", "target_month", "product", "location", "is_state"]
CATEGORICAL = ["product", "location"]


class FeatureStore:
    """Features de todas as séries e origens, calculadas uma vez por painel."""

    def __init__(self, panel):
        self.panel = panel
        self.products = sorted({k[1] for k in panel.keys})
        self.locations = sorted({k[0] for k in panel.keys})
        frames = [_series_features(panel.y[s], panel.stations[s], panel.low[s]) for s in range(len(panel.keys))]
        self.matrix = np.stack([f[FEATURES].to_numpy(dtype=float) for f in frames])  # (S, T, F)
        self.product_code = np.array([self.products.index(k[1]) for k in panel.keys])
        self.location_code = np.array([self.locations.index(k[0]) for k in panel.keys])
        self.state_flag = np.array([float(panel.is_state(s)) for s in range(len(panel.keys))])

    def frame(self, series, origins, horizon):
        """DataFrame de modelo para os pares (série, origem) com um horizonte."""
        weeks = [self.panel.weeks[0] + pd.Timedelta(weeks=int(i) + horizon) for i in origins]
        calendar = pd.DatetimeIndex(weeks).isocalendar()
        data = pd.DataFrame(self.matrix[series, origins], columns=FEATURES)
        data["horizon"] = horizon
        data["target_week_of_year"] = calendar["week"].to_numpy().astype(float)
        data["target_month"] = pd.DatetimeIndex(weeks).month.to_numpy().astype(float)
        data["product"] = self.product_code[series]
        data["location"] = self.location_code[series]
        data["is_state"] = self.state_flag[series]
        return data[MODEL_COLUMNS]

    def training_set(self, cutoff):
        """Pares (série, origem, h) cujo alvo já era conhecido na semana `cutoff`."""
        panel, parts, targets = self.panel, [], []
        for h in HORIZONS:
            last_origin = min(cutoff - h, panel.last - h)
            if last_origin < 0:
                continue
            origin_ok = ~np.isnan(panel.y[:, : last_origin + 1])
            target_ok = ~np.isnan(panel.y[:, h: last_origin + 1 + h])
            s_idx, i_idx = np.nonzero(origin_ok & target_ok)
            if s_idx.size == 0:
                continue
            parts.append(self.frame(s_idx, i_idx, h))
            targets.append(panel.y[s_idx, i_idx + h] - panel.y[s_idx, i_idx])
        if not parts:
            return None, None
        return pd.concat(parts, ignore_index=True), np.concatenate(targets)


def train_candidate(features, cutoff):
    import lightgbm as lgb  # dependência pesada: só é importada quando o candidato é treinado

    X, target = features.training_set(cutoff)
    if X is None or len(X) < 500:
        return None
    dataset = lgb.Dataset(X, label=target, categorical_feature=CATEGORICAL, free_raw_data=False)
    return lgb.train(LGB_PARAMS, dataset, num_boost_round=LGB_ROUNDS)


def candidate_forecast(model, features, series, origin, horizon):
    """Previsão de `y[origin + horizon]` para as séries dadas (array alinhado a `series`)."""
    origins = np.full(len(series), origin)
    X = features.frame(np.asarray(series), origins, horizon)
    delta = model.predict(X, num_threads=1)
    return features.panel.y[np.asarray(series), origin] + delta
