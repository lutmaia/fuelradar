-- Previsões, variações incomuns e versões de modelo (Marco 7; arquitetura, seção 11).
-- Escritas só pela rotina de previsão (papel administrativo). A API lê pelo papel radar_reader.

CREATE TABLE model_version (
    model_version_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name             text    NOT NULL,
    version          text    NOT NULL,
    kind             text    NOT NULL CHECK (kind IN ('baseline', 'candidate')),
    status           text    NOT NULL CHECK (status IN ('candidate', 'approved', 'rejected', 'archived')),
    is_published     boolean NOT NULL DEFAULT false,
    uf               text    NOT NULL,
    origin_week      date    NOT NULL,
    code_sha         text,
    data_hash        text    NOT NULL,
    parameters       jsonb   NOT NULL DEFAULT '{}',
    metrics          jsonb   NOT NULL DEFAULT '{}',
    artifact_uri     text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
-- No máximo um modelo publicado por vez; o anterior fica arquivado e serve de rollback.
CREATE UNIQUE INDEX uq_model_version_published ON model_version ((true)) WHERE is_published;

CREATE TABLE forecast (
    model_version_id integer NOT NULL REFERENCES model_version,
    uf               text    NOT NULL,
    location_id      integer REFERENCES dim_location,   -- nulo = agregado estadual
    product_id       integer NOT NULL REFERENCES dim_product,
    origin_week      date    NOT NULL,
    target_week      date    NOT NULL,
    horizon          smallint NOT NULL CHECK (horizon BETWEEN 1 AND 4),
    point            numeric(8,4) NOT NULL,
    lower            numeric(8,4) NOT NULL,
    upper            numeric(8,4) NOT NULL,
    interval_level   numeric(4,3) NOT NULL,
    history_weeks    integer NOT NULL,
    station_count    integer,
    generated_on     date    NOT NULL,
    CHECK (lower <= point AND point <= upper)
);
CREATE UNIQUE INDEX uq_forecast ON forecast (model_version_id, uf, coalesce(location_id, 0), product_id, horizon);

-- Por que uma série tem (ou não) previsão: elegibilidade da seção 14.2.
CREATE TABLE forecast_eligibility (
    model_version_id integer NOT NULL REFERENCES model_version,
    uf               text    NOT NULL,
    location_id      integer REFERENCES dim_location,
    product_id       integer NOT NULL REFERENCES dim_product,
    eligible         boolean NOT NULL,
    reasons          text[]  NOT NULL DEFAULT '{}',
    history_weeks    integer NOT NULL,
    last_week        date    NOT NULL
);
CREATE UNIQUE INDEX uq_forecast_eligibility
    ON forecast_eligibility (model_version_id, uf, coalesce(location_id, 0), product_id);

CREATE TABLE anomaly (
    anomaly_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_version_id integer NOT NULL REFERENCES model_version,
    uf               text    NOT NULL,
    location_id      integer REFERENCES dim_location,
    product_id       integer NOT NULL REFERENCES dim_product,
    week_start       date    NOT NULL,
    observed         numeric(8,4) NOT NULL,
    expected         numeric(8,4) NOT NULL,
    lower            numeric(8,4) NOT NULL,
    upper            numeric(8,4) NOT NULL,
    residual         numeric(8,4) NOT NULL,
    direction        text    NOT NULL CHECK (direction IN ('acima', 'abaixo')),
    station_count    integer NOT NULL,
    interval_level   numeric(4,3) NOT NULL
);
CREATE UNIQUE INDEX uq_anomaly ON anomaly (model_version_id, uf, coalesce(location_id, 0), product_id, week_start);
CREATE INDEX ix_anomaly_week ON anomaly (week_start DESC);

GRANT SELECT ON forecast, forecast_eligibility, anomaly TO radar_reader;
-- Sem artifact_uri (caminho local) nem code_sha: não fazem parte do contrato público.
GRANT SELECT (model_version_id, name, version, kind, status, is_published, uf, origin_week, data_hash,
              parameters, metrics, created_at) ON model_version TO radar_reader;
