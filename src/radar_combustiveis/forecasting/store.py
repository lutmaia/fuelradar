"""Gravação das versões de modelo, previsões, elegibilidade e variações incomuns (migração 0004)."""

import json

from . import evaluate as ev
from .models import CANDIDATE
from .panel import STATE


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def version_of(result):
    return f"{result['origin_week'].isoformat()}-{result['data_hash'][:8]}"


def model_metrics(result, name):
    summary = result["summary"]
    best = result["decision"]["best_baseline"]
    return {
        "overall": summary["overall"][name],
        "by_horizon": {k: v[name] for k, v in summary["by_horizon"].items()},
        "by_product": {k: v[name] for k, v in summary["by_product"].items()},
        "by_level": {k: v[name] for k, v in summary["by_level"].items()},
        "evaluated_points": summary["points"],
        "evaluated_origins": len(summary["evaluated_origins"]),
        "decision": result["decision"],
        "reference": {"best_baseline": best, "best_baseline_overall": summary["overall"][best],
                      "candidate_overall": summary["overall"][CANDIDATE]},
    }


def publish(conn, result, uf="SP"):
    """Grava tudo em uma transação. Reexecutar com os mesmos dados substitui os registros da versão."""
    version, published = version_of(result), result["published_model"]
    models = [(name, "baseline") for name in result["parameters"]["baselines"]] + [(CANDIDATE, "candidate")]
    ids = {}
    with conn.transaction():
        conn.execute("UPDATE model_version SET is_published = false, status = 'archived' "
                     "WHERE is_published AND NOT (version = %s AND name = %s)", (version, published))
        for name, kind in models:
            is_published = name == published
            status = "approved" if is_published else "rejected" if kind == "candidate" else "archived"
            row = conn.execute("""
                INSERT INTO model_version (name, version, kind, status, is_published, uf, origin_week, code_sha,
                                           data_hash, parameters, metrics)
                VALUES (%(name)s, %(version)s, %(kind)s, %(status)s, %(published)s, %(uf)s, %(origin)s, %(sha)s,
                        %(hash)s, %(params)s::jsonb, %(metrics)s::jsonb)
                ON CONFLICT (name, version) DO UPDATE SET status = excluded.status,
                    is_published = excluded.is_published, code_sha = excluded.code_sha,
                    parameters = excluded.parameters, metrics = excluded.metrics, created_at = now()
                RETURNING model_version_id""", {
                "name": name, "version": version, "kind": kind, "status": status, "published": is_published,
                "uf": uf, "origin": result["origin_week"], "sha": result["code_sha"], "hash": result["data_hash"],
                "params": _json(result["parameters"] if kind == "candidate" else {"baseline": name}),
                "metrics": _json(model_metrics(result, name))}).fetchone()
            ids[name] = row[0]
        model_id = ids[published]
        for table in ("forecast", "forecast_eligibility", "anomaly"):
            conn.execute(f"DELETE FROM {table} WHERE model_version_id = %s", (model_id,))  # tabela fixa, sem entrada externa

        locations = dict(conn.execute(
            "SELECT municipality_name_normalized, location_id FROM dim_location WHERE uf = %s", (uf,)).fetchall())
        products = dict(conn.execute("SELECT canonical_name, product_id FROM dim_product").fetchall())

        def place(location):
            return None if location == STATE else locations[location]

        generated = result["generated_on"]
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO forecast (model_version_id, uf, location_id, product_id, origin_week, target_week, horizon,
                                      point, lower, upper, interval_level, history_weeks, station_count, generated_on)
                VALUES (%s, %s, %s, %s, %s, %s, %s, round(%s::numeric, 4), round(%s::numeric, 4),
                        round(%s::numeric, 4), %s, %s, %s, %s)""",
                [(model_id, uf, place(f["location"]), products[f["product"]], result["origin_week"],
                  f["target_week"], f["horizon"], f["point"], f["lower"], f["upper"], ev.INTERVAL_LEVEL,
                  f["history_weeks"], None if f["stations"] != f["stations"] else int(f["stations"]), generated)
                 for f in result["forecasts"]])
            cur.executemany("""
                INSERT INTO forecast_eligibility (model_version_id, uf, location_id, product_id, eligible, reasons,
                                                  history_weeks, last_week)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [(model_id, uf, place(e["location"]), products[e["product"]], e["eligible"], e["reasons"],
                  e["history_weeks"], e["last_week"]) for e in result["eligibility"]])
            cur.executemany("""
                INSERT INTO anomaly (model_version_id, uf, location_id, product_id, week_start, observed, expected,
                                     lower, upper, residual, direction, station_count, interval_level)
                VALUES (%s, %s, %s, %s, %s, round(%s::numeric, 4), round(%s::numeric, 4), round(%s::numeric, 4),
                        round(%s::numeric, 4), round(%s::numeric, 4), %s, %s, %s)""",
                [(model_id, uf, place(a["location"]), products[a["product"]], a["week_start"], a["observed"],
                  a["expected"], a["lower"], a["upper"], a["residual"], a["direction"], a["stations"],
                  ev.ANOMALY_UPPER_Q - ev.ANOMALY_LOWER_Q) for a in result["anomalies"]])
    return {"model_version_id": model_id, "version": version, "published": published,
            "forecasts": len(result["forecasts"]), "anomalies": len(result["anomalies"])}
