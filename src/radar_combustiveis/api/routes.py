"""Endpoints de leitura (arquitetura 15.2). `/forecasts` e `/anomalies` ficam para o Marco 7."""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from psycopg import Connection

from ..ingestion.normalize import normalize_text
from . import queries
from .errors import ApiError
from .schemas import (CompareItem, CompareReference, CompareResponse, CoverageSummary, DataQualityResponse, ErrorResponse,
                      FreshnessResponse, Health, HistoryResponse, LatestPrice, Location, LocationItem,
                      LocationsResponse, LoadRun, LowCoverageItem, LowCoveragePage, Product, ProductsResponse, QualityLoad,
                      Sample, SeriesPoint, Station, StationsResponse, Statistics, WeeklyChange)

API_PREFIX = "/api/v1"
MAX_HISTORY_DAYS = 1096          # 3 anos; o histórico tem uma linha por semana (≤ 157 pontos)
DEFAULT_HISTORY_WEEKS = 52
MAX_COMPARE = 10
MAX_PAGE_SIZE = 200
SOURCE = "ANP — Levantamento de Preços de Combustíveis (preços de revenda, coletados semanalmente)"

PRODUCT_LABELS = {
    "GASOLINA_COMUM": "Gasolina comum",
    "GASOLINA_ADITIVADA": "Gasolina aditivada",
    "ETANOL_HIDRATADO": "Etanol hidratado",
    "DIESEL_COMUM": "Diesel comum (S500)",
    "DIESEL_S10": "Diesel S10",
    "GNV": "GNV",
}
UF_LABELS = {"SP": "São Paulo"}
COVERAGE_STATUS = {"ok": "ok", "cobertura_baixa": "low", "sem_historico": "no_history"}

ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse},
          503: {"model": ErrorResponse}}

health_router = APIRouter(tags=["Saúde"])
router = APIRouter(prefix=API_PREFIX)


def today():
    return datetime.now(timezone.utc).date()


# -- Dependências ---------------------------------------------------------------------------


def get_conn(request: Request):
    with request.app.state.pool.connection() as conn:
        yield conn


Conn = Annotated[Connection, Depends(get_conn)]


def published_uf(request: Request, uf: Annotated[str, Query(
        min_length=2, max_length=2, pattern="^[A-Za-z]{2}$",
        description="UF publicada. Hoje somente SP.")] = "SP") -> str:
    value = uf.upper()
    published = request.app.state.target_ufs
    if value not in published:
        raise ApiError(422, "UF_NOT_PUBLISHED",
                       f"UF {value} fora da cobertura publicada ({', '.join(published)}).")
    return value


Uf = Annotated[str, Depends(published_uf)]
MunicipalityParam = Annotated[str, Query(min_length=1, max_length=80, description="Nome do município; sem acento ou caixa.")]
ProductParam = Annotated[str, Query(min_length=1, max_length=40, description="Código do produto (ver /products).")]


class Pagination:
    def __init__(self, page: Annotated[int, Query(ge=1, le=100_000)] = 1,
                 page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50):
        self.page, self.page_size = page, page_size

    @property
    def offset(self):
        return (self.page - 1) * self.page_size


Page = Annotated[Pagination, Depends(Pagination)]


# -- Resolução e montagem -------------------------------------------------------------------


def require_product(conn, code):
    row = queries.find_product(conn, code.strip().upper())
    if row is None:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "Produto não encontrado entre os publicados (ver /api/v1/products).")
    return row


def require_locations(conn, uf, names):
    rows = queries.find_locations(conn, uf, names)
    found = {r["municipality_name_normalized"] for r in rows}
    missing = sorted({n.strip() for n in names if normalize_text(n) not in found})
    if missing:
        raise ApiError(404, "LOCATION_NOT_FOUND",
                       f"Município não encontrado na cobertura publicada para {UF_LABELS.get(uf, uf)}: "
                       f"{', '.join(missing)}.")
    return rows


def require_week_start(value, name="week_start"):
    if value is not None and value.weekday() != 6:  # semana da ANP: domingo a sábado
        raise ApiError(422, "INVALID_WEEK", f"{name} deve ser um domingo (início da semana da ANP).")


def statistics_of(row):
    return Statistics(min=row["price_min"], p25=row["price_p25"], median=row["price_median"], mean=row["price_mean"],
                      p75=row["price_p75"], max=row["price_max"], stddev=row["price_stddev"])


def sample_of(row, state_coverage=None):
    if state_coverage is not None:  # agregado estadual: a cobertura é avaliada por município
        return Sample(observations=row["observation_count"], stations=row["station_count"],
                      coverage_status="not_applicable", municipalities=state_coverage["municipalities"],
                      low_coverage_municipalities=state_coverage["low"])
    status = COVERAGE_STATUS[row["quality_flag"]]
    if status == "ok" and row["baseline_median_stations"] == 0:
        status = "no_history"  # série nova: nas 8 semanas anteriores não havia nenhum posto para comparar
    return Sample(observations=row["observation_count"], stations=row["station_count"],
                  coverage_status=status, coverage_ratio=row["coverage_ratio"],
                  baseline_median_stations=row["baseline_median_stations"])


def empty_sample():
    return Sample(observations=0, stations=0, coverage_status="no_data")


def weekly_change(row, previous):
    """(mediana ÷ mediana da semana anterior) − 1; N/D sem semana anterior ou com cobertura baixa."""
    if previous is None:
        return WeeklyChange(reason="NO_PREVIOUS_WEEK")
    if "cobertura_baixa" in (row["quality_flag"], previous["quality_flag"]):
        return WeeklyChange(previous_week_start=previous["week_start"], reason="LOW_COVERAGE")
    value = round(row["price_median"] / previous["price_median"] - 1, 4)
    return WeeklyChange(value=value, previous_week_start=previous["week_start"])


def location_of(uf, name):
    return Location(uf=uf, municipality=name)


def series_for(conn, uf, location, product_id, start, end):
    """Linhas semanais de um município (ou do estado) e, por semana, a cobertura estadual."""
    if location is not None:
        rows = queries.city_series(conn, location["location_id"], product_id, start, end)
        return rows, {}
    rows = queries.state_series(conn, uf, product_id, start, end)
    return rows, queries.state_coverage(conn, uf, product_id, start, end)


def point_parts(row, previous, coverage):
    state = None
    if row["quality_flag"] is None:  # agregado estadual
        state = coverage.get(row["week_start"]) or {"municipalities": 0, "low": 0}
    return statistics_of(row), sample_of(row, state), weekly_change(row, previous)


def one_location(conn, uf, municipality):
    return require_locations(conn, uf, [municipality])[0] if municipality else None


# -- Saúde ----------------------------------------------------------------------------------


@health_router.get("/health/live", response_model=Health, summary="O processo está vivo")
def live():
    return Health(status="ok")


@health_router.get("/health/ready", response_model=Health, responses={503: {"model": ErrorResponse}},
                   summary="O banco responde e há carga publicada")
def ready(conn: Conn):
    n = conn.execute("SELECT count(*) AS n FROM ingestion_run WHERE status IN ('success', 'warning')").fetchone()["n"]
    if n == 0:
        raise ApiError(503, "NOT_READY", "O banco não tem nenhuma carga publicada.")
    return Health(status="ready")


# -- Metadados e cadastros ------------------------------------------------------------------


def load_run_of(row):
    return LoadRun(**row) if row else None


@router.get("/metadata/freshness", response_model=FreshnessResponse, responses=ERRORS, tags=["Metadados"],
            summary="Última atualização, fonte e UFs publicadas")
def metadata_freshness(request: Request, conn: Conn):
    fresh = queries.dataset_freshness(conn)
    as_of = fresh["data_as_of"]
    return FreshnessResponse(
        data_as_of=as_of, source_retrieved_at=fresh["source_retrieved_at"],
        published_ufs=list(request.app.state.target_ufs), latest_week_start=fresh["latest_week_start"],
        age_days=(today() - as_of).days if as_of else None,
        last_successful_load_at=queries.last_successful_load_at(conn),
        last_load=load_run_of(queries.latest_run(conn)), source=SOURCE)


@router.get("/products", response_model=ProductsResponse, responses=ERRORS, tags=["Cadastros"],
            summary="Produtos publicados")
def products(conn: Conn):
    fresh = queries.dataset_freshness(conn)
    items = [Product(code=r["canonical_name"], label=PRODUCT_LABELS.get(r["canonical_name"], r["canonical_name"]),
                     category=r["category"], unit=r["unit"]) for r in queries.published_products(conn)]
    return ProductsResponse(data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"], items=items)


@router.get("/locations", response_model=LocationsResponse, responses=ERRORS, tags=["Cadastros"],
            summary="Municípios com preços publicados")
def locations(request: Request, conn: Conn, uf: Uf, page: Page,
              q: Annotated[str | None, Query(max_length=80, description="Trecho do nome do município.")] = None):
    fresh = queries.dataset_freshness(conn)
    rows = queries.list_locations(conn, uf, q, page.page_size, page.offset)
    total = (rows or queries.list_locations(conn, uf, q, 1, 0) or [{"total": 0}])[0]["total"]
    items = [LocationItem(uf=r["uf"], municipality=r["municipality_name"], products=r["products"],
                          first_week_start=r["first_week_start"], last_week_start=r["last_week_start"]) for r in rows]
    return LocationsResponse(data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"],
                             page=page.page, page_size=page.page_size, total=total,
                             published_ufs=list(request.app.state.target_ufs), items=items)


# -- Preços ---------------------------------------------------------------------------------


@router.get("/prices/latest", response_model=LatestPrice, responses=ERRORS, tags=["Preços"],
            summary="Estatística semanal mais recente de um produto")
def prices_latest(conn: Conn, uf: Uf, product: ProductParam, municipality: MunicipalityParam | None = None):
    """Sem `municipality`, devolve o agregado estadual. A resposta traz a semana usada: se a série
    não tem dados na semana mais recente do conjunto, `is_dataset_latest_week` é falso."""
    prod = require_product(conn, product)
    loc = one_location(conn, uf, municipality)
    week = (queries.city_latest_week(conn, loc["location_id"], prod["product_id"]) if loc
            else queries.state_latest_week(conn, uf, prod["product_id"]))
    if week is None:
        raise ApiError(404, "NO_DATA", "Não há preços publicados para este recorte.")
    rows, coverage = series_for(conn, uf, loc, prod["product_id"], week - timedelta(days=7), week)
    by_week = {r["week_start"]: r for r in rows}
    row = by_week[week]
    statistics, sample, change = point_parts(row, by_week.get(week - timedelta(days=7)), coverage)
    fresh = queries.series_freshness(conn, uf, prod["product_id"], week, week,
                                     [loc["location_id"]] if loc else None)
    return LatestPrice(
        location=location_of(uf, loc["municipality_name"] if loc else None), product=prod["canonical_name"],
        week_start=week, week_end=week + timedelta(days=6),
        is_dataset_latest_week=(week == queries.dataset_latest_week(conn, uf)),
        data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"],
        statistics=statistics, sample=sample, weekly_change=change)


@router.get("/prices/history", response_model=HistoryResponse, responses=ERRORS, tags=["Preços"],
            summary="Série semanal de um produto")
def prices_history(conn: Conn, uf: Uf, product: ProductParam, page: Page, municipality: MunicipalityParam | None = None,
                   start: Annotated[date | None, Query(description="Primeira semana (data). Padrão: 52 semanas até `end`.")] = None,
                   end: Annotated[date | None, Query(description="Última semana (data). Padrão: semana mais recente do conjunto.")] = None):
    prod = require_product(conn, product)
    loc = one_location(conn, uf, municipality)
    if start is not None and end is not None and start > end:
        raise ApiError(422, "INVALID_RANGE", "`start` não pode ser posterior a `end`.")
    if end is None:
        end = queries.dataset_latest_week(conn, uf)
        if end is None:
            raise ApiError(404, "NO_DATA", "Não há preços publicados.")
    if start is None:
        start = end - timedelta(weeks=DEFAULT_HISTORY_WEEKS - 1)
    if start > end:
        raise ApiError(422, "INVALID_RANGE", "`start` não pode ser posterior a `end`.")
    if (end - start).days > MAX_HISTORY_DAYS:
        raise ApiError(422, "RANGE_TOO_LARGE", f"O intervalo máximo é de {MAX_HISTORY_DAYS} dias.")
    rows, coverage = series_for(conn, uf, loc, prod["product_id"], start - timedelta(days=7), end)
    by_week = {r["week_start"]: r for r in rows}
    items = []
    for row in rows:
        if row["week_start"] < start:
            continue
        statistics, sample, change = point_parts(row, by_week.get(row["week_start"] - timedelta(days=7)), coverage)
        items.append(SeriesPoint(week_start=row["week_start"], week_end=row["week_start"] + timedelta(days=6),
                                 statistics=statistics, sample=sample, weekly_change=change))
    fresh = queries.series_freshness(conn, uf, prod["product_id"], start, end,
                                     [loc["location_id"]] if loc else None)
    window = items[page.offset:page.offset + page.page_size]
    return HistoryResponse(
        location=location_of(uf, loc["municipality_name"] if loc else None), product=prod["canonical_name"],
        start=start, end=end, data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"],
        page=page.page, page_size=page.page_size, total=len(items), items=window)


@router.get("/prices/compare", response_model=CompareResponse, responses=ERRORS, tags=["Preços"],
            summary="Compara municípios em uma semana, com o agregado estadual como referência")
def prices_compare(conn: Conn, uf: Uf, product: ProductParam,
                   municipality: Annotated[list[str], Query(
                       min_length=1, max_length=MAX_COMPARE,
                       description="Repita o parâmetro para cada município (até 10).")],
                   week_start: Annotated[date | None, Query(description="Domingo da semana. Padrão: a mais recente.")] = None):
    """`rank` ordena pela menor mediana, só entre municípios com dados e cobertura não baixa
    (seção 12.3 da arquitetura: cobertura baixa fica fora de rankings)."""
    require_week_start(week_start)
    if any(not (1 <= len(name.strip()) <= 80) for name in municipality):
        raise ApiError(422, "VALIDATION_ERROR", "Cada município deve ter entre 1 e 80 caracteres.")
    prod = require_product(conn, product)
    found = require_locations(conn, uf, municipality)
    week = week_start or queries.dataset_latest_week(conn, uf)
    if week is None:
        raise ApiError(404, "NO_DATA", "Não há preços publicados.")
    rows = queries.compare_rows(conn, [r["location_id"] for r in found], prod["product_id"], week)
    state_rows = queries.state_series(conn, uf, prod["product_id"], week, week)
    state = state_rows[0] if state_rows else None
    coverage = queries.state_coverage(conn, uf, prod["product_id"], week, week).get(week)
    state_median = state["price_median"] if state else None

    eligible = sorted((r for r in rows if r["week_start"] is not None and r["quality_flag"] != "cobertura_baixa"),
                      key=lambda r: (r["price_median"], r["municipality_name"]))
    ranks, previous, position = {}, None, 0
    for r in eligible:
        position += 1
        if previous is None or r["price_median"] != previous:
            rank = position
        ranks[r["location_id"]], previous = rank, r["price_median"]

    items = []
    for r in rows:
        has_data = r["week_start"] is not None
        diff = (round(r["price_median"] - state_median, 4) if has_data and state_median is not None else None)
        items.append(CompareItem(
            location=location_of(uf, r["municipality_name"]),
            statistics=statistics_of(r) if has_data else None,
            sample=sample_of(r) if has_data else empty_sample(),
            rank=ranks.get(r["location_id"]), difference_to_state=diff))
    items.sort(key=lambda i: (i.rank is None, i.rank or 0, i.location.municipality))

    fresh = queries.series_freshness(conn, uf, prod["product_id"], week, week, [r["location_id"] for r in found])
    reference = CompareReference(
        location=location_of(uf, None), statistics=statistics_of(state) if state else None,
        sample=sample_of(state, coverage or {"municipalities": 0, "low": 0}) if state else empty_sample())
    return CompareResponse(product=prod["canonical_name"], week_start=week, week_end=week + timedelta(days=6),
                           data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"],
                           reference=reference, items=items)


# -- Postos ---------------------------------------------------------------------------------


@router.get("/stations", response_model=StationsResponse, responses=ERRORS, tags=["Postos"],
            summary="Postos pesquisados no recorte, com o último preço do produto")
def stations(conn: Conn, uf: Uf, page: Page, municipality: MunicipalityParam | None = None,
             product: ProductParam | None = None):
    """Postos da amostra da ANP, não o cadastro completo de revendedores. Com `product`, só os
    postos com preço desse produto e o último preço de cada um (a data vai junto)."""
    prod = require_product(conn, product) if product else None
    loc = one_location(conn, uf, municipality)
    rows = queries.list_stations(conn, uf, loc["location_id"] if loc else None,
                                 prod["product_id"] if prod else None, page.page_size, page.offset)
    total = (rows or queries.list_stations(conn, uf, loc["location_id"] if loc else None,
                                           prod["product_id"] if prod else None, 1, 0) or [{"total": 0}])[0]["total"]
    fresh = queries.dataset_freshness(conn)
    items = [Station(cnpj=r["cnpj"], name=r["trade_name"] or r["legal_name"], legal_name=r["legal_name"],
                     brand=r["brand"], address=r["address"], neighborhood=r["neighborhood"],
                     postal_code=r["postal_code"], municipality=r["municipality_name"], uf=r["uf"],
                     first_seen_date=r["first_seen_date"], last_seen_date=r["last_seen_date"],
                     latest_price=r["latest_price"], latest_price_date=r["latest_price_date"],
                     latest_price_flags=r["latest_price_flags"]) for r in rows]
    return StationsResponse(data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"],
                            page=page.page, page_size=page.page_size, total=total,
                            product=prod["canonical_name"] if prod else None, items=items)


# -- Qualidade ------------------------------------------------------------------------------


@router.get("/data-quality", response_model=DataQualityResponse, responses=ERRORS, tags=["Qualidade"],
            summary="Cobertura, avisos e quarentena do conjunto publicado")
def data_quality(conn: Conn, uf: Uf, page: Page,
                 week_start: Annotated[date | None, Query(description="Domingo da semana. Padrão: a mais recente.")] = None):
    require_week_start(week_start)
    week = week_start or queries.dataset_latest_week(conn, uf)
    fresh = queries.dataset_freshness(conn)
    published, flags = queries.observation_counts(conn)
    quarantined, reasons = queries.quarantine_counts(conn)
    counts = queries.coverage_summary(conn, uf, week) if week else {}
    low_rows = queries.low_coverage_series(conn, uf, week, page.page_size, page.offset) if week else []
    low_total = low_rows[0]["total"] if low_rows else counts.get("cobertura_baixa", 0)
    return DataQualityResponse(
        data_as_of=fresh["data_as_of"], source_retrieved_at=fresh["source_retrieved_at"],
        last_load=load_run_of(queries.latest_run(conn)),
        observations=QualityLoad(
            observations_published=published["published"], observations_with_warning=published["with_warning"],
            warning_counts=flags, observations_quarantined=quarantined, quarantine_reasons=reasons),
        coverage=CoverageSummary(week_start=week, series=sum(counts.values()), ok=counts.get("ok", 0),
                                 low=counts.get("cobertura_baixa", 0), no_history=counts.get("sem_historico", 0)),
        low_coverage=LowCoveragePage(
            page=page.page, page_size=page.page_size, total=low_total,
            items=[LowCoverageItem(location=location_of(r["uf"], r["municipality_name"]), product=r["product"],
                                   stations=r["station_count"], baseline_median_stations=r["baseline_median_stations"],
                                   coverage_ratio=r["coverage_ratio"]) for r in low_rows]))
