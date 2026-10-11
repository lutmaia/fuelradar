"""Contratos de resposta da API. Geram o esquema OpenAPI e são a referência do contrato.

Preços saem como número JSON, em R$ (ou R$/m³ no GNV), com até 4 casas. Datas em ISO 8601 e
instantes em UTC. `null` significa "não disponível", nunca zero.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ok: cobertura normal; low: abaixo de 50% da mediana de postos das 8 semanas anteriores;
# no_history: sem 8 semanas de base ou série nova (base zero); not_applicable: agregado estadual;
# no_data: sem observações.
CoverageStatus = Literal["ok", "low", "no_history", "not_applicable", "no_data"]


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Freshness(BaseModel):
    data_as_of: date | None = Field(None, description="Última data de coleta usada na resposta.")
    source_retrieved_at: datetime | None = Field(
        None, description="Quando o arquivo mais recente usado foi baixado da ANP. Nulo para arquivos "
                          "recebidos manualmente, sem registro de download.")


class PageInfo(BaseModel):
    page: int
    page_size: int
    total: int


class Location(BaseModel):
    uf: str
    municipality: str | None = Field(None, description="Nulo no agregado estadual.")


class Statistics(BaseModel):
    min: float | None = None
    p25: float | None = None
    median: float | None = Field(None, description="Indicador principal (seção 13.1 da arquitetura).")
    mean: float | None = None
    p75: float | None = None
    max: float | None = None
    stddev: float | None = None


class Sample(BaseModel):
    observations: int
    stations: int
    coverage_status: CoverageStatus
    coverage_ratio: float | None = Field(None, description="Postos da semana ÷ mediana das 8 semanas anteriores.")
    baseline_median_stations: float | None = None
    municipalities: int | None = Field(None, description="Só no agregado estadual: municípios na amostra.")
    low_coverage_municipalities: int | None = Field(
        None, description="Só no agregado estadual: municípios com cobertura baixa na semana.")


class WeeklyChange(BaseModel):
    value: float | None = Field(None, description="(mediana da semana ÷ mediana da anterior) − 1; nulo é N/D.")
    previous_week_start: date | None = None
    reason: Literal["NO_PREVIOUS_WEEK", "LOW_COVERAGE"] | None = Field(
        None, description="Por que o valor é N/D: sem semana anterior ou cobertura insuficiente.")


class Health(BaseModel):
    status: Literal["ok", "ready"]


class LoadRun(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    quality_decision: str | None
    rows_accepted: int | None
    rows_quarantined: int | None


class FreshnessResponse(Freshness):
    published_ufs: list[str]
    latest_week_start: date | None
    age_days: int | None = Field(None, description="Dias entre a última coleta e hoje (UTC).")
    last_successful_load_at: datetime | None
    last_load: LoadRun | None = Field(None, description="Última tentativa de carga, de qualquer status.")
    source: str


class Product(BaseModel):
    code: str
    label: str
    category: str
    unit: str


class ProductsResponse(Freshness):
    items: list[Product]


class LocationItem(BaseModel):
    uf: str
    municipality: str
    products: int
    first_week_start: date
    last_week_start: date


class LocationsResponse(Freshness, PageInfo):
    published_ufs: list[str]
    items: list[LocationItem]


class LatestPrice(Freshness):
    location: Location
    product: str
    week_start: date
    week_end: date
    is_dataset_latest_week: bool = Field(
        description="Falso quando a série não tem dados na semana mais recente do conjunto.")
    statistics: Statistics
    sample: Sample
    weekly_change: WeeklyChange


class SeriesPoint(BaseModel):
    week_start: date
    week_end: date
    statistics: Statistics
    sample: Sample
    weekly_change: WeeklyChange


class HistoryResponse(Freshness, PageInfo):
    location: Location
    product: str
    start: date
    end: date
    items: list[SeriesPoint]


class CompareItem(BaseModel):
    location: Location
    statistics: Statistics | None
    sample: Sample
    rank: int | None = Field(None, description="1 = menor mediana. Nulo sem dados ou com cobertura baixa.")
    difference_to_state: float | None = Field(None, description="Mediana do município − mediana estadual.")


class CompareReference(BaseModel):
    location: Location
    statistics: Statistics | None
    sample: Sample


class CompareResponse(Freshness):
    product: str
    week_start: date
    week_end: date
    reference: CompareReference
    items: list[CompareItem]


class Station(BaseModel):
    cnpj: str
    name: str | None
    legal_name: str | None
    brand: str | None
    address: str | None
    neighborhood: str | None
    postal_code: str | None
    municipality: str
    uf: str
    first_seen_date: date
    last_seen_date: date
    latest_price: float | None = Field(None, description="Só com o filtro `product`.")
    latest_price_date: date | None = None
    latest_price_flags: list[str] = []


class StationsResponse(Freshness, PageInfo):
    product: str | None
    items: list[Station]


class QualityLoad(BaseModel):
    observations_published: int
    observations_with_warning: int
    warning_counts: dict[str, int]
    observations_quarantined: int
    quarantine_reasons: dict[str, int]


class CoverageSummary(BaseModel):
    week_start: date | None
    series: int
    ok: int
    low: int
    no_history: int


class LowCoverageItem(BaseModel):
    location: Location
    product: str
    stations: int
    baseline_median_stations: float | None
    coverage_ratio: float | None


class LowCoveragePage(PageInfo):
    items: list[LowCoverageItem]


class DataQualityResponse(Freshness):
    last_load: LoadRun | None
    observations: QualityLoad
    coverage: CoverageSummary
    low_coverage: LowCoveragePage
