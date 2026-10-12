"""Consultas de leitura da API: SQL explícito, sempre parametrizado (nunca montado por texto).

Cada função recebe uma conexão com `row_factory=dict_row`, aberta somente leitura. Só as agregações
semanais (`mart_*`) alimentam preços; o fato é usado para atualidade e para os postos. Ver ADR 0004.
"""

from ..ingestion.normalize import normalize_text

# -- Cadastros ------------------------------------------------------------------------------


def published_products(conn):
    return conn.execute("""
        SELECT product_id, canonical_name, category, unit
        FROM dim_product WHERE active AND category = 'automotivo' ORDER BY canonical_name""").fetchall()


def find_product(conn, code):
    return conn.execute("""
        SELECT product_id, canonical_name, category, unit FROM dim_product
        WHERE active AND category = 'automotivo' AND canonical_name = %s""", (code,)).fetchone()


def find_locations(conn, uf, names):
    """Municípios pelo nome normalizado (sem acento, caixa alta), como o carregador os guarda."""
    keys = sorted({normalize_text(name) for name in names})
    return conn.execute("""
        SELECT location_id, uf, municipality_name, municipality_name_normalized
        FROM dim_location WHERE uf = %s AND municipality_name_normalized = ANY(%s)""", (uf, keys)).fetchall()


def list_locations(conn, uf, search, limit, offset):
    return conn.execute("""
        SELECT l.uf, l.municipality_name, count(DISTINCT m.product_id) AS products,
               min(m.week_start) AS first_week_start, max(m.week_start) AS last_week_start,
               count(*) OVER () AS total
        FROM dim_location l JOIN mart_weekly_city_price m USING (location_id)
        WHERE l.uf = %(uf)s
          AND (%(search)s::text IS NULL OR position(%(search)s::text IN l.municipality_name_normalized) > 0)
        GROUP BY l.location_id, l.uf, l.municipality_name, l.municipality_name_normalized
        ORDER BY l.municipality_name_normalized
        LIMIT %(limit)s OFFSET %(offset)s""",
        {"uf": uf, "search": normalize_text(search) if search else None, "limit": limit, "offset": offset}).fetchall()


# -- Atualidade -----------------------------------------------------------------------------


def dataset_freshness(conn):
    return conn.execute("""
        SELECT (SELECT max(collection_date) FROM fact_price_observation WHERE is_current_source_revision) AS data_as_of,
               (SELECT max(retrieved_at) FROM source_file WHERE is_current)                                AS source_retrieved_at,
               (SELECT max(week_start) FROM mart_weekly_state_price)                                       AS latest_week_start
        """).fetchone()


def latest_run(conn):
    return conn.execute("""
        SELECT run_id::text AS run_id, started_at, finished_at, status, quality_decision,
               rows_accepted, rows_quarantined
        FROM ingestion_run ORDER BY started_at DESC LIMIT 1""").fetchone()


def last_successful_load_at(conn):
    return conn.execute("""
        SELECT max(finished_at) AS finished_at FROM ingestion_run WHERE status IN ('success', 'warning')
        """).fetchone()["finished_at"]


def dataset_latest_week(conn, uf):
    return conn.execute("SELECT max(week_start) AS week_start FROM mart_weekly_state_price WHERE uf = %s",
                        (uf,)).fetchone()["week_start"]


def series_freshness(conn, uf, product_id, start, end, location_ids=None):
    """Última coleta e último download dos arquivos que sustentam um recorte."""
    return conn.execute("""
        SELECT max(f.collection_date) AS data_as_of, max(s.retrieved_at) AS source_retrieved_at
        FROM fact_price_observation f
        JOIN source_file s USING (source_file_id)
        JOIN dim_location l USING (location_id)
        WHERE f.is_current_source_revision AND l.uf = %(uf)s AND f.product_id = %(product)s
          AND f.week_start BETWEEN %(start)s AND %(end)s
          AND (%(locations)s::int[] IS NULL OR f.location_id = ANY(%(locations)s))""",
        {"uf": uf, "product": product_id, "start": start, "end": end, "locations": location_ids}).fetchone()


# -- Preços (agregações semanais) -----------------------------------------------------------


def city_series(conn, location_id, product_id, start, end):
    return conn.execute("""
        SELECT week_start, observation_count, station_count, price_min, price_p25, price_median, price_mean,
               price_p75, price_max, price_stddev, baseline_median_stations, coverage_ratio, quality_flag
        FROM mart_weekly_city_price
        WHERE location_id = %s AND product_id = %s AND week_start BETWEEN %s AND %s
        ORDER BY week_start""", (location_id, product_id, start, end)).fetchall()


def state_series(conn, uf, product_id, start, end):
    return conn.execute("""
        SELECT week_start, observation_count, station_count, price_min, price_p25, price_median, price_mean,
               price_p75, price_max, price_stddev,
               NULL::numeric AS baseline_median_stations, NULL::numeric AS coverage_ratio, NULL::text AS quality_flag
        FROM mart_weekly_state_price
        WHERE uf = %s AND product_id = %s AND week_start BETWEEN %s AND %s
        ORDER BY week_start""", (uf, product_id, start, end)).fetchall()


def city_latest_week(conn, location_id, product_id):
    return conn.execute("""
        SELECT max(week_start) AS week_start FROM mart_weekly_city_price
        WHERE location_id = %s AND product_id = %s""", (location_id, product_id)).fetchone()["week_start"]


def state_latest_week(conn, uf, product_id):
    return conn.execute("""
        SELECT max(week_start) AS week_start FROM mart_weekly_state_price
        WHERE uf = %s AND product_id = %s""", (uf, product_id)).fetchone()["week_start"]


def state_coverage(conn, uf, product_id, start, end):
    """Por semana: municípios na amostra e quantos com cobertura baixa."""
    rows = conn.execute("""
        SELECT m.week_start, count(*) AS municipalities,
               count(*) FILTER (WHERE m.quality_flag = 'cobertura_baixa') AS low
        FROM mart_weekly_city_price m JOIN dim_location l USING (location_id)
        WHERE l.uf = %s AND m.product_id = %s AND m.week_start BETWEEN %s AND %s
        GROUP BY m.week_start""", (uf, product_id, start, end)).fetchall()
    return {row["week_start"]: row for row in rows}


def compare_rows(conn, location_ids, product_id, week_start):
    return conn.execute("""
        SELECT l.location_id, l.uf, l.municipality_name,
               m.week_start, m.observation_count, m.station_count, m.price_min, m.price_p25, m.price_median,
               m.price_mean, m.price_p75, m.price_max, m.price_stddev, m.baseline_median_stations,
               m.coverage_ratio, m.quality_flag
        FROM dim_location l
        LEFT JOIN mart_weekly_city_price m
               ON m.location_id = l.location_id AND m.product_id = %s AND m.week_start = %s
        WHERE l.location_id = ANY(%s)""", (product_id, week_start, list(location_ids))).fetchall()


# -- Postos ---------------------------------------------------------------------------------


def list_stations(conn, uf, location_id, product_id, limit, offset, since=None, order="name"):
    """Postos do recorte; com `product_id`, só os que têm preço do produto e o último preço de cada um.

    `since` mantém só os postos cujo último preço foi coletado nessa data ou depois. `order` é
    `name`, `price_asc` ou `price_desc` (comparado por parâmetro, sem texto de SQL montado)."""
    return conn.execute("""
        SELECT s.cnpj, s.trade_name, s.legal_name, s.brand, s.address, s.neighborhood, s.postal_code,
               l.municipality_name, l.uf, s.first_seen_date, s.last_seen_date,
               p.sale_price AS latest_price, p.collection_date AS latest_price_date,
               coalesce(p.quality_flags, '{}') AS latest_price_flags,
               count(*) OVER () AS total
        FROM dim_station s
        JOIN dim_location l USING (location_id)
        LEFT JOIN LATERAL (
            SELECT f.sale_price, f.collection_date, f.quality_flags
            FROM fact_price_observation f
            WHERE f.station_id = s.station_id AND f.product_id = %(product)s AND f.is_current_source_revision
            ORDER BY f.collection_date DESC LIMIT 1) p ON true
        WHERE l.uf = %(uf)s
          AND (%(location)s::int IS NULL OR s.location_id = %(location)s)
          AND (%(product)s::int IS NULL OR p.sale_price IS NOT NULL)
          AND (%(since)s::date IS NULL OR p.collection_date >= %(since)s)
        ORDER BY CASE WHEN %(order)s = 'price_asc' THEN p.sale_price END ASC,
                 CASE WHEN %(order)s = 'price_desc' THEN p.sale_price END DESC,
                 coalesce(s.trade_name, s.legal_name), s.station_id
        LIMIT %(limit)s OFFSET %(offset)s""",
        {"uf": uf, "location": location_id, "product": product_id, "limit": limit, "offset": offset,
         "since": since, "order": order}).fetchall()


def brand_prices(conn, uf, location_id, product_id, week_start):
    """Estatísticas da semana por bandeira (a bandeira cadastrada do posto), direto do fato."""
    return conn.execute("""
        SELECT coalesce(s.brand, 'NAO INFORMADA') AS brand,
               count(DISTINCT f.station_id) AS stations, count(*) AS observations,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS median,
               round(avg(f.sale_price), 4) AS mean, min(f.sale_price) AS min, max(f.sale_price) AS max
        FROM fact_price_observation f
        JOIN dim_station s USING (station_id)
        JOIN dim_location l ON l.location_id = f.location_id
        WHERE f.is_current_source_revision AND f.product_id = %(product)s AND f.week_start = %(week)s
          AND l.uf = %(uf)s AND (%(location)s::int IS NULL OR f.location_id = %(location)s)
        GROUP BY 1 ORDER BY median, brand""",
        {"product": product_id, "week": week_start, "uf": uf, "location": location_id}).fetchall()


# -- Previsões e variações incomuns (Marco 7) -----------------------------------------------


def published_model(conn, uf):
    """O modelo em uso: no máximo um por vez (índice único parcial). Só colunas liberadas ao papel."""
    return conn.execute("""
        SELECT model_version_id, name, version, kind, status, origin_week, created_at, metrics
        FROM model_version WHERE is_published AND uf = %s""", (uf,)).fetchone()


def forecast_items(conn, model_id, uf, location_id, product_id):
    return conn.execute("""
        SELECT horizon, target_week, point, lower, upper, interval_level, history_weeks, station_count,
               origin_week, generated_on
        FROM forecast
        WHERE model_version_id = %(model)s AND uf = %(uf)s AND product_id = %(product)s
          AND location_id IS NOT DISTINCT FROM %(location)s
        ORDER BY horizon""", {"model": model_id, "uf": uf, "product": product_id, "location": location_id}).fetchall()


def forecast_eligibility(conn, model_id, uf, location_id, product_id):
    return conn.execute("""
        SELECT eligible, reasons, history_weeks, last_week FROM forecast_eligibility
        WHERE model_version_id = %(model)s AND uf = %(uf)s AND product_id = %(product)s
          AND location_id IS NOT DISTINCT FROM %(location)s""",
        {"model": model_id, "uf": uf, "product": product_id, "location": location_id}).fetchone()


def list_anomalies(conn, model_id, uf, location_id, product_id, since, limit, offset):
    return conn.execute("""
        SELECT l.municipality_name, p.canonical_name AS product, a.week_start, a.observed, a.expected, a.lower,
               a.upper, a.residual, a.direction, a.station_count, a.interval_level, count(*) OVER () AS total
        FROM anomaly a
        LEFT JOIN dim_location l USING (location_id)
        JOIN dim_product p USING (product_id)
        WHERE a.model_version_id = %(model)s AND a.uf = %(uf)s AND a.week_start >= %(since)s
          AND (%(product)s::int IS NULL OR a.product_id = %(product)s)
          AND (%(location)s::int IS NULL OR a.location_id = %(location)s)
        ORDER BY a.week_start DESC, abs(a.residual) DESC, l.municipality_name NULLS FIRST, p.canonical_name
        LIMIT %(limit)s OFFSET %(offset)s""",
        {"model": model_id, "uf": uf, "since": since, "product": product_id, "location": location_id,
         "limit": limit, "offset": offset}).fetchall()


# -- Qualidade e cobertura ------------------------------------------------------------------


def observation_counts(conn):
    row = conn.execute("""
        SELECT count(*) AS published, count(*) FILTER (WHERE quality_status = 'warning') AS with_warning
        FROM fact_price_observation WHERE is_current_source_revision""").fetchone()
    flags = conn.execute("""
        SELECT flag, count(*) AS n FROM (
            SELECT unnest(quality_flags) AS flag FROM fact_price_observation WHERE is_current_source_revision) t
        GROUP BY flag ORDER BY flag""").fetchall()
    return row, {r["flag"]: r["n"] for r in flags}


def quarantine_counts(conn):
    row = conn.execute("SELECT count(*) AS n FROM quarantine_observation WHERE is_current").fetchone()
    reasons = conn.execute("""
        SELECT reason, count(*) AS n FROM (
            SELECT unnest(reasons) AS reason FROM quarantine_observation WHERE is_current) t
        GROUP BY reason ORDER BY reason""").fetchall()
    return row["n"], {r["reason"]: r["n"] for r in reasons}


def coverage_summary(conn, uf, week_start):
    # Base zero (série nova) conta como sem histórico, igual ao `coverage_status` das respostas.
    rows = conn.execute("""
        SELECT CASE WHEN m.quality_flag = 'ok' AND m.baseline_median_stations = 0 THEN 'sem_historico'
                    ELSE m.quality_flag END AS quality_flag, count(*) AS n
        FROM mart_weekly_city_price m JOIN dim_location l USING (location_id)
        WHERE l.uf = %s AND m.week_start = %s GROUP BY 1""", (uf, week_start)).fetchall()
    return {r["quality_flag"]: r["n"] for r in rows}


def low_coverage_series(conn, uf, week_start, limit, offset):
    return conn.execute("""
        SELECT l.uf, l.municipality_name, p.canonical_name AS product, m.station_count,
               m.baseline_median_stations, m.coverage_ratio, count(*) OVER () AS total
        FROM mart_weekly_city_price m
        JOIN dim_location l USING (location_id)
        JOIN dim_product p USING (product_id)
        WHERE l.uf = %s AND m.week_start = %s AND m.quality_flag = 'cobertura_baixa'
        ORDER BY m.coverage_ratio, l.municipality_name_normalized, p.canonical_name
        LIMIT %s OFFSET %s""", (uf, week_start, limit, offset)).fetchall()
