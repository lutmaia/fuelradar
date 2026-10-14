"""Marco 8b — análises descritivas para o consumidor (docs/estudo/descritivo.md).

Não testam hipóteses: medem e descrevem, na mesma janela do estudo (o teste final continua
lacrado). Funções puras sobre os mesmos DataFrames de Q1 a Q3.
"""

import math

import numpy as np
import pandas as pd

from ..regions import CAPITAL, COAST, METRO, REGIONS, region_of  # noqa: F401  (listas movidas, sem mudança)
from .common import PRIMARY_PRODUCT, check_window
from .q2 import pairs

ETHANOL = "ETANOL_HIDRATADO"
ETHANOL_PAYS = 0.70          # regra prática: etanol compensa até 70% do preço da gasolina
MIN_PAIRED_WEEKS = 26        # semanas com os dois preços para ranquear um município
MIN_STATIONS = 5             # postos na semana para medir a economia dentro do município
TANK_LITERS = 50
REGION_PRODUCTS = (PRIMARY_PRODUCT, ETHANOL, "DIESEL_S10")
# Capital, metropolitana, litoral e interior: definições em `radar_combustiveis/regions.py`, que o
# painel também usa (a lista é a mesma do estudo).


def _year_shares(frame, flag):
    years = pd.to_datetime(frame["week_start"]).dt.year
    return {int(y): dict(share=float(g[flag].mean()), n=int(len(g))) for y, g in frame.groupby(years)}


# -- Etanol × gasolina ------------------------------------------------------------------------


def ethanol_vs_gasoline(city, state):
    """Razão etanol/gasolina das medianas semanais; compensa quando ≤ 70%. Cobertura baixa não entra."""
    check_window(city["week_start"].unique())
    check_window(state["week_start"].unique())
    ok = city[~city["low_coverage"].astype(bool) & city["product"].isin((PRIMARY_PRODUCT, ETHANOL))]
    wide = ok.pivot_table(index=["municipality", "week_start"], columns="product", values="median").dropna()
    wide = wide.reset_index()
    wide["ratio"] = wide[ETHANOL] / wide[PRIMARY_PRODUCT]
    wide["pays"] = wide["ratio"] <= ETHANOL_PAYS + 1e-12

    st = state.pivot_table(index="week_start", columns="product", values="median").dropna(
        subset=[PRIMARY_PRODUCT, ETHANOL]).reset_index()
    st["ratio"] = st[ETHANOL] / st[PRIMARY_PRODUCT]
    st["pays"] = st["ratio"] <= ETHANOL_PAYS + 1e-12

    per_city = (wide.groupby("municipality")
                .agg(weeks=("ratio", "size"), share=("pays", "mean"), median_ratio=("ratio", "median")))
    ranked = per_city[per_city["weeks"] >= MIN_PAIRED_WEEKS].sort_values(["share", "median_ratio"],
                                                                        ascending=[False, True])
    last = wide["week_start"].max()
    latest = wide[wide["week_start"] == last]
    lo, hi = st.loc[st["ratio"].idxmin()], st.loc[st["ratio"].idxmax()]
    return dict(
        city_weeks=int(len(wide)), share_city_weeks=float(wide["pays"].mean()), by_year=_year_shares(wide, "pays"),
        state=dict(weeks=int(len(st)), share=float(st["pays"].mean()), median_ratio=float(st["ratio"].median()),
                   min=dict(ratio=float(lo["ratio"]), week=lo["week_start"]),
                   max=dict(ratio=float(hi["ratio"]), week=hi["week_start"]),
                   series=[dict(week=w, ratio=float(r)) for w, r in zip(st["week_start"], st["ratio"])]),
        ranked_cities=int(len(ranked)),
        most=[dict(municipality=m, **{k: float(v) if k != "weeks" else int(v) for k, v in row.items()})
              for m, row in ranked.head(10).iterrows()],
        least=[dict(municipality=m, **{k: float(v) if k != "weeks" else int(v) for k, v in row.items()})
               for m, row in ranked.tail(10).iloc[::-1].iterrows()],
        latest=dict(week=last, cities=int(len(latest)), paying=int(latest["pays"].sum())))


# -- Quanto se economiza escolhendo o posto -----------------------------------------------------


def _quantiles(s):
    return dict(p25=float(s.quantile(0.25)), median=float(s.median()), p75=float(s.quantile(0.75)))


def station_choice(obs, sizes=None, product=PRIMARY_PRODUCT, exclude_extreme=True):
    """Mediana menos o menor preço da semana no município (semanas com ≥ 5 postos), e a faixa P25–P75."""
    check_window(obs["week_start"].unique())
    o = obs[obs["product"] == product]
    if exclude_extreme:
        o = o[~o["extreme"].astype(bool)]
    g = o.groupby(["municipality", "week_start"])["price"]
    cells = pd.DataFrame(dict(stations=g.size(), low=g.min(), median=g.median(),
                              p25=g.quantile(0.25), p75=g.quantile(0.75))).reset_index()
    cells = cells[cells["stations"] >= MIN_STATIONS]
    cells["saving"] = cells["median"] - cells["low"]
    cells["spread"] = cells["p75"] - cells["p25"]
    out = dict(city_weeks=int(len(cells)), saving=_quantiles(cells["saving"]), spread=_quantiles(cells["spread"]),
               saving_tank=float(cells["saving"].median() * TANK_LITERS),
               saving_pct=float((cells["saving"] / cells["median"]).median() * 100))
    if sizes:
        cells["size"] = cells["municipality"].map(sizes)
        out["by_size"] = {s: dict(city_weeks=int(len(g)), saving=float(g["saving"].median()))
                          for s, g in cells.groupby("size")}
    per_city = cells.groupby("municipality").agg(weeks=("saving", "size"), saving=("saving", "median"))
    ranked = per_city[per_city["weeks"] >= MIN_PAIRED_WEEKS].sort_values("saving", ascending=False)
    out["most"] = [dict(municipality=m, weeks=int(r["weeks"]), saving=float(r["saving"]))
                   for m, r in ranked.head(10).iterrows()]
    # Referência temporal: tamanho típico de uma mudança de preço no mesmo posto (Q2, |Δ| ≥ R$ 0,01).
    d = pairs(o)["delta"].abs()
    out["typical_change"] = float(d[d >= 0.01].median()) if (d >= 0.01).any() else math.nan
    return out


# -- Capital × metropolitana × litoral × interior ----------------------------------------------


def regions(obs):
    """Mediana semanal dos preços de cada região e a diferença para a capital, por produto."""
    check_window(obs["week_start"].unique())
    o = obs[obs["product"].isin(REGION_PRODUCTS)].assign(region=lambda d: d["municipality"].map(region_of))
    weekly = o.groupby(["product", "region", "week_start"])["price"].median().unstack("region")
    out = dict(municipalities={r: sorted(set(o.loc[o["region"] == r, "municipality"])) for r in REGIONS},
               products={})
    for product in REGION_PRODUCTS:
        if product not in weekly.index.get_level_values(0):
            continue
        w = weekly.loc[product]
        res = {}
        for r in REGIONS:
            if r == "capital" or r not in w.columns or "capital" not in w.columns:
                continue
            diff = (w[r] - w["capital"]).dropna()
            if diff.empty:
                continue
            years = pd.to_datetime(pd.Series(diff.index)).dt.year.to_numpy()
            res[r] = dict(weeks=int(len(diff)), median_diff=float(diff.median()), mean_diff=float(diff.mean()),
                          share_cheaper=float((diff < 0).mean()),
                          by_year={int(y): float(np.median(diff.to_numpy()[years == y])) for y in np.unique(years)})
        out["products"][product] = res
    return out


def analyze(obs, city, state, sizes=None):
    return dict(ethanol=ethanol_vs_gasoline(city, state),
                station_choice=station_choice(obs, sizes),
                station_choice_with_extremes=station_choice(obs, sizes, exclude_extreme=False),
                regions=regions(obs))
