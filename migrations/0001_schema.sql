-- Esquema inicial (Marco 4): tabelas operacionais, dimensões e fato de preços.
-- Executada pelo runner com search_path = radar; ver docs/decisions/0003-banco-postgresql.md.

-- Operacional ---------------------------------------------------------------

CREATE TABLE ingestion_run (
    run_id            uuid PRIMARY KEY,
    started_at        timestamptz NOT NULL,
    finished_at       timestamptz,
    status            text NOT NULL CHECK (status IN ('running', 'success', 'warning', 'failed')),
    code_sha          text,
    rows_read         bigint,
    rows_accepted     bigint,
    rows_quarantined  bigint,
    quality_run_id    uuid,
    quality_decision  text,
    error_summary     text
);

CREATE TABLE source_file (
    source_file_id    text PRIMARY KEY CHECK (source_file_id ~ '^[0-9a-f]{16}$'),
    run_id            uuid NOT NULL REFERENCES ingestion_run (run_id),
    sha256            text NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    period_key        text NOT NULL,
    revision          integer NOT NULL CHECK (revision >= 1),
    is_current        boolean NOT NULL,
    kinds             text[] NOT NULL,
    reference_start   date,
    reference_end     date,
    source_url        text,
    retrieved_at      timestamptz,
    storage_uri       text NOT NULL,
    size_bytes        bigint NOT NULL,
    first_seen_at     timestamptz NOT NULL,
    UNIQUE (period_key, revision),
    CHECK (reference_end IS NULL OR reference_start <= reference_end)
);
-- Uma revisão vigente por período.
CREATE UNIQUE INDEX one_current_revision_per_period ON source_file (period_key) WHERE is_current;

-- Dimensões ----------------------------------------------------------------

CREATE TABLE dim_location (
    location_id                   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ibge_code                     text,
    municipality_name             text NOT NULL,
    municipality_name_normalized  text NOT NULL,
    uf                            char(2) NOT NULL CHECK (uf ~ '^[A-Z]{2}$'),
    region                        text,
    UNIQUE (uf, municipality_name_normalized)
);

CREATE TABLE dim_product (
    product_id      smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_name  text NOT NULL UNIQUE,
    source_name     text NOT NULL,
    category        text NOT NULL CHECK (category IN ('automotivo', 'glp')),
    unit            text NOT NULL,
    active          boolean NOT NULL
);

-- Deve espelhar PRODUCTS (ingestion/normalize.py) e PRODUCT_UNITS (quality/rules.py);
-- um teste confere a igualdade. GLP existe na fonte, mas está fora do MVP automotivo.
INSERT INTO dim_product (canonical_name, source_name, category, unit, active) VALUES
    ('GASOLINA_COMUM',     'GASOLINA COMUM',     'automotivo', 'BRL/L',    true),
    ('GASOLINA_ADITIVADA', 'GASOLINA ADITIVADA', 'automotivo', 'BRL/L',    true),
    ('ETANOL_HIDRATADO',   'ETANOL',             'automotivo', 'BRL/L',    true),
    ('DIESEL_COMUM',       'DIESEL S500',        'automotivo', 'BRL/L',    true),
    ('DIESEL_S10',         'DIESEL S10',         'automotivo', 'BRL/L',    true),
    ('GNV',                'GNV',                'automotivo', 'BRL/M3',   true),
    ('GLP',                'GLP',                'glp',        'BRL/13KG', false);

CREATE TABLE dim_station (
    station_id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cnpj             text NOT NULL UNIQUE CHECK (cnpj ~ '^[0-9A-Z]{12}[0-9]{2}$'),
    legal_name       text,
    trade_name       text,
    brand            text,
    address          text,
    neighborhood     text,
    postal_code      text,
    location_id      integer NOT NULL REFERENCES dim_location (location_id),
    first_seen_date  date NOT NULL,
    last_seen_date   date NOT NULL,
    CHECK (first_seen_date <= last_seen_date)
);

-- Fato ---------------------------------------------------------------------

CREATE TABLE fact_price_observation (
    observation_id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_id              text NOT NULL REFERENCES source_file (source_file_id),
    station_id                  integer NOT NULL REFERENCES dim_station (station_id),
    location_id                 integer NOT NULL REFERENCES dim_location (location_id),
    product_id                  smallint NOT NULL REFERENCES dim_product (product_id),
    collection_date             date NOT NULL,
    week_start                  date NOT NULL,
    sale_price                  numeric NOT NULL CHECK (sale_price > 0),
    purchase_price              numeric CHECK (purchase_price > 0),
    row_key                     text NOT NULL,
    source_row_hash             text NOT NULL,
    source_row_number           integer NOT NULL,
    quality_status              text NOT NULL CHECK (quality_status IN ('ok', 'warning')),
    quality_flags               text[] NOT NULL DEFAULT '{}',
    duplicate_sources           text[] NOT NULL DEFAULT '{}',
    -- Verdadeiro quando a linha pertence ao conjunto publicado atual: revisão vigente da
    -- fonte e cópia escolhida pela precedência. Linhas antigas são mantidas para auditoria.
    is_current_source_revision  boolean NOT NULL,
    loaded_run_id               uuid NOT NULL REFERENCES ingestion_run (run_id),
    UNIQUE (source_file_id, source_row_hash),
    -- Semana da ANP: domingo a sábado.
    CHECK (week_start = collection_date - extract(dow FROM collection_date)::integer),
    CHECK (quality_status = CASE WHEN cardinality(quality_flags) = 0 THEN 'ok' ELSE 'warning' END)
);
-- No máximo uma observação vigente por chave de negócio.
CREATE UNIQUE INDEX uq_fact_current_row_key ON fact_price_observation (row_key)
    WHERE is_current_source_revision;
CREATE INDEX ix_fact_location_product_date ON fact_price_observation (location_id, product_id, collection_date);
CREATE INDEX ix_fact_station_product_date ON fact_price_observation (station_id, product_id, collection_date);
CREATE INDEX ix_fact_week_product ON fact_price_observation (week_start, product_id);

-- Quarentena -----------------------------------------------------------------

CREATE FUNCTION safe_date(value text) RETURNS date LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN value::date;
EXCEPTION WHEN others THEN
    RETURN NULL;
END
$$;

CREATE TABLE quarantine_observation (
    quarantine_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_id     text NOT NULL REFERENCES source_file (source_file_id),
    source_row_number  integer NOT NULL,
    source_row_hash    text NOT NULL,
    collection_date    date,
    reasons            text[] NOT NULL CHECK (cardinality(reasons) > 0),
    original           jsonb NOT NULL,
    is_current         boolean NOT NULL,
    loaded_run_id      uuid NOT NULL REFERENCES ingestion_run (run_id),
    UNIQUE (source_file_id, source_row_hash)
);
