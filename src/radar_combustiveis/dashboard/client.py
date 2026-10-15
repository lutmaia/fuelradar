"""Cliente HTTP da API para o painel.

O painel só conversa com a API (`RADAR_API_URL`); não conhece o banco. Falhas viram dois erros que
as páginas sabem mostrar: `ApiUnavailable` (não houve resposta) e `ApiError` (a API respondeu com o
formato de erro da arquitetura 15.5).
"""

import os

import httpx

DEFAULT_API_URL = "http://127.0.0.1:8000"
PAGE_SIZE = 200          # máximo da API
EXPORT_ROW_LIMIT = 2000  # limite de linhas de uma exportação (seção 24 da arquitetura)
RANKING_SIZE = 5         # postos em cada lista de "mais baratos" e "mais caros"
TIMEOUT_SECONDS = 10


class ApiUnavailable(Exception):
    """A API não respondeu (rede, recusa de conexão ou tempo esgotado)."""


class ApiError(Exception):
    def __init__(self, status, code, message, request_id=None):
        super().__init__(message)
        self.status, self.code, self.message, self.request_id = status, code, message, request_id


def _clean(params):
    return {k: v for k, v in (params or {}).items() if v is not None}


class ApiClient:
    mode = "api"

    def __init__(self, http):
        self._http = http

    @classmethod
    def from_env(cls, environ=None):
        environ = os.environ if environ is None else environ
        base = (environ.get("RADAR_API_URL") or DEFAULT_API_URL).rstrip("/")
        return cls(httpx.Client(base_url=base, timeout=TIMEOUT_SECONDS,
                                headers={"User-Agent": "radar-combustiveis-painel"}))

    @property
    def base_url(self):
        return str(self._http.base_url).rstrip("/")

    def _get(self, path, params=None):
        try:
            response = self._http.get(path, params=_clean(params))
        except httpx.TransportError as exc:
            raise ApiUnavailable(f"A API não respondeu em {self.base_url} ({type(exc).__name__}).") from exc
        if response.status_code >= 400:
            try:
                error = response.json()["error"]
                raise ApiError(response.status_code, error["code"], error["message"], error.get("request_id"))
            except (ValueError, KeyError, TypeError):
                raise ApiError(response.status_code, "HTTP_ERROR", f"A API respondeu {response.status_code}.") from None
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(response.status_code, "INVALID_RESPONSE", "Resposta da API não é JSON.") from exc

    def _all_pages(self, path, params, limit=None):
        """Percorre as páginas de uma lista. Devolve (itens, total, truncado, primeira resposta)."""
        items, page, first = [], 1, None
        while True:
            body = self._get(path, {**params, "page": page, "page_size": PAGE_SIZE})
            first = first or body
            items.extend(body["items"])
            if len(items) >= body["total"] or not body["items"]:
                return items, body["total"], False, first
            if limit is not None and len(items) >= limit:
                return items[:limit], body["total"], True, first
            page += 1

    # -- consultas ----------------------------------------------------------------------------

    def freshness(self):
        return self._get("/api/v1/metadata/freshness")

    def products(self):
        return self._get("/api/v1/products")["items"]

    def locations(self):
        return self._all_pages("/api/v1/locations", {})[0]

    def latest(self, product, municipality=None):
        return self._get("/api/v1/prices/latest", {"product": product, "municipality": municipality})

    def history(self, product, municipality=None, start=None, end=None):
        items, total, _, first = self._all_pages("/api/v1/prices/history", {
            "product": product, "municipality": municipality, "start": start, "end": end})
        return {**first, "items": items, "total": total}

    def compare(self, product, municipalities, week_start=None):
        return self._get("/api/v1/prices/compare", {
            "product": product, "municipality": list(municipalities), "week_start": week_start})

    def stations(self, municipality, product, limit=EXPORT_ROW_LIMIT):
        items, total, truncated, first = self._all_pages(
            "/api/v1/stations", {"municipality": municipality, "product": product}, limit)
        return {**first, "items": items, "total": total, "truncated": truncated}

    def station_ranking(self, municipality, product, cheapest=True, size=RANKING_SIZE):
        """Os postos de menor (ou maior) último preço, só com preço da semana mais recente do estado."""
        return self._get("/api/v1/stations", {
            "municipality": municipality, "product": product, "only_latest_week": "true",
            "order": "price_asc" if cheapest else "price_desc", "page": 1, "page_size": size})

    def brands(self, product, municipality=None):
        return self._get("/api/v1/prices/by-brand", {"product": product, "municipality": municipality})

    def ethanol(self, municipality=None, weeks=26):
        return self._get("/api/v1/prices/ethanol-vs-gasoline", {"municipality": municipality, "weeks": weeks})

    def station_choice(self, product, municipality):
        return self._get("/api/v1/prices/station-choice", {"product": product, "municipality": municipality})

    def regions(self, product, weeks=26):
        return self._get("/api/v1/prices/regions", {"product": product, "weeks": weeks})

    def rankings(self, product, weeks=26):
        return self._get("/api/v1/prices/rankings", {"product": product, "weeks": weeks})

    def margins(self, product, municipality=None, weeks=52):
        return self._get("/api/v1/prices/margins", {"product": product, "municipality": municipality, "weeks": weeks})

    def margin_municipalities(self, product):
        return self._get("/api/v1/prices/margins/municipalities", {"product": product})

    def margin_stations(self, product, municipality):
        return self._get("/api/v1/prices/margins/stations", {"product": product, "municipality": municipality})

    def forecasts(self, product, municipality=None):
        return self._get("/api/v1/forecasts", {"product": product, "municipality": municipality})

    def anomalies(self, product=None, municipality=None, weeks=4):
        items, total, _, first = self._all_pages("/api/v1/anomalies", {
            "product": product, "municipality": municipality, "weeks": weeks}, limit=EXPORT_ROW_LIMIT)
        return {**first, "items": items, "total": total}

    def data_quality(self, week_start=None):
        """Resumo de qualidade; `low_coverage.items` traz até 200 séries (o total vem em `total`)."""
        return self._get("/api/v1/data-quality", {"week_start": week_start, "page_size": PAGE_SIZE})
