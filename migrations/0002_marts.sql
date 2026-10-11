-- Agregações semanais (Marco 4), recalculadas pelo carregador na mesma transação da carga.
-- Estatísticas de preço arredondadas a 4 casas (as fontes têm até 3); mínimo e máximo exatos.
-- percentile_cont trabalha em ponto flutuante: o arredondamento remove o ruído binário.

CREATE MATERIALIZED VIEW mart_weekly_city_price AS
WITH weekly AS (
    SELECT f.week_start, f.location_id, f.product_id,
           count(*)                                    AS observation_count,
           count(DISTINCT f.station_id)                AS station_count,
           min(f.sale_price)                           AS price_min,
           round(percentile_cont(0.25) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS price_p25,
           round(percentile_cont(0.50) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS price_median,
           round(avg(f.sale_price), 4)                 AS price_mean,
           round(percentile_cont(0.75) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS price_p75,
           max(f.sale_price)                           AS price_max,
           round(stddev_samp(f.sale_price), 4)         AS price_stddev
    FROM fact_price_observation f
    WHERE f.is_current_source_revision
    GROUP BY f.week_start, f.location_id, f.product_id
),
calendar AS (
    SELECT generate_series(min(week_start), max(week_start), interval '7 days')::date AS week_start
    FROM weekly
),
grid AS (  -- ausência de uma semana conta como zero postos, como no relatório de cobertura
    SELECT c.week_start, s.location_id, s.product_id, coalesce(w.station_count, 0) AS station_count
    FROM calendar c
    CROSS JOIN (SELECT DISTINCT location_id, product_id FROM weekly) s
    LEFT JOIN weekly w USING (week_start, location_id, product_id)
),
baseline AS (  -- mediana de postos das oito semanas anteriores; exige as oito no calendário
    SELECT g.week_start, g.location_id, g.product_id,
           CASE WHEN count(p.week_start) = 8
                THEN percentile_cont(0.5) WITHIN GROUP (ORDER BY p.station_count) END AS baseline_median_stations
    FROM grid g
    LEFT JOIN grid p ON p.location_id = g.location_id AND p.product_id = g.product_id
                    AND p.week_start BETWEEN g.week_start - 56 AND g.week_start - 7
    GROUP BY g.week_start, g.location_id, g.product_id
)
SELECT w.week_start, w.location_id, w.product_id,
       w.observation_count, w.station_count,
       w.price_min, w.price_p25, w.price_median, w.price_mean, w.price_p75, w.price_max, w.price_stddev,
       b.baseline_median_stations,
       CASE WHEN b.baseline_median_stations > 0
            THEN round(w.station_count / b.baseline_median_stations::numeric, 3) END AS coverage_ratio,
       CASE WHEN b.baseline_median_stations IS NULL THEN 'sem_historico'
            WHEN b.baseline_median_stations >= 3 AND w.station_count < 0.5 * b.baseline_median_stations
                 THEN 'cobertura_baixa'
            ELSE 'ok' END AS quality_flag
FROM weekly w
JOIN baseline b USING (week_start, location_id, product_id);

CREATE UNIQUE INDEX uq_mart_weekly_city_price ON mart_weekly_city_price (week_start, location_id, product_id);

CREATE MATERIALIZED VIEW mart_weekly_state_price AS
SELECT f.week_start, l.uf, f.product_id,
       count(*)                                    AS observation_count,
       count(DISTINCT f.station_id)                AS station_count,
       min(f.sale_price)                           AS price_min,
       round(percentile_cont(0.25) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS price_p25,
       round(percentile_cont(0.50) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS price_median,
       round(avg(f.sale_price), 4)                 AS price_mean,
       round(percentile_cont(0.75) WITHIN GROUP (ORDER BY f.sale_price::double precision)::numeric, 4) AS price_p75,
       max(f.sale_price)                           AS price_max,
       round(stddev_samp(f.sale_price), 4)         AS price_stddev
FROM fact_price_observation f
JOIN dim_location l USING (location_id)
WHERE f.is_current_source_revision
GROUP BY f.week_start, l.uf, f.product_id;

CREATE UNIQUE INDEX uq_mart_weekly_state_price ON mart_weekly_state_price (week_start, uf, product_id);
