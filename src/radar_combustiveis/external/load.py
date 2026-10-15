"""Carga das fontes externas no PostgreSQL: atômica por fonte e idempotente.

Upsert pela chave (fonte, produto, nível, local, início do período). Um valor que muda num download
posterior é atualizado e marcado `revised`; `first_retrieved_at` e `available_at` não andam para
frente. Linhas que somem do arquivo mais recente ficam como estavam (a fonte não as apagou de fato).
"""

from datetime import datetime

from .sources import SOURCES, available_at

COLUMNS = ("source_id", "product", "geo_level", "geo", "uf", "period_start", "period_end", "value", "stddev",
           "unit", "available_at", "first_retrieved_at", "retrieved_at", "file_sha256")


def _parse_instant(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def upsert_sources(conn):
    for s in SOURCES.values():
        conn.execute("""
            INSERT INTO external_source (source_id, publisher, title, page_url, license, terms_url, cadence, lag_rule)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id) DO UPDATE SET publisher = EXCLUDED.publisher, title = EXCLUDED.title,
                page_url = EXCLUDED.page_url, license = EXCLUDED.license, terms_url = EXCLUDED.terms_url,
                cadence = EXCLUDED.cadence, lag_rule = EXCLUDED.lag_rule""",
                     (s.source_id, s.publisher, s.title, s.page_url, s.license, s.terms_url, s.cadence, s.lag_rule))


def load_source(conn, source_id, files):
    """Carrega uma fonte. `files`: [(registro do download, linhas lidas dele)]. Devolve as contagens."""
    with conn.transaction():
        upsert_sources(conn)
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS ext_stage (LIKE external_observation INCLUDING DEFAULTS) "
                     "ON COMMIT DELETE ROWS")
        conn.execute("DELETE FROM ext_stage")
        for record, rows in files:
            retrieved, first = _parse_instant(record["retrieved_at"]), _parse_instant(record["first_retrieved_at"])
            conn.execute("""
                INSERT INTO external_file (sha256, source_id, name, url, raw_path, retrieved_at, row_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (sha256) DO NOTHING""",
                         (record["sha256"], source_id, record["name"], record["url"], record["raw_path"],
                          first, len(rows)))
            with conn.cursor().copy(f"COPY ext_stage ({', '.join(COLUMNS)}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row((row["source_id"], row["product"], row["geo_level"], row["geo"], row["uf"],
                                    row["period_start"], row["period_end"], row["value"], row["stddev"], row["unit"],
                                    available_at(source_id, row["period_end"], first.date()), first, retrieved,
                                    record["sha256"]))
        counts = conn.execute("""
            WITH up AS (
                INSERT INTO external_observation AS o (""" + ", ".join(COLUMNS) + """)
                SELECT """ + ", ".join(COLUMNS) + """ FROM ext_stage
                ON CONFLICT (source_id, product, geo_level, geo, period_start) DO UPDATE SET
                    value = EXCLUDED.value, stddev = EXCLUDED.stddev, period_end = EXCLUDED.period_end,
                    unit = EXCLUDED.unit, retrieved_at = EXCLUDED.retrieved_at, file_sha256 = EXCLUDED.file_sha256,
                    revised = o.revised OR o.value <> EXCLUDED.value
                WHERE o.value IS DISTINCT FROM EXCLUDED.value OR o.stddev IS DISTINCT FROM EXCLUDED.stddev
                RETURNING (xmax = 0) AS inserted, o.revised)
            SELECT count(*) FILTER (WHERE inserted) AS inserted,
                   count(*) FILTER (WHERE NOT inserted) AS updated,
                   count(*) FILTER (WHERE revised) AS revised FROM up""").fetchone()
        total = conn.execute("SELECT count(*) FROM external_observation WHERE source_id = %s",
                             (source_id,)).fetchone()[0]
    return {"inserted": counts[0], "updated": counts[1], "revised": counts[2], "total": total}
