"""Q1 — bandeira branca (protocolo, seção 2).

Regressão do log do preço numa indicadora de bandeira branca, com efeito fixo de mercado
(município × semana, um produto por vez) absorvido pela transformação *within*. Células sem os
dois tipos de posto não identificam nada e saem antes do ajuste. Erro-padrão agrupado por posto.

Entrada: um DataFrame de observações com `station_id`, `municipality`, `product`, `week_start`
(date), `price` (R$), `brand` (como no cadastro), `postal_code` e `extreme` (aviso `preco_extremo`).
"""

import math

import numpy as np
import pandas as pd
from scipy import stats

from ..forecasting import protocol
from .common import (PRIMARY_PRODUCT, SECONDARY_PRODUCTS, WHITE, check_window, holm, in_period,
                     normalize_brand, same_sign)

MARKET = ("municipality", "week_start")
NEIGHBORHOOD = ("cep5", "week_start")
BIG_BRANDS = ("IPIRANGA", "RAIZEN", "VIBRA")


def prepare(obs):
    check_window(obs["week_start"].unique())
    df = obs.copy()
    df["brand"] = df["brand"].map(normalize_brand)
    df["white"] = (df["brand"] == WHITE).astype(float)
    df["log_price"] = np.log(df["price"].astype(float))
    digits = df["postal_code"].fillna("").astype(str).str.replace(r"\D", "", regex=True)
    df["cep5"] = digits.str[:5].where(digits.str.len() >= 5)
    return df


def within_fit(df, y, xcols, fe, cluster="station_id"):
    """MQO com um efeito fixo de alta dimensão e erro-padrão agrupado (correção de pequena amostra
    G/(G−1)·(N−1)/(N−K), com K contando os efeitos fixos). Devolve um dicionário por regressor."""
    d = df.dropna(subset=list(fe))
    empty = {x: dict(beta=math.nan, se=math.nan, p=math.nan, ci=(math.nan, math.nan)) for x in xcols}
    if d.empty:
        return empty, dict(n_obs=0, n_cells=0, n_clusters=0)
    cells = d.groupby(list(fe), sort=False).ngroup().to_numpy()
    X = d[list(xcols)].to_numpy(float)
    by_cell = pd.DataFrame(X).groupby(cells)
    varies = ((by_cell.transform("max") - by_cell.transform("min")).abs().sum(axis=1) > 0).to_numpy()
    d, X, cells = d[varies], X[varies], cells[varies]
    if len(d) == 0:
        return empty, dict(n_obs=0, n_cells=0, n_clusters=0)
    cells = pd.factorize(cells)[0]
    yv = d[y].to_numpy(float)
    Xd = X - pd.DataFrame(X).groupby(cells).transform("mean").to_numpy()
    yd = yv - pd.Series(yv).groupby(cells).transform("mean").to_numpy()
    bread = Xd.T @ Xd
    beta = np.linalg.solve(bread, Xd.T @ yd)
    resid = yd - Xd @ beta
    clusters = pd.factorize(d[cluster].to_numpy())[0]
    scores = pd.DataFrame(Xd * resid[:, None]).groupby(clusters).sum().to_numpy()
    n, k, n_cells, g = len(yd), X.shape[1], cells.max() + 1, clusters.max() + 1
    dof = n - k - n_cells
    if g < 2 or dof <= 0:
        return empty, dict(n_obs=n, n_cells=int(n_cells), n_clusters=int(g))
    inv = np.linalg.inv(bread)
    cov = g / (g - 1) * (n - 1) / dof * inv @ (scores.T @ scores) @ inv
    se = np.sqrt(np.diag(cov))
    crit = stats.t.ppf(0.975, g - 1)
    out = {}
    for i, x in enumerate(xcols):
        p = float(2 * stats.t.sf(abs(beta[i] / se[i]), g - 1)) if se[i] > 0 else math.nan
        out[x] = dict(beta=float(beta[i]), se=float(se[i]), p=p,
                      ci=(float(beta[i] - crit * se[i]), float(beta[i] + crit * se[i])))
    return out, dict(n_obs=int(n), n_cells=int(n_cells), n_clusters=int(g))


def pct(log_diff):
    return 100 * (math.exp(log_diff) - 1) if np.isfinite(log_diff) else math.nan


def white_gap(df, fe=MARKET):
    """Diferença percentual da bandeira branca contra os bandeirados, com IC de 95%."""
    fit, sizes = within_fit(df, "log_price", ["white"], fe)
    r = fit["white"]
    return dict(beta=r["beta"], se=r["se"], p=r["p"], pct=pct(r["beta"]),
                pct_ci=(pct(r["ci"][0]), pct(r["ci"][1])), **sizes)


def brand_gaps(df):
    """Cada uma das três maiores bandeiras contra a branca (referência), em % e com Holm."""
    sub = df[df["brand"].isin((WHITE,) + BIG_BRANDS)].copy()
    cols = []
    for b in BIG_BRANDS:
        sub[b] = (sub["brand"] == b).astype(float)
        cols.append(b)
    fit, sizes = within_fit(sub, "log_price", cols, MARKET)
    adjusted = holm([fit[b]["p"] for b in BIG_BRANDS])
    return {b: dict(pct=pct(fit[b]["beta"]), pct_ci=(pct(fit[b]["ci"][0]), pct(fit[b]["ci"][1])),
                    p=fit[b]["p"], p_holm=float(adjusted[i]), **sizes)
            for i, b in enumerate(BIG_BRANDS)}


def analyze(obs):
    df = prepare(obs)
    main = df[df["product"] == PRIMARY_PRODUCT]
    primary = white_gap(main)

    secondary = {p: white_gap(df[df["product"] == p]) for p in SECONDARY_PRODUCTS}
    for p, value in zip(SECONDARY_PRODUCTS, holm([secondary[p]["p"] for p in SECONDARY_PRODUCTS])):
        secondary[p]["p_holm"] = float(value)

    robustness = {
        "vizinhanca_cep5": white_gap(main, fe=NEIGHBORHOOD),
        "sem_preco_extremo": white_gap(main[~main["extreme"].astype(bool)]),
    }
    for name, period in zip(("subperiodo_a", "subperiodo_b"), protocol.SUBPERIODS):
        robustness[name] = white_gap(in_period(main, period))

    low, high = primary["pct_ci"]
    excludes_zero = np.isfinite(low) and np.isfinite(high) and (low > 0 or high < 0)
    stable = bool(excludes_zero and same_sign(primary["beta"], *(r["beta"] for r in robustness.values())))
    return dict(primary=primary, secondary=secondary, brands=brand_gaps(main), robustness=robustness,
                stable=stable)
