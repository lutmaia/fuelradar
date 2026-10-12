"""Orquestração do Marco 7: backtest, decisão, previsões do modelo publicado e variações incomuns.

`compute` é puro (sem banco): recebe as linhas semanais e devolve tudo o que será gravado e
relatado. A gravação fica em `store.py`.
"""

from datetime import date, timedelta

import numpy as np

from . import evaluate as ev
from .models import BASELINES, CANDIDATE, HORIZONS, LGB_PARAMS, LGB_ROUNDS, FeatureStore, baseline_forecast, \
    candidate_forecast, train_candidate
from .panel import STATE, build_panel, data_hash, eligibility

ANOMALY_WEEKS = 12          # quantas semanas recentes são varridas em busca de variações incomuns
MIN_ANOMALY_ABS = 0.15      # mudança mínima relevante, em R$/litro (seção 14.10)
MIN_ANOMALY_STATIONS = 3    # amostra mínima na semana observada


def _published_forecasts(panel, features, published, model, points, origin):
    """Previsões de 1 a 4 semanas à frente para as séries elegíveis, com o intervalo calibrado."""
    table = ev._pool_quantiles(points, [published], ev.LOWER_Q, ev.UPPER_Q)  # todos os resíduos do backtest
    forecasts, status = [], []
    for s, (location, product) in enumerate(panel.keys):
        ok, reasons = eligibility(panel, s, origin)
        history = int((~np.isnan(panel.y[s, : origin + 1])).sum())
        level = "estado" if location == STATE else "municipio"
        rows = []
        if ok:
            for h in HORIZONS:
                bounds = ev._lookup(table, published, level, product, h)
                if published == CANDIDATE:
                    central = float(candidate_forecast(model, features, [s], origin, h)[0])
                else:
                    central = float(baseline_forecast(panel, published, h)[s, origin])
                if bounds is None or not np.isfinite(central):
                    reasons = reasons + ["sem_residuos_suficientes_para_o_intervalo"]
                    rows = []
                    break
                rows.append({"location": location, "product": product, "horizon": h,
                             "target_week": panel.weeks[origin] + timedelta(weeks=h), "point": central,
                             "lower": central + bounds[0], "upper": central + bounds[1],
                             "history_weeks": history, "stations": panel.stations[s, origin]})
        forecasts += rows
        status.append({"location": location, "product": product, "eligible": bool(rows), "reasons": reasons,
                       "history_weeks": history, "last_week": panel.weeks[origin]})
    return forecasts, status


def _anomalies(panel, best, points, weeks=ANOMALY_WEEKS):
    """Semanas em que o valor observado ficou fora do intervalo de 99% do baseline de 1 semana."""
    table = ev._pool_quantiles(points, [best], ev.ANOMALY_LOWER_Q, ev.ANOMALY_UPPER_Q)
    one_step = baseline_forecast(panel, best, 1)
    found = []
    for j in range(max(1, panel.last - weeks + 1), panel.last + 1):
        i = j - 1
        for s, (location, product) in enumerate(panel.keys):
            observed, expected = panel.y[s, j], one_step[s, i]
            if np.isnan(observed) or np.isnan(expected) or panel.low[s, j]:
                continue
            if location != STATE and not panel.stations[s, j] >= MIN_ANOMALY_STATIONS:
                continue
            if not eligibility(panel, s, i)[0]:
                continue
            level = "estado" if location == STATE else "municipio"
            bounds = ev._lookup(table, best, level, product, 1, ev.ANOMALY_MIN_POOL)
            if bounds is None:
                continue
            lower, upper = expected + bounds[0], expected + bounds[1]
            residual = observed - expected
            if (observed < lower or observed > upper) and abs(residual) >= MIN_ANOMALY_ABS:
                found.append({"location": location, "product": product, "week_start": panel.weeks[j],
                              "observed": float(observed), "expected": float(expected), "lower": float(lower),
                              "upper": float(upper), "residual": float(residual),
                              "direction": "acima" if residual > 0 else "abaixo",
                              "stations": int(panel.stations[s, j])})
    return found


def _reproducible(features, panel, origin):
    """Treina o candidato duas vezes com os mesmos dados; as previsões precisam ser idênticas."""
    first, second = train_candidate(features, origin), train_candidate(features, origin)
    if first is None or second is None:
        return False
    series = np.arange(len(panel.keys))
    # Séries sem dado na origem dão NaN nos dois lados; NaN deve contar como igual.
    return all(np.array_equal(candidate_forecast(first, features, series, origin, h),
                              candidate_forecast(second, features, series, origin, h), equal_nan=True)
               for h in HORIZONS)


def compute(rows, code_sha=None, step=ev.STEP, burn_in=ev.BURN_IN, min_origin=ev.MIN_ORIGIN, progress=None):
    panel = build_panel(rows)
    features = FeatureStore(panel)
    origin = panel.last
    origins = ev.origins_for(panel, step, min_origin)
    points = ev.add_intervals(ev.collect_points(panel, features, origins, progress=progress))
    summary, _ = ev.summarize(points, burn_in=burn_in)
    reproducible = _reproducible(features, panel, origin)
    decision = ev.decide(summary, reproducible)
    published = CANDIDATE if decision["approved"] else decision["best_baseline"]
    model = train_candidate(features, origin) if published == CANDIDATE else None
    forecasts, status = _published_forecasts(panel, features, published, model, points, origin)
    anomalies = _anomalies(panel, decision["best_baseline"], points)
    weeks = [panel.weeks[o] for o in origins]
    return {
        "uf_rows": len(rows), "data_hash": data_hash(rows), "code_sha": code_sha,
        "origin_week": panel.weeks[origin], "first_week": panel.weeks[0],
        "series": len(panel.keys), "backtest_origins": weeks, "step": step, "burn_in": burn_in,
        "summary": summary, "decision": decision, "published_model": published,
        "reproducible": reproducible, "forecasts": forecasts, "eligibility": status, "anomalies": anomalies,
        "parameters": {"candidate": {"params": LGB_PARAMS, "rounds": LGB_ROUNDS}, "baselines": list(BASELINES),
                       "horizons": list(HORIZONS), "interval": [ev.LOWER_Q, ev.UPPER_Q],
                       "anomaly_interval": [ev.ANOMALY_LOWER_Q, ev.ANOMALY_UPPER_Q],
                       "min_anomaly_abs": MIN_ANOMALY_ABS},
        "generated_on": date.today(),
    }
