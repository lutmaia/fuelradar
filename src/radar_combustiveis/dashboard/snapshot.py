"""Cliente instantâneo: o painel lendo um pacote de arquivos em vez da API (demonstrativo público).

Mesmos métodos e mesmas respostas do `ApiClient`. A maior parte vem pronta do pacote (gerado por
`radar_combustiveis.snapshot` a partir da API real); histórico por intervalo, comparação de
municípios e filtros de variações incomuns são recalculados aqui com a regra da API, e um teste
confere cliente instantâneo × API nas mesmas consultas (tests/test_snapshot.py).
"""

from datetime import date, datetime, timedelta, timezone
import gzip
import json

from ..ingestion.normalize import normalize_text
from .client import ApiError

MAX_HISTORY_DAYS = 1096
DEFAULT_HISTORY_WEEKS = 52
MAX_ANOMALY_WEEKS = 12


def _key(*parts):
    return json.dumps(list(parts), ensure_ascii=False)


def _iso(value):
    return value if value is None or isinstance(value, str) else value.isoformat()


def _week_plus(week, days):
    return (date.fromisoformat(week) + timedelta(days=days)).isoformat()


def _raise(body):
    if isinstance(body, dict) and "__error__" in body:
        error = body["__error__"]
        raise ApiError(error["status"], error["code"], error["message"])
    return body


class SnapshotClient:
    mode = "snapshot"
    base_url = "pacote instantâneo"

    def __init__(self, package, today=None):
        self._p = package
        self._today = today
        self._names = {normalize_text(loc["municipality"]): loc["municipality"] for loc in self._stored("locations")}

    @classmethod
    def from_file(cls, path):
        with gzip.open(path, "rb") as fh:
            return cls(json.loads(fh.read().decode("utf-8")))

    @property
    def built_at(self):
        return self._p["built_at"]

    # -- auxiliares ---------------------------------------------------------------------------

    def _stored(self, method, *args):
        key = _key(method, *args)
        if key not in self._p["calls"]:
            raise ApiError(404, "NOT_IN_SNAPSHOT", "Esta consulta não está no pacote do demonstrativo.")
        return _raise(self._p["calls"][key])

    def _product(self, code):
        if code not in {p["code"] for p in self._stored("products")}:
            raise ApiError(404, "PRODUCT_NOT_FOUND", "Produto não encontrado entre os publicados (ver /api/v1/products).")
        return code

    def _location(self, name):
        if name is None:
            return None
        found = self._names.get(normalize_text(name))
        if found is None:
            raise ApiError(404, "LOCATION_NOT_FOUND",
                           f"Município não encontrado na cobertura publicada para São Paulo: {name.strip()}.")
        return found

    def _freshness_of(self, product, names, start, end):
        """Como `series_freshness` da API: última coleta e último download no recorte."""
        by_city = self._p["collections"].get(product, {})
        as_of = retrieved = None
        for name in (names if names is not None else by_city):
            for week, (day, got) in by_city.get(name, {}).items():
                if start <= week <= end:
                    as_of = day if as_of is None or day > as_of else as_of
                    retrieved = got if got and (retrieved is None or got > retrieved) else retrieved
        return as_of, retrieved

    def _series(self, product, name):
        return self._p["history"][_key(product, name)]

    # -- consultas ----------------------------------------------------------------------------

    def freshness(self):
        body = dict(self._stored("freshness"))
        if body["data_as_of"]:  # a idade é de hoje, não do dia em que o pacote foi gerado
            today = self._today or datetime.now(timezone.utc).date()
            body["age_days"] = (today - date.fromisoformat(body["data_as_of"])).days
        return body

    def products(self):
        return self._stored("products")

    def locations(self):
        return self._stored("locations")

    def latest(self, product, municipality=None):
        return self._stored("latest", product, municipality)

    def history(self, product, municipality=None, start=None, end=None):
        self._product(product)
        name = self._location(municipality)
        start, end = _iso(start), _iso(end) or self._p["latest_week_start"]
        if start is not None and start > end:
            raise ApiError(422, "INVALID_RANGE", "`start` não pode ser posterior a `end`.")
        start = start or _week_plus(end, -7 * (DEFAULT_HISTORY_WEEKS - 1))
        if (date.fromisoformat(end) - date.fromisoformat(start)).days > MAX_HISTORY_DAYS:
            raise ApiError(422, "RANGE_TOO_LARGE", f"O intervalo máximo é de {MAX_HISTORY_DAYS} dias.")
        series = self._series(product, name)
        items = [p for p in series["items"] if start <= p["week_start"] <= end]
        as_of, retrieved = self._freshness_of(product, None if name is None else [name], start, end)
        return {"data_as_of": as_of, "source_retrieved_at": retrieved, "location": series["location"],
                "product": product, "start": start, "end": end, "page": 1, "page_size": 200,
                "total": len(items), "items": items}

    def compare(self, product, municipalities, week_start=None):
        """Mesma regra de `/prices/compare`: posição pela menor mediana, sem cobertura baixa; empate divide."""
        self._product(product)
        names = sorted({self._location(n) for n in municipalities})
        week = _iso(week_start) or self._p["latest_week_start"]
        points = {}
        for name in names:
            points[name] = next((p for p in self._series(product, name)["items"] if p["week_start"] == week), None)
        state = next((p for p in self._series(product, None)["items"] if p["week_start"] == week), None)
        state_median = state["statistics"]["median"] if state else None
        eligible = sorted((n for n, p in points.items() if p and p["sample"]["coverage_status"] != "low"),
                          key=lambda n: (points[n]["statistics"]["median"], n))
        ranks, previous, position = {}, None, 0
        for name in eligible:
            position += 1
            median = points[name]["statistics"]["median"]
            if previous is None or median != previous:
                rank = position
            ranks[name], previous = rank, median
        items = []
        for name, p in points.items():
            diff = (round(p["statistics"]["median"] - state_median, 4)
                    if p is not None and state_median is not None else None)
            items.append({"location": {"uf": self._p["uf"], "municipality": name},
                          "statistics": p["statistics"] if p else None,
                          "sample": p["sample"] if p else _empty_sample(),
                          "rank": ranks.get(name), "difference_to_state": diff})
        items.sort(key=lambda i: (i["rank"] is None, i["rank"] or 0, i["location"]["municipality"]))
        as_of, retrieved = self._freshness_of(product, names, week, week)
        return {"data_as_of": as_of, "source_retrieved_at": retrieved, "product": product, "week_start": week,
                "week_end": _week_plus(week, 6),
                "reference": {"location": {"uf": self._p["uf"], "municipality": None},
                              "statistics": state["statistics"] if state else None,
                              "sample": state["sample"] if state else _empty_sample()},
                "items": items}

    def stations(self, municipality, product, limit=None):
        return self._stored("stations", municipality, product)

    def station_ranking(self, municipality, product, cheapest=True, size=5):
        return self._stored("station_ranking", municipality, product, cheapest)

    def brands(self, product, municipality=None):
        return self._stored("brands", product, municipality)

    def ethanol(self, municipality=None, weeks=26):
        return self._stored("ethanol", municipality, weeks)

    def station_choice(self, product, municipality):
        return self._stored("station_choice", product, municipality)

    def regions(self, product, weeks=26):
        return self._stored("regions", product, weeks)

    def rankings(self, product, weeks=26):
        return self._stored("rankings", product, weeks)

    def margins(self, product, municipality=None, weeks=52):
        return self._stored("margins", product, municipality, weeks)

    def margin_municipalities(self, product):
        return self._stored("margin_municipalities", product)

    def margin_stations(self, product, municipality):
        return self._stored("margin_stations", product, municipality)

    def scoreboard(self):
        return self._stored("scoreboard")

    def forecasts(self, product, municipality=None):
        return self._stored("forecasts", product, municipality)

    def anomalies(self, product=None, municipality=None, weeks=4):
        """Filtra as 12 semanas guardadas como `/anomalies` filtra no banco."""
        if not 1 <= weeks <= MAX_ANOMALY_WEEKS:
            raise ApiError(422, "VALIDATION_ERROR", "`weeks` deve estar entre 1 e 12.")
        stored = _raise(self._p["anomalies"])
        if product is not None:
            self._product(product)
        name = self._location(municipality)
        since = _week_plus(self._p["latest_week_start"], -7 * (weeks - 1))
        items = [i for i in stored["items"] if i["week_start"] >= since
                 and (product is None or i["product"] == product)
                 and (name is None or i["location"]["municipality"] == name)]
        return {**stored, "since_week_start": since, "page": 1, "total": len(items), "items": items}

    def data_quality(self, week_start=None):
        return self._stored("data_quality")


def _empty_sample():
    return {"observations": 0, "stations": 0, "coverage_status": "no_data", "coverage_ratio": None,
            "baseline_median_stations": None, "municipalities": None, "low_coverage_municipalities": None}
