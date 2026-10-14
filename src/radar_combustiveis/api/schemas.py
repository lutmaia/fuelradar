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
    latest_week_start: date | None = Field(
        None, description="Semana usada por `only_latest_week` (domingo); nulo sem o filtro.")
    items: list[Station]


class BrandItem(BaseModel):
    brand: str
    stations: int
    observations: int
    median: float
    mean: float
    min: float
    max: float
    difference_to_reference: float = Field(description="Mediana da bandeira menos a mediana de todos os postos.")


class BrandsResponse(Freshness):
    location: Location
    product: str
    unit: str
    week_start: date
    week_end: date
    reference_median: float | None = Field(description="Mediana de todos os postos do recorte na semana.")
    reference_stations: int
    min_stations: int = Field(description="Bandeiras com menos postos que isso não são detalhadas.")
    hidden_brands: int
    hidden_stations: int
    items: list[BrandItem]


class EthanolPoint(BaseModel):
    week_start: date
    gasoline_median: float | None = None
    ethanol_median: float | None = None
    ratio: float | None = Field(None, description="Mediana do etanol ÷ mediana da gasolina comum, 4 casas.")
    pays: bool | None = Field(None, description="Verdadeiro quando `ratio` ≤ `threshold` (o etanol compensa).")
    reason: Literal["MISSING_PRODUCT", "LOW_COVERAGE"] | None = Field(
        None, description="Por que não há razão na semana: falta um dos produtos ou a cobertura está baixa.")


class EthanolResponse(Freshness):
    location: Location
    threshold: float = Field(description="Regra prática: o etanol compensa até esta fração do preço da gasolina.")
    latest: EthanolPoint | None = Field(description="Semana mais recente com razão calculada.")
    items: list[EthanolPoint] = Field(description="Semanas com algum dos dois preços, em ordem cronológica.")


class StationChoiceWeek(BaseModel):
    week_start: date
    week_end: date
    stations: int
    median: float
    min: float
    p25: float
    p75: float
    saving: float = Field(description="Mediana menos o menor preço da semana, em R$ por unidade.")
    saving_tank: float | None = Field(None, description="`saving` vezes `tank_liters`; nulo fora de R$/litro.")


class StationChoiceResponse(Freshness):
    location: Location
    product: str
    unit: str
    min_stations: int = Field(description="Semanas com menos postos não entram: o menor preço de poucos diz pouco.")
    tank_liters: int
    latest: StationChoiceWeek | None = Field(description="Semana mais recente do município com postos suficientes.")
    typical_saving: float | None = Field(None, description="Mediana de `saving` nas semanas do último ano.")
    typical_weeks: int = Field(description="Semanas usadas em `typical_saving`.")
    typical_change: float | None = Field(
        None, description="Mediana do tamanho de uma mudança de preço (|Δ| ≥ R$ 0,01) do mesmo posto entre semanas "
                          "consecutivas, no último ano: o reajuste típico, para comparar com `typical_saving`.")


Region = Literal["capital", "metropolitana", "litoral", "interior"]


class RegionPoint(BaseModel):
    week_start: date
    region: Region
    median: float = Field(description="Mediana de todos os preços da região na semana (não a mediana das medianas).")
    observations: int
    stations: int
    municipalities: int


class RegionItem(RegionPoint):
    label: str
    difference_to_capital: float | None = Field(
        None, description="Mediana da região menos a da capital na mesma semana; nulo na capital ou sem ela.")
    municipality_names: list[str] = Field(description="Municípios da região com preço na semana.")


class RegionsResponse(Freshness):
    product: str
    unit: str
    week_start: date = Field(description="Semana mais recente do estado para o produto.")
    week_end: date
    items: list[RegionItem] = Field(description="As regiões na semana mais recente.")
    series: list[RegionPoint] = Field(description="As semanas da janela pedida, em ordem cronológica.")


class EthanolRank(BaseModel):
    weeks: int = Field(description="Semanas da janela com as duas medianas e cobertura normal.")
    share_pays: float | None = Field(None, description="Fração dessas semanas em que o etanol compensou.")
    median_ratio: float | None = None
    latest_ratio: float | None = None
    latest_week_start: date | None = None
    ranked: bool = Field(description="Verdadeiro com `weeks` ≥ `min_weeks`.")


class ChoiceRank(BaseModel):
    weeks: int = Field(description="Semanas da janela com ao menos `min_stations` postos.")
    typical_saving: float | None = Field(None, description="Mediana de (mediana − menor preço) nessas semanas.")
    latest_saving: float | None = None
    latest_week_start: date | None = None
    ranked: bool


class RankingItem(BaseModel):
    location: Location
    region: Region
    ethanol: EthanolRank
    station_choice: ChoiceRank


class RankingsResponse(Freshness):
    product: str = Field(description="Produto da economia de escolher o posto; o etanol compara sempre com a gasolina comum.")
    unit: str
    start: date
    end: date
    weeks: int
    min_weeks: int = Field(description="Semanas mínimas para entrar no ranking (metade da janela).")
    threshold: float
    min_stations: int
    tank_liters: int
    items: list[RankingItem] = Field(description="Todos os municípios com dado na janela, por nome.")


class ForecastPoint(BaseModel):
    horizon: int = Field(description="Semanas à frente da semana de origem (1 a 4).")
    target_week_start: date
    target_week_end: date
    point: float = Field(description="Previsão central da mediana semanal, em R$ por unidade.")
    lower: float = Field(description="Limite inferior do intervalo (`interval_level`).")
    upper: float


class BacktestMetrics(BaseModel):
    mae: float | None = Field(None, description="Erro absoluto médio no backtest, em R$ por unidade.")
    weighted_mae: float | None = Field(None, description="MAE ponderado pelo número de postos da semana prevista.")
    bias: float | None = Field(None, description="Previsão menos observado (negativo: subestima).")
    interval_coverage: float | None = Field(None, description="Fração de observados dentro do intervalo.")
    interval_width: float | None = None


class ModelBacktest(BaseModel):
    points: int
    origins: int
    published: BacktestMetrics
    best_baseline: str
    best_baseline_label: str
    candidate: BacktestMetrics | None
    candidate_approved: bool
    candidate_change: float | None = Field(
        None, description="Variação do MAE ponderado do candidato contra o melhor baseline "
                          "(negativo = candidato melhor).")
    checks: dict[str, bool]


class ModelInfo(BaseModel):
    name: str
    label: str
    kind: Literal["baseline", "candidate"]
    version: str
    status: str
    origin_week_start: date
    created_at: datetime
    backtest: ModelBacktest | None


class ForecastResponse(Freshness):
    location: Location
    product: str
    unit: str
    model: ModelInfo
    eligible: bool
    reasons: list[str] = Field(description="Por que a série não tem previsão, quando não tem.")
    history_weeks: int | None
    origin_week_start: date | None
    interval_level: float | None
    items: list[ForecastPoint]


class AnomalyItem(BaseModel):
    location: Location
    product: str
    week_start: date
    week_end: date
    observed: float = Field(description="Mediana observada na semana.")
    expected: float = Field(description="Valor esperado pelo baseline de uma semana (último valor).")
    lower: float
    upper: float
    difference: float = Field(description="Observado menos esperado.")
    direction: Literal["acima", "abaixo"]
    stations: int
    interval_level: float


class AnomaliesResponse(Freshness, PageInfo):
    model_version: str
    since_week_start: date
    items: list[AnomalyItem]


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
