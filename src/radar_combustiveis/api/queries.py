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


def city_rows(conn, uf, product_ids, start, end):
    """Agregações semanais de todos os municípios da UF para alguns produtos (rankings)."""
    return conn.execute("""
        SELECT l.municipality_name, l.municipality_name_normalized, m.product_id, m.week_start,
               m.station_count, m.price_min, m.price_median, m.quality_flag
        FROM mart_weekly_city_price m JOIN dim_location l USING (location_id)
        WHERE l.uf = %s AND m.product_id = ANY(%s) AND m.week_start BETWEEN %s AND %s
        ORDER BY l.municipality_name_normalized, m.week_start""",
        (uf, list(product_ids), start, end)).fetchall()


def region_prices(conn, uf, product_id, start, end, capital, metro, coast):
    """Mediana semanal de todos os preços de cada região, direto do fato (como no estudo descritivo).

    A região sai das listas de `regions.py`, passadas como parâmetros; o resto do estado é interior."""
    return conn.execute("""
        SELECT f.week_start,
               CASE WHEN l.municipality_name_normalized = %(capital)s THEN 'capital'
                    WHEN l.municipality_name_normalized = ANY(%(metro)s) THEN 'metropolitana'
                    WHEN l.municipality_name_normalized = ANY(%(coast)s) THEN 'litoral'
                    ELSE 'interior' END AS region,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS median,
               count(*) AS observations, count(DISTINCT f.station_id) AS stations,
               array_agg(DISTINCT l.municipality_name ORDER BY l.municipality_name) AS municipalities
        FROM fact_price_observation f JOIN dim_location l ON l.location_id = f.location_id
        WHERE f.is_current_source_revision AND l.uf = %(uf)s AND f.product_id = %(product)s
          AND f.week_start BETWEEN %(start)s AND %(end)s
        GROUP BY 1, 2 ORDER BY 1, 2""",
        {"uf": uf, "product": product_id, "start": start, "end": end, "capital": capital,
         "metro": sorted(metro), "coast": sorted(coast)}).fetchall()


def distribution_prices(conn, uf, product_code, geo, start, end):
    """Preço médio de distribuição (ANP) por semana: `geo` é o nome normalizado do município ou a sigla da UF."""
    return conn.execute("""
        SELECT period_start AS week_start, value, available_at FROM external_observation
        WHERE source_id = 'anp_distribuicao' AND uf = %s AND product = %s AND geo = %s
          AND geo_level = CASE WHEN %s THEN 'uf' ELSE 'municipio' END
          AND period_start BETWEEN %s AND %s
        ORDER BY period_start""", (uf, product_code, geo, geo == uf, start, end)).fetchall()


def latest_distribution_week(conn, uf, product_code):
    return conn.execute("""
        SELECT max(period_start) AS week_start FROM external_observation
        WHERE source_id = 'anp_distribuicao' AND uf = %s AND product = %s AND geo_level = 'uf'""",
                        (uf, product_code)).fetchone()["week_start"]


def municipal_margins(conn, uf, product_id, product_code, week_start):
    """Por município, na semana: mediana dos postos (agregação semanal) e preço médio de distribuição."""
    return conn.execute("""
        SELECT l.municipality_name, m.price_median, m.station_count, m.quality_flag, d.value AS distribution
        FROM mart_weekly_city_price m
        JOIN dim_location l USING (location_id)
        JOIN external_observation d
          ON d.source_id = 'anp_distribuicao' AND d.geo_level = 'municipio' AND d.uf = l.uf
         AND d.geo = l.municipality_name_normalized AND d.product = %(code)s AND d.period_start = m.week_start
        WHERE l.uf = %(uf)s AND m.product_id = %(product)s AND m.week_start = %(week)s
        ORDER BY l.municipality_name_normalized""",
        {"uf": uf, "product": product_id, "code": product_code, "week": week_start}).fetchall()


def station_week_prices(conn, location_id, product_id, week_start):
    """Preço de cada posto na semana (média das coletas da semana, em geral uma só)."""
    return conn.execute("""
        SELECT s.cnpj, s.trade_name, s.legal_name, s.brand, s.address, s.neighborhood,
               round(avg(f.sale_price), 4) AS price, max(f.collection_date) AS collection_date,
               bool_or('preco_extremo' = ANY (f.quality_flags)) AS extreme
        FROM fact_price_observation f JOIN dim_station s USING (station_id)
        WHERE f.is_current_source_revision AND f.location_id = %s AND f.product_id = %s AND f.week_start = %s
        GROUP BY s.station_id, s.cnpj, s.trade_name, s.legal_name, s.brand, s.address, s.neighborhood
        ORDER BY price, coalesce(s.trade_name, s.legal_name), s.station_id""",
        (location_id, product_id, week_start)).fetchall()


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


def typical_station_change(conn, location_id, product_id, start, end):
    """Mediana de |Δ| (≥ R$ 0,01) entre semanas consecutivas do mesmo posto: o reajuste típico."""
    return conn.execute("""
        WITH obs AS (
            SELECT f.station_id, f.week_start, f.sale_price,
                   lag(f.week_start) OVER w AS prev_week, lag(f.sale_price) OVER w AS prev_price
            FROM fact_price_observation f
            WHERE f.is_current_source_revision AND f.location_id = %(location)s AND f.product_id = %(product)s
              AND f.week_start BETWEEN %(start)s::date - 7 AND %(end)s
            WINDOW w AS (PARTITION BY f.station_id ORDER BY f.week_start))
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(sale_price - prev_price)::double precision) AS change
        FROM obs
        WHERE week_start >= %(start)s AND week_start - prev_week = 7 AND abs(sale_price - prev_price) >= 0.01""",
        {"location": location_id, "product": product_id, "start": start, "end": end}).fetchone()["change"]


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


# -- Previsões e variações incomuns ------------------------------------------------------


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


def class_forecasts(conn, uf, location_id, product_id):
    """Probabilidades de classe da origem mais recente registrada (avaliação ao vivo)."""
    return conn.execute("""
        SELECT origin_week, horizon, target_week, p_down, p_flat, p_up, model, temperature
        FROM forecast_class
        WHERE uf = %(uf)s AND product_id = %(product)s AND location_id IS NOT DISTINCT FROM %(location)s
          AND origin_week = (SELECT max(origin_week) FROM forecast_class WHERE uf = %(uf)s)
        ORDER BY horizon""", {"uf": uf, "product": product_id, "location": location_id}).fetchall()


def latest_scoreboard(conn):
    return conn.execute("SELECT computed_at, body FROM live_scoreboard ORDER BY computed_at DESC LIMIT 1").fetchone()


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
