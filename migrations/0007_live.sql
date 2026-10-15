-- Previsões de classe ao vivo e placar (Marcos 10b e 11; docs/estudo/protocolo-ao-vivo.md).
-- O registro de verdade são os arquivos em reports/ledger/ (commitados toda semana); estas tabelas
-- são a cópia que a API lê. Uma linha por origem, série e horizonte; nunca atualizada.

CREATE TABLE forecast_class (
    origin_week  date     NOT NULL,
    uf           text     NOT NULL,
    location_id  integer  REFERENCES dim_location,   -- nulo = agregado estadual
    product_id   integer  NOT NULL REFERENCES dim_product,
    horizon      smallint NOT NULL CHECK (horizon IN (1, 2, 4)),
    target_week  date     NOT NULL,
    p_down       numeric(7,6) NOT NULL,
    p_flat       numeric(7,6) NOT NULL,
    p_up         numeric(7,6) NOT NULL,
    model        text     NOT NULL,
    temperature  numeric(8,6) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (abs(p_down + p_flat + p_up - 1) < 0.0001)
);
CREATE UNIQUE INDEX uq_forecast_class ON forecast_class (origin_week, uf, coalesce(location_id, 0), product_id, horizon);

CREATE TABLE live_scoreboard (
    computed_at timestamptz PRIMARY KEY DEFAULT now(),
    body        jsonb NOT NULL
);

GRANT SELECT ON forecast_class, live_scoreboard TO radar_reader;
