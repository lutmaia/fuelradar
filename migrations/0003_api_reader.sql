-- Papel somente leitura da API (Marco 5). Menor privilégio: só as tabelas e colunas que as
-- consultas de leitura usam. Sem LOGIN nem senha: scripts/create_api_role.py cria o usuário de
-- login (radar_api) como membro deste papel, com a senha vinda do ambiente.
-- CREATE ROLE vale para o servidor inteiro, por isso a verificação prévia. Exige permissão
-- CREATEROLE (o superusuário "radar" do contêiner a tem).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'radar_reader') THEN
        CREATE ROLE radar_reader NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA radar TO radar_reader;

GRANT SELECT ON dim_location, dim_product, dim_station, fact_price_observation,
                mart_weekly_city_price, mart_weekly_state_price TO radar_reader;

-- Sem storage_uri (caminho local) nem error_summary: não fazem parte do contrato público.
GRANT SELECT (source_file_id, period_key, revision, is_current, kinds, reference_start, reference_end,
              source_url, retrieved_at) ON source_file TO radar_reader;
GRANT SELECT (run_id, started_at, finished_at, status, rows_read, rows_accepted, rows_quarantined,
              quality_decision) ON ingestion_run TO radar_reader;
-- Quarentena: só os motivos para contagem; os valores originais não são expostos.
GRANT SELECT (source_file_id, reasons, is_current) ON quarantine_observation TO radar_reader;

-- Índices das consultas da API --------------------------------------------------
-- Série de um município e produto: o índice único da visão começa por week_start.
CREATE INDEX ix_mart_city_series ON mart_weekly_city_price (location_id, product_id, week_start);
-- "Última data de coleta" sem varrer o fato inteiro.
CREATE INDEX ix_fact_current_collection_date ON fact_price_observation (collection_date)
    WHERE is_current_source_revision;
