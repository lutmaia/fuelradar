"""Pacote instantâneo do demonstrativo público (ADR 0009).

O demonstrativo roda o mesmo painel sem API nem banco: lê um arquivo com as respostas da API já
calculadas. Este módulo gera esse arquivo consultando a API de verdade (em processo, sobre o banco)
para todo parâmetro que o painel usa e que é finito (produto × município), e guarda o mínimo para
o cliente instantâneo reproduzir as consultas combinatórias (histórico por intervalo, comparação
de municípios, variações por filtro) com a mesma regra da API.

Privacidade: nenhum CNPJ nem razão social vai ao pacote. O posto
aparece pelo nome fantasia publicado pela ANP ou, sem ele, pela bandeira (o endereço vai à parte).
"""

from datetime import date, datetime, timedelta, timezone
import gzip
import json

from pydantic import TypeAdapter

from .dashboard.client import ApiError

FORMAT_VERSION = 1
HISTORY_DAYS = 1095        # o intervalo máximo da API (1.096 dias) cobre a janela de 3 anos do painel
REGION_WEEKS = 26
ANOMALY_WEEKS = 12         # o máximo da API; o cliente filtra janelas menores
MARGIN_WEEKS = 52          # margem bruta; o dólar não entra no pacote (ODbL, ADR 0010)
_DATETIME = TypeAdapter(datetime)


def call_key(method, *args):
    return json.dumps([method, *args], ensure_ascii=False)


def public_name(brand):
    if not brand:
        return "Posto sem bandeira informada"
    return "Posto bandeira branca" if brand == "BRANCA" else f"Posto {brand}"


def public_station(item, trade_names):
    """Tira CNPJ e razão social; o nome é o fantasia publicado pela ANP ou a bandeira."""
    return {**item, "cnpj": None, "legal_name": None,
            "name": trade_names.get(item["cnpj"]) or public_name(item["brand"])}


def _trade_names(conn, uf):
    rows = conn.execute("""
        SELECT s.cnpj, nullif(trim(s.trade_name), '') AS trade_name
        FROM dim_station s JOIN dim_location l USING (location_id) WHERE l.uf = %s""", (uf,)).fetchall()
    return {r["cnpj"]: r["trade_name"] for r in rows}


def _collections(conn, uf):
    """Última coleta e último download por produto, município e semana: o cliente instantâneo
    calcula com isso o `data_as_of` de qualquer recorte, como `series_freshness` da API."""
    rows = conn.execute("""
        SELECT p.canonical_name AS product, l.municipality_name AS municipality, f.week_start,
               max(f.collection_date) AS data_as_of, max(s.retrieved_at) AS retrieved_at
        FROM fact_price_observation f
        JOIN source_file s USING (source_file_id)
        JOIN dim_location l ON l.location_id = f.location_id
        JOIN dim_product p ON p.product_id = f.product_id
        WHERE f.is_current_source_revision AND l.uf = %s
        GROUP BY 1, 2, 3""", (uf,)).fetchall()
    out = {}
    for r in rows:
        retrieved = None if r["retrieved_at"] is None else _DATETIME.dump_python(
            r["retrieved_at"].astimezone(timezone.utc), mode="json")
        out.setdefault(r["product"], {}).setdefault(r["municipality"], {})[r["week_start"].isoformat()] = [
            r["data_as_of"].isoformat(), retrieved]
    return out


def build(api, conn, uf="SP", now=None):
    """Gera o pacote: `api` é um `ApiClient` (a API real), `conn` uma conexão `dict_row` ao mesmo banco."""
    calls = {}

    def take(method, *args, transform=None):
        try:
            body = getattr(api, method)(*args)
            if transform:
                body = transform(body)
        except ApiError as exc:
            body = {"__error__": {"status": exc.status, "code": exc.code, "message": exc.message}}
        calls[call_key(method, *args)] = body
        return body

    trade_names = _trade_names(conn, uf)

    def private(body):
        return {**body, "items": [public_station(i, trade_names) for i in body["items"]]}

    fresh = take("freshness")
    products = [p["code"] for p in take("products")]
    names = [loc["municipality"] for loc in take("locations")]
    take("data_quality")
    take("scoreboard")
    latest_week = fresh["latest_week_start"]
    start = (date.fromisoformat(latest_week) - timedelta(days=HISTORY_DAYS)).isoformat()

    history = {}
    for product in products:
        take("regions", product, REGION_WEEKS)
        take("rankings", product, REGION_WEEKS)
        take("margin_municipalities", product)
        for name in [None, *names]:
            take("latest", product, name)
            take("brands", product, name)
            take("forecasts", product, name)
            take("margins", product, name, MARGIN_WEEKS)
            if name is not None:
                take("margin_stations", product, name, transform=private)
            body = api.history(product, name, start, latest_week)
            history[call_key(product, name)] = {"location": body["location"], "items": body["items"]}
            if name is None:
                continue
            take("station_choice", product, name)
            take("stations", name, product, transform=private)
            take("station_ranking", name, product, True, transform=private)
            take("station_ranking", name, product, False, transform=private)
    take("ethanol", None, 1)
    for name in names:
        take("ethanol", name, 26)
    try:
        anomalies = api.anomalies(None, None, ANOMALY_WEEKS)
    except ApiError as exc:
        anomalies = {"__error__": {"status": exc.status, "code": exc.code, "message": exc.message}}

    return {"format": FORMAT_VERSION, "uf": uf,
            "built_at": _DATETIME.dump_python(now or datetime.now(timezone.utc), mode="json"),
            "latest_week_start": latest_week, "history_start": start, "calls": calls, "history": history,
            "anomalies": anomalies, "collections": _collections(conn, uf)}


def write(package, path):
    data = json.dumps(package, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with gzip.GzipFile(path, "wb", mtime=0) as fh:  # mtime fixo: o mesmo pacote gera os mesmos bytes
        fh.write(data)
    return len(data)
