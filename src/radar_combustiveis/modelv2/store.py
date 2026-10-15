"""Cópia do registro ao vivo e do placar no banco (a API lê daqui). Nunca altera o que já existe."""

import json

from ..forecasting.panel import STATE
from .report import dumps


def save_forecasts(conn, frame, uf="SP"):
    """Insere as previsões que ainda não estão no banco; devolve quantas entraram."""
    if frame.empty:
        return 0
    products = dict(conn.execute("SELECT canonical_name, product_id FROM dim_product").fetchall())
    places = dict(conn.execute("SELECT municipality_name_normalized, location_id FROM dim_location WHERE uf = %s",
                               (uf,)).fetchall())
    inserted = 0
    with conn.transaction():
        for row in frame.itertuples():
            location = None if row.location == STATE else places.get(row.location)
            if row.location != STATE and location is None:
                continue
            cur = conn.execute("""
                INSERT INTO forecast_class (origin_week, uf, location_id, product_id, horizon, target_week,
                                            p_down, p_flat, p_up, model, temperature)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING""",
                               (row.origin_week, uf, location, products[row.product], int(row.horizon), row.target_week,
                                round(float(row.p0), 6), round(float(row.p1), 6), round(1 - round(float(row.p0), 6)
                                                                                     - round(float(row.p1), 6), 6),
                                row.model, float(row.temperature)))
            inserted += cur.rowcount
    return inserted


def save_scoreboard(conn, board):
    with conn.transaction():
        conn.execute("INSERT INTO live_scoreboard (body) VALUES (%s::jsonb)", (dumps(board),))


def latest_scoreboard(conn):
    row = conn.execute("SELECT computed_at, body FROM live_scoreboard ORDER BY computed_at DESC LIMIT 1").fetchone()
    return None if row is None else {"computed_at": row[0], **(row[1] if isinstance(row[1], dict) else json.loads(row[1]))}
