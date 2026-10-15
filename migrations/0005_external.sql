-- Fontes externas (Marco 9; desenho do estudo de caso, seção 4.3, e ADR 0010).
-- Uma tabela de observações para as três fontes: dólar (BCB), produtores e distribuição (ANP).
-- `available_at` é o dia a partir do qual o valor podia ser conhecido: uma previsão feita na data
-- D só pode usar valores com available_at <= D.

CREATE TABLE external_source (
    source_id  text PRIMARY KEY,
    publisher  text NOT NULL,
    title      text NOT NULL,
    page_url   text NOT NULL,
    license    text NOT NULL,
    terms_url  text NOT NULL,
    cadence    text NOT NULL,
    lag_rule   text NOT NULL
);

CREATE TABLE external_file (
    sha256       text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    source_id    text NOT NULL REFERENCES external_source,
    name         text NOT NULL,
    url          text NOT NULL,
    raw_path     text NOT NULL,
    retrieved_at timestamptz NOT NULL,
    row_count    integer NOT NULL,
    loaded_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE external_observation (
    source_id          text NOT NULL REFERENCES external_source,
    product            text NOT NULL,
    geo_level          text NOT NULL CHECK (geo_level IN ('pais', 'regiao', 'uf', 'municipio')),
    geo                text NOT NULL,
    uf                 text,
    period_start       date NOT NULL,
    period_end         date NOT NULL CHECK (period_end >= period_start),
    value              numeric(12,6) NOT NULL CHECK (value > 0),
    stddev             numeric(12,6),
    unit               text NOT NULL,
    available_at       date NOT NULL CHECK (available_at >= period_end),
    first_retrieved_at timestamptz NOT NULL,
    retrieved_at       timestamptz NOT NULL,
    file_sha256        text NOT NULL REFERENCES external_file,
    revised            boolean NOT NULL DEFAULT false,
    PRIMARY KEY (source_id, product, geo_level, geo, period_start)
);
CREATE INDEX ix_external_observation_available ON external_observation (source_id, product, geo, available_at);

-- A API lê a distribuição para a margem bruta; o caminho local dos arquivos não faz parte do contrato.
GRANT SELECT ON external_source, external_observation TO radar_reader;
GRANT SELECT (sha256, source_id, name, url, retrieved_at, row_count) ON external_file TO radar_reader;
