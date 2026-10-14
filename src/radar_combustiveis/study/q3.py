"""Q3 — difusão entre municípios (protocolo, seção 4).

Séries semanais de mediana por município num calendário contínuo de domingos; semanas sem dado
ou com cobertura baixa ficam NaN, e Δ só existe entre semanas consecutivas com dado. Líderes são
os municípios grandes, seguidores os médios.

Entradas: `city` com `municipality`, `product`, `week_start`, `median`, `stations`, `low_coverage`;
`state` com `product`, `week_start`, `median`.
"""

from datetime import timedelta
import math

import numpy as np
import pandas as pd
from scipy import stats

from ..forecasting import protocol
from .common import (ALPHA, PRIMARY_PRODUCT, check_window, holm, kaplan_meier, logrank, size_class)

LAGS = 2
MIN_OBS = 30              # semanas utilizáveis para o teste de precedência de um seguidor
EVENT_THRESHOLD = 0.10
ROBUST_EVENT_THRESHOLDS = (0.05, 0.15)
FALLBACK_EVENT_THRESHOLD = 0.05
MIN_EVENTS = 5
FOLLOW_THRESHOLD = 0.05
FOLLOW_WEEKS = 8
XCORR_LAGS = range(-4, 5)
MIN_FOLLOWER_SHARE = 0.25
SECONDARY_PRODUCT = "ETANOL_HIDRATADO"


def calendar(weeks):
    start, end = min(weeks), max(weeks)
    return [start + timedelta(weeks=i) for i in range((end - start).days // 7 + 1)]


def sizes(city):
    """Porte de cada município pela mediana semanal de postos com gasolina comum."""
    gc = city[city["product"] == PRIMARY_PRODUCT]
    return {m: size_class(v) for m, v in gc.groupby("municipality")["stations"].median().items()}


def wide_medians(city, product, weeks):
    """Matriz semana × município; cobertura baixa vira NaN, como uma semana sem dado."""
    c = city[city["product"] == product]
    values = c["median"].astype(float).where(~c["low_coverage"].astype(bool))
    return (pd.DataFrame({"week_start": c["week_start"], "municipality": c["municipality"], "v": values})
            .pivot(index="week_start", columns="municipality", values="v").reindex(weeks))


def leaders_series(deltas, leaders):
    cols = [m for m in leaders if m in deltas.columns]
    block = deltas[cols]
    return block.mean(axis=1).where(block.notna().sum(axis=1) >= 2)


def precedence(y, x, lags=LAGS, min_obs=MIN_OBS):
    """Teste F de que as defasagens de x não melhoram a previsão de y além das de y (p, n)."""
    frame = pd.DataFrame({"y": y.to_numpy(), "x": x.to_numpy()})
    cols = {"y": frame["y"]}
    for k in range(1, lags + 1):
        cols[f"y{k}"] = frame["y"].shift(k)
        cols[f"x{k}"] = frame["x"].shift(k)
    data = pd.DataFrame(cols).dropna()
    n = len(data)
    k_full = 1 + 2 * lags
    if n < max(min_obs, k_full + 2):
        return math.nan, n
    ones = np.ones((n, 1))
    own = data[[f"y{k}" for k in range(1, lags + 1)]].to_numpy()
    other = data[[f"x{k}" for k in range(1, lags + 1)]].to_numpy()
    target = data["y"].to_numpy()

    def rss(X):
        beta = np.linalg.lstsq(X, target, rcond=None)[0]
        return float(np.sum((target - X @ beta) ** 2))

    restricted, full = rss(np.hstack([ones, own])), rss(np.hstack([ones, own, other]))
    if full <= 0:
        return math.nan, n
    f = ((restricted - full) / lags) / (full / (n - k_full))
    return float(stats.f.sf(f, lags, n - k_full)), n


def precedence_all(deltas, lead, followers):
    """Para cada seguidor: líderes → seguidor e o controle reverso, com Holm em cada sentido."""
    forward, reverse, used = [], [], []
    for m in followers:
        pf, n = precedence(deltas[m], lead)
        pr_, _ = precedence(lead, deltas[m])
        forward.append(pf), reverse.append(pr_), used.append(n)
    fwd, rev = holm(forward), holm(reverse)
    testable = int(np.sum(~np.isnan(fwd)))

    def share(adjusted):
        return float(np.sum(adjusted < ALPHA) / testable) if testable else math.nan

    per = {m: dict(p_forward=forward[i], p_forward_holm=float(fwd[i]), p_reverse=reverse[i],
                   p_reverse_holm=float(rev[i]), weeks_used=used[i]) for i, m in enumerate(followers)}
    return dict(testable=testable, share_forward=share(fwd), share_reverse=share(rev), followers=per)


def state_events(state, product, weeks, threshold):
    s = state[state["product"] == product].set_index("week_start")["median"].astype(float).reindex(weeks)
    d = s.diff().round(4)
    return [(i, 1 if v > 0 else -1) for i, v in enumerate(d.to_numpy()) if np.isfinite(v) and abs(v) >= threshold]


def choose_events(state, product, weeks):
    """Eventos a R$ 0,10; um sentido com menos de 5 eventos passa a R$ 0,05 (declarado)."""
    events = state_events(state, product, weeks, EVENT_THRESHOLD)
    fallback = state_events(state, product, weeks, FALLBACK_EVENT_THRESHOLD)
    chosen, thresholds = [], {}
    for direction in (1, -1):
        mine = [e for e in events if e[1] == direction]
        if len(mine) < MIN_EVENTS:
            mine, thresholds[direction] = [e for e in fallback if e[1] == direction], FALLBACK_EVENT_THRESHOLD
        else:
            thresholds[direction] = EVENT_THRESHOLD
        chosen += mine
    return sorted(chosen), thresholds


def follow_times(medians, events, municipalities):
    """Semanas até cada município acompanhar cada evento: (município, sentido, tempo, acompanhou)."""
    values = medians.to_numpy()
    cols = {m: medians.columns.get_loc(m) for m in municipalities if m in medians.columns}
    event_weeks = {i for i, _ in events}
    last = len(medians) - 1
    rows = []
    for t, direction in events:
        for m, j in cols.items():
            if t == 0 or not np.isfinite(values[t - 1, j]):
                continue
            base = values[t - 1, j]
            outcome = None
            for k in range(FOLLOW_WEEKS):
                i = t + k
                if i > last or (k > 0 and i in event_weeks) or not np.isfinite(values[i, j]):
                    outcome = (k - 1, False)
                    break
                if direction * (values[i, j] - base) >= FOLLOW_THRESHOLD - 1e-9:
                    outcome = (k, True)
                    break
            outcome = outcome or (FOLLOW_WEEKS - 1, False)
            if outcome[0] >= 0:
                rows.append((m, direction, *outcome))
    return pd.DataFrame(rows, columns=["municipality", "direction", "weeks", "followed"])


def diffusion(follow, size_of):
    f = follow.assign(size=follow["municipality"].map(size_of))

    def km(g):
        return dict(cases=len(g), followed=int(g["followed"].sum()),
                    median_weeks=kaplan_meier(g["weeks"], g["followed"])[2] if len(g) else math.nan)

    big, mid = f[f["size"] == "grande"], f[f["size"] == "medio"]
    return dict(grande=km(big), medio=km(mid), alta=km(f[f["direction"] > 0]), queda=km(f[f["direction"] < 0]),
                p_logrank_porte=logrank(big["weeks"], big["followed"], mid["weeks"], mid["followed"]))


def cross_correlation(deltas, lead, followers):
    """Defasagem (−4 a +4; positiva = líderes antes) de maior correlação, por seguidor."""
    out = {}
    for m in followers:
        corr = {lag: deltas[m].corr(lead.shift(lag)) for lag in XCORR_LAGS}
        finite = {k: v for k, v in corr.items() if np.isfinite(v)}
        out[m] = dict(best_lag=max(finite, key=finite.get) if finite else None,
                      correlations={k: float(v) for k, v in corr.items()})
    return out


def precedence_for(city, product, weeks, leaders, followers, period=None):
    # Município sem esse produto vira coluna vazia: fica "não testável", não um erro.
    medians = wide_medians(city, product, weeks)
    medians = medians.reindex(columns=sorted(set(medians.columns) | set(leaders) | set(followers)))
    deltas = medians.diff()
    if period is not None:
        mask = (medians.index >= period[0]) & (medians.index <= period[1])
        deltas = deltas[mask]
    lead = leaders_series(deltas, leaders)
    return precedence_all(deltas, lead, followers), deltas, lead, medians


def analyze(city, state):
    check_window(city["week_start"].unique())
    check_window(state["week_start"].unique())
    weeks = calendar(set(city["week_start"]) | set(state["week_start"]))
    size_of = sizes(city)
    leaders = sorted(m for m, s in size_of.items() if s == "grande")
    followers = sorted(m for m, s in size_of.items() if s == "medio")

    primary, deltas, lead, medians = precedence_for(city, PRIMARY_PRODUCT, weeks, leaders, followers)
    subperiods = {name: precedence_for(city, PRIMARY_PRODUCT, weeks, leaders, followers, period)[0]
                  for name, period in zip(("subperiodo_a", "subperiodo_b"), protocol.SUBPERIODS)}

    events, thresholds = choose_events(state, PRIMARY_PRODUCT, weeks)
    included = leaders + followers
    follow = diffusion(follow_times(medians, events, included), size_of)
    robust_follow = {}
    for threshold in ROBUST_EVENT_THRESHOLDS:
        ev = state_events(state, PRIMARY_PRODUCT, weeks, threshold)
        robust_follow[f"evento_{threshold:.2f}"] = dict(events=len(ev), **diffusion(
            follow_times(medians, ev, included), size_of))

    def forward_beats_reverse(r):
        return np.isfinite(r["share_forward"]) and r["share_forward"] > r["share_reverse"]

    stable = bool(np.isfinite(primary["share_forward"]) and primary["share_forward"] >= MIN_FOLLOWER_SHARE
                  and forward_beats_reverse(primary) and all(forward_beats_reverse(r) for r in subperiods.values()))
    ethanol = precedence_for(city, SECONDARY_PRODUCT, weeks, leaders, followers)[0]
    return dict(leaders=leaders, followers=followers, primary=primary, subperiods=subperiods,
                events=dict(count=len(events), up=sum(1 for e in events if e[1] > 0),
                            down=sum(1 for e in events if e[1] < 0),
                            threshold_up=thresholds[1], threshold_down=thresholds[-1]),
                diffusion=follow, diffusion_robustness=robust_follow,
                cross_correlation=cross_correlation(deltas, lead, followers),
                ethanol=dict(testable=ethanol["testable"], share_forward=ethanol["share_forward"],
                             share_reverse=ethanol["share_reverse"]),
                stable=stable)
