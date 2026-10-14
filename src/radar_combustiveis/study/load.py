"""Leitura do PostgreSQL para o estudo, já recortada na janela do protocolo.

O recorte acontece no SQL (`week_start` entre STUDY_START e STUDY_END) e é conferido de novo na
saída com `assert_no_holdout`: um erro de consulta não pode deixar passar o teste final.
"""

import hashlib

import pandas as pd

from ..forecasting import protocol

OBSERVATIONS = """
    SELECT f.row_key, f.station_id, l.municipality_name_normalized AS municipality, p.canonical_name AS product,
           f.week_start, f.sale_price::float8 AS price, s.brand, s.postal_code,
           'preco_extremo' = ANY (f.quality_flags) AS extreme
    FROM fact_price_observation f
    JOIN dim_station s USING (station_id)
    JOIN dim_location l ON l.location_id = f.location_id
    JOIN dim_product p USING (product_id)
    WHERE f.is_current_source_revision AND l.uf = %(uf)s AND p.active AND p.category = 'automotivo'
      AND f.week_start BETWEEN %(start)s AND %(end)s"""

CITY = """
    SELECT l.municipality_name_normalized AS municipality, p.canonical_name AS product, m.week_start,
           m.price_median::float8 AS median, m.station_count AS stations,
           coalesce(m.quality_flag = 'cobertura_baixa', false) AS low_coverage
    FROM mart_weekly_city_price m
    JOIN dim_location l USING (location_id) JOIN dim_product p USING (product_id)
    WHERE l.uf = %(uf)s AND p.active AND p.category = 'automotivo'
      AND m.price_median IS NOT NULL AND m.week_start BETWEEN %(start)s AND %(end)s"""

STATE = """
    SELECT p.canonical_name AS product, m.week_start, m.price_median::float8 AS median
    FROM mart_weekly_state_price m JOIN dim_product p USING (product_id)
    WHERE m.uf = %(uf)s AND p.active AND p.category = 'automotivo'
      AND m.week_start BETWEEN %(start)s AND %(end)s"""


def _frame(conn, sql, uf):
    cur = conn.execute(sql, dict(uf=uf, start=protocol.STUDY_START, end=protocol.STUDY_END))
    frame = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    protocol.assert_no_holdout(frame["week_start"].unique())
    return frame


def frame_hash(frame, key):
    """SHA-256 das linhas em ordem canônica, com todas as colunas: identifica os dados usados."""
    ordered = frame.sort_values(key, kind="stable")
    digest = hashlib.sha256()
    for row in ordered.itertuples(index=False):
        digest.update(("|".join("" if v is None else str(v) for v in row) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _ordered(frame, key):
    # O PostgreSQL não garante a ordem das linhas; outra ordem muda a ordem das somas e o último
    # dígito dos resultados. Ordenar torna duas execuções idênticas byte a byte.
    return frame.sort_values(key, kind="stable").reset_index(drop=True)


def load(conn, uf="SP"):
    obs = _ordered(_frame(conn, OBSERVATIONS, uf), ["row_key"])
    city = _ordered(_frame(conn, CITY, uf), ["municipality", "product", "week_start"])
    state = _ordered(_frame(conn, STATE, uf), ["product", "week_start"])
    hashes = dict(observations=frame_hash(obs, ["row_key"]),
                  city=frame_hash(city, ["municipality", "product", "week_start"]),
                  state=frame_hash(state, ["product", "week_start"]))
    combined = hashlib.sha256("".join(hashes[k] for k in sorted(hashes)).encode()).hexdigest()
    return obs, city, state, dict(hashes, combined=combined)
