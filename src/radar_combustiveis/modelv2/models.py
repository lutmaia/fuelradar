"""Modelos da modelagem v2: taxa-base (L0), logística multinomial e LightGBM (L1 a L3).

Parâmetros fixos do protocolo, sem busca. A logística é implementada aqui (numpy + L-BFGS do
scipy) para não trazer o scikit-learn; um teste a confere contra um caso de resposta conhecida.
"""

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .spec import LGB_CLASS_PARAMS, LGB_ROUNDS, LGB_VALUE_PARAMS, LOGIT_LAMBDA


class BaseRate:
    """Frequência de cada classe por produto e mês do alvo, com suavização de Laplace (+1)."""

    def fit(self, products, months, labels):
        frame = pd.DataFrame({"p": products, "m": months, "y": labels})
        counts = frame.groupby(["p", "m", "y"]).size().unstack(fill_value=0).reindex(columns=[0, 1, 2], fill_value=0)
        self.table = {key: (row.to_numpy() + 1) / (row.sum() + 3) for key, row in counts.iterrows()}
        by_product = frame.groupby(["p", "y"]).size().unstack(fill_value=0).reindex(columns=[0, 1, 2], fill_value=0)
        self.fallback = {p: (row.to_numpy() + 1) / (row.sum() + 3) for p, row in by_product.iterrows()}
        overall = np.bincount(np.asarray(labels, dtype=int), minlength=3) + 1
        self.overall = overall / overall.sum()
        return self

    def predict(self, products, months):
        return np.array([self.table.get((p, m), self.fallback.get(p, self.overall)) for p, m in zip(products, months)])

    def predict_product(self, products):
        """Só por produto, sem o mês: a verificação da referência (protocolo, seção 5)."""
        return np.array([self.fallback.get(p, self.overall) for p in products])


class Logistic:
    """Logística multinomial com penalidade L2 sobre variáveis padronizadas (intercepto livre)."""

    def __init__(self, lam=LOGIT_LAMBDA, products=None):
        self.lam, self.products = lam, products

    def _matrix(self, frame):
        x = frame[self.columns].to_numpy(dtype=float)
        missing = np.isnan(x[:, self.missing_cols]).astype(float)
        x = np.where(np.isnan(x), self.mean, x)
        x = (x - self.mean) / self.scale
        dummies = (frame["product"].to_numpy()[:, None] == np.arange(self.n_products)[None, :]).astype(float)
        return np.hstack([x, missing, dummies[:, 1:]])

    def fit(self, frame, labels):
        self.columns = [c for c in frame.columns if c != "product"]
        self.n_products = int(frame["product"].max()) + 1 if self.products is None else self.products
        raw = frame[self.columns].to_numpy(dtype=float)
        with warnings.catch_warnings():  # coluna toda ausente (ex.: L3 sem fonte externa): média 0, escala 1
            warnings.simplefilter("ignore", RuntimeWarning)
            self.mean = np.nan_to_num(np.nanmean(raw, axis=0))
            std = np.nan_to_num(np.nanstd(raw, axis=0))
        self.scale = np.where(std > 0, std, 1.0)
        self.missing_cols = np.flatnonzero(np.isnan(raw).any(axis=0))
        x = self._matrix(frame)
        y = np.asarray(labels, dtype=int)
        n, d = x.shape
        target = np.zeros((n, 3))
        target[np.arange(n), y] = 1.0

        def objective(theta):
            w, b = theta[: 3 * d].reshape(d, 3), theta[3 * d:]
            z = x @ w + b
            z -= z.max(axis=1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(axis=1, keepdims=True)
            loss = -np.sum(target * np.log(np.clip(p, 1e-15, None))) / n + 0.5 * self.lam * np.sum(w * w) / n
            grad_z = (p - target) / n
            grad_w = x.T @ grad_z + self.lam * w / n
            return loss, np.concatenate([grad_w.ravel(), grad_z.sum(axis=0)])

        result = minimize(objective, np.zeros(3 * d + 3), jac=True, method="L-BFGS-B",
                          options={"maxiter": 1000, "gtol": 1e-7})
        self.w, self.b = result.x[: 3 * d].reshape(d, 3), result.x[3 * d:]
        self.converged = bool(result.success)
        return self

    def predict(self, frame):
        z = self._matrix(frame) @ self.w + self.b
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        return p / p.sum(axis=1, keepdims=True)


class LightGBMClass:
    def fit(self, frame, labels):
        import lightgbm as lgb
        data = lgb.Dataset(frame, label=np.asarray(labels, dtype=int), categorical_feature=["product"],
                           free_raw_data=False)
        self.model = lgb.train(LGB_CLASS_PARAMS, data, num_boost_round=LGB_ROUNDS)
        return self

    def predict(self, frame):
        return self.model.predict(frame, num_threads=1)


class LightGBMValue:
    """Diferença para o último valor, objetivo L1 (como o candidato do Marco 7)."""

    def fit(self, frame, delta):
        import lightgbm as lgb
        data = lgb.Dataset(frame, label=np.asarray(delta, dtype=float), categorical_feature=["product"],
                           free_raw_data=False)
        self.model = lgb.train(LGB_VALUE_PARAMS, data, num_boost_round=LGB_ROUNDS)
        return self

    def predict(self, frame):
        return self.model.predict(frame, num_threads=1)


CLASS_MODELS = {"logistica": Logistic, "lightgbm": LightGBMClass}
