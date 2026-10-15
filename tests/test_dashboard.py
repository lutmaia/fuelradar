"""Painel (Marco 6): formatação, cliente, gráficos, exportação e páginas.

As páginas rodam com o `AppTest` do Streamlit, sem navegador: primeiro contra uma API falsa (casos de
borda, erros e textos), depois contra a API real sobre um PostgreSQL de teste (mesmos dados sintéticos
de tests/test_api.py), conferindo que o que aparece é o que a API e o cálculo independente dizem.
Sem banco ou sem httpx, só a parte sem banco roda.
"""

from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

import logging

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Sem servidor, o Streamlit avisa a cada AppTest que não há runtime; o aviso é esperado.
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

from streamlit.testing.v1 import AppTest  # noqa: E402
import streamlit as st  # noqa: E402

from radar_combustiveis.dashboard import charts, exports, formatting as fmt, tables, views  # noqa: E402
from radar_combustiveis.dashboard.client import (ApiClient, ApiError, ApiUnavailable,  # noqa: E402
                                                 EXPORT_ROW_LIMIT, PAGE_SIZE)
from tests.test_api import ApiCase, LAST, LAST_COLLECTION, week  # noqa: E402

# O Streamlit avisa a cada AppTest que não há runtime; é esperado fora do servidor.
logging.getLogger("streamlit").setLevel(logging.ERROR)


def tearDownModule():
    # O AppTest cria um diretório temporário no import e só o descarta na saída do interpretador,
    # com ResourceWarning. Descartá-lo aqui mantém `-W error::ResourceWarning` limpo.
    from streamlit.testing.v1 import app_test
    app_test.TMP_DIR.cleanup()


EXPLORE = "from radar_combustiveis.dashboard import views\nviews.guarded(views.explore)()"
HOME = "from radar_combustiveis.dashboard import views\nviews.guarded(views.home)()"
COMPARE = "from radar_combustiveis.dashboard import views\nviews.guarded(views.compare)()"
QUALITY = "from radar_combustiveis.dashboard import views\nviews.guarded(views.quality)()"
RANKING = "from radar_combustiveis.dashboard import views\nviews.guarded(views.stations_ranking)()"
FORECAST = "from radar_combustiveis.dashboard import views\nviews.guarded(views.forecasts_page)()"
ANOMALIES = "from radar_combustiveis.dashboard import views\nviews.guarded(views.anomalies_page)()"
BRANDS = "from radar_combustiveis.dashboard import views\nviews.guarded(views.brands_page)()"
REGIONS = "from radar_combustiveis.dashboard import views\nviews.guarded(views.regions_page)()"
STUDY = "from radar_combustiveis.dashboard import views\nviews.guarded(views.study_page)()"
MARGINS = "from radar_combustiveis.dashboard import views\nviews.guarded(views.margins_page)()"


# -- Formatação -----------------------------------------------------------------------------


class FormattingTests(unittest.TestCase):
    def test_brazilian_numbers(self):
        self.assertEqual(fmt.brl(6.289), "R$ 6,29")
        self.assertEqual(fmt.brl(6.289, 3), "R$ 6,289")
        self.assertEqual(fmt.brl(1234.5), "R$ 1.234,50")
        self.assertEqual(fmt.number_br(179699), "179.699")
        self.assertEqual(fmt.decimal_br(0.3103, 4), "0,3103")
        self.assertEqual(fmt.brl(None), "N/D")
        self.assertEqual(fmt.number_br(None), "N/D")

    def test_signed_values_and_percent(self):
        self.assertEqual(fmt.percent(0.0123), "+1,2%")
        self.assertEqual(fmt.percent(-0.0156), "−1,6%")
        self.assertEqual(fmt.percent(0.0), "0,0%")
        self.assertEqual(fmt.percent(0.00001), "0,0%")  # sem sinal quando arredonda para zero
        self.assertEqual(fmt.percent(0.5, 0, signed=False), "50%")
        self.assertEqual(fmt.percent(None), "N/D")
        self.assertEqual(fmt.signed_brl(0.1), "+R$ 0,10")
        self.assertEqual(fmt.signed_brl(-0.1), "−R$ 0,10")
        self.assertEqual(fmt.signed_brl(None), "N/D")

    def test_popular_brand_names_are_shown_in_parentheses(self):
        self.assertEqual(fmt.brand_label("RAIZEN"), "RAIZEN (Shell)")
        self.assertEqual(fmt.brand_label("VIBRA"), "VIBRA (Petrobras)")
        self.assertEqual(fmt.brand_label("VIBRA ENERGIA"), "VIBRA ENERGIA (Petrobras)")
        self.assertEqual(fmt.brand_label("IPIRANGA"), "IPIRANGA")
        self.assertEqual(fmt.brand_label(None), fmt.ND)

    def test_dates_and_instants(self):
        self.assertEqual(fmt.date_br("2026-09-27"), "27/09/2026")
        self.assertEqual(fmt.date_br(date(2026, 1, 5)), "05/01/2026")
        self.assertEqual(fmt.date_br(None), "N/D")
        self.assertEqual(fmt.datetime_br("2026-10-08T19:25:21Z"), "08/10/2026 19:25 UTC")
        self.assertEqual(fmt.week_range_br("2026-09-27"), "27/09/2026 a 03/10/2026")
        self.assertEqual(fmt.retrieved_text(None), "sem registro de download")
        self.assertEqual(fmt.retrieved_short(None), "sem registro")
        self.assertEqual(fmt.retrieved_short("2026-10-08T19:25:21Z"), "08/10/2026")
        self.assertIn("UTC", fmt.retrieved_text("2026-10-08T19:25:21Z"))

    def test_weekly_change_text_explains_the_missing_value(self):
        self.assertEqual(fmt.change_text({"value": -0.0156, "reason": None}), "−1,6%")
        self.assertEqual(fmt.change_text({"value": None, "reason": "LOW_COVERAGE"}), "N/D (cobertura insuficiente)")
        self.assertEqual(fmt.change_text({"value": None, "reason": "NO_PREVIOUS_WEEK"}), "N/D (sem semana anterior)")
        self.assertEqual(fmt.coverage_label("low"), "Cobertura baixa")
        self.assertEqual(fmt.unit_label("BRL/M3"), "R$/m³")


# -- Cliente --------------------------------------------------------------------------------


def mock_client(handler):
    return ApiClient(httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handler)))


class ClientTests(unittest.TestCase):
    def test_none_params_are_dropped_and_lists_repeat(self):
        seen = []

        def handler(request):
            seen.append(request.url)
            return httpx.Response(200, json={"items": [], "total": 0, "page": 1, "page_size": 200,
                                             "location": {}, "product": "X", "start": "", "end": ""})
        client = mock_client(handler)
        client.compare("GASOLINA_COMUM", ["A", "B"], None)
        client.history("GASOLINA_COMUM", None, "2026-01-04")
        self.assertEqual(seen[0].params.get_list("municipality"), ["A", "B"])
        self.assertNotIn("week_start", seen[0].params)
        self.assertNotIn("municipality", seen[1].params)
        self.assertEqual(seen[1].params["start"], "2026-01-04")

    def test_pagination_collects_every_page(self):
        pages = {1: list(range(200)), 2: list(range(200, 250))}

        def handler(request):
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"items": pages[page], "total": 250, "page": page, "page_size": 200})
        items = mock_client(handler).locations()
        self.assertEqual(len(items), 250)

    def test_export_limit_truncates_and_reports_it(self):
        def handler(request):
            return httpx.Response(200, json={"items": list(range(PAGE_SIZE)), "total": 99_999, "page": 1,
                                             "page_size": PAGE_SIZE})
        body = mock_client(handler).stations("CAMPINAS", "GASOLINA_COMUM")
        self.assertTrue(body["truncated"])
        self.assertEqual(len(body["items"]), EXPORT_ROW_LIMIT)
        self.assertEqual(body["total"], 99_999)

    def test_station_ranking_asks_the_api_for_five_current_stations_in_order(self):
        seen = []

        def handler(request):
            seen.append(dict(request.url.params))
            return httpx.Response(200, json={"items": [], "total": 0, "page": 1, "page_size": 5})
        client = mock_client(handler)
        client.station_ranking("CAMPINAS", "GASOLINA_COMUM", True)
        client.station_ranking("CAMPINAS", "GASOLINA_COMUM", False)
        self.assertEqual([p["order"] for p in seen], ["price_asc", "price_desc"])
        for params in seen:
            self.assertEqual((params["only_latest_week"], params["page"], params["page_size"], params["municipality"]),
                             ("true", "1", "5", "CAMPINAS"))

    def test_api_error_keeps_code_message_and_request_id(self):
        def handler(request):
            return httpx.Response(404, json={"error": {"code": "LOCATION_NOT_FOUND", "message": "Município não encontrado.",
                                                       "request_id": "abc"}})
        with self.assertRaises(ApiError) as caught:
            mock_client(handler).latest("GASOLINA_COMUM", "ATLANTIDA")
        self.assertEqual((caught.exception.status, caught.exception.code, caught.exception.request_id),
                         (404, "LOCATION_NOT_FOUND", "abc"))

    def test_unexpected_responses_become_api_errors(self):
        with self.assertRaises(ApiError) as caught:
            mock_client(lambda r: httpx.Response(502, text="<html>bad gateway</html>")).freshness()
        self.assertEqual((caught.exception.status, caught.exception.code), (502, "HTTP_ERROR"))
        with self.assertRaises(ApiError) as caught:
            mock_client(lambda r: httpx.Response(200, text="não é json")).freshness()
        self.assertEqual(caught.exception.code, "INVALID_RESPONSE")

    def test_network_failure_is_api_unavailable(self):
        def handler(request):
            raise httpx.ConnectError("recusada")
        with self.assertRaises(ApiUnavailable):
            mock_client(handler).freshness()

    def test_from_env(self):
        self.assertEqual(ApiClient.from_env({}).base_url, "http://127.0.0.1:8000")
        self.assertEqual(ApiClient.from_env({"RADAR_API_URL": "http://api.local:9000/"}).base_url, "http://api.local:9000")


# -- Gráficos e exportação -----------------------------------------------------------------


def point(week_start, median, status="ok", stations=8, obs=8, p25=None, p75=None):
    return {"week_start": week_start,
            "week_end": (date.fromisoformat(week_start) + timedelta(days=6)).isoformat(),
            "statistics": {"min": median - 0.2, "p25": p25 or median - 0.1, "median": median, "mean": median,
                           "p75": p75 or median + 0.1, "max": median + 0.2, "stddev": 0.1},
            "sample": {"observations": obs, "stations": stations, "coverage_status": status},
            "weekly_change": {"value": 0.01, "previous_week_start": None, "reason": None}}


class ChartAndExportTests(unittest.TestCase):
    def test_missing_weeks_become_gaps_not_interpolated_values(self):
        points = [point("2026-09-06", 6.0), point("2026-09-20", 6.2)]  # falta 13/09
        by_week, weeks = charts.weekly_axis(points)
        self.assertEqual(weeks, ["2026-09-06", "2026-09-13", "2026-09-20"])
        fig = charts.history_figure(points, "CAMPINAS", "R$/litro")
        median = next(t for t in fig.data if t.name == "Mediana — CAMPINAS")
        self.assertEqual(list(median.y), [6.0, None, 6.2])
        self.assertFalse(median.connectgaps)

    def test_low_coverage_is_marked_and_state_reference_is_drawn(self):
        points = [point("2026-09-06", 6.0), point("2026-09-13", 6.1, status="low", stations=2)]
        state = [point("2026-09-06", 6.05), point("2026-09-13", 6.08)]
        fig = charts.history_figure(points, "JUNDIAI", "R$/litro", state)
        names = [t.name for t in fig.data]
        self.assertIn("Cobertura baixa", names)
        self.assertIn("Mediana — estado de SP", names)
        low = next(t for t in fig.data if t.name == "Cobertura baixa")
        self.assertEqual(list(low.x), ["2026-09-13"])
        self.assertEqual(low.marker.symbol, "x")  # não depende só da cor
        self.assertLess(fig.layout.legend.y, 0)  # legenda abaixo do gráfico, não sobre o título

    def test_normalized_index_starts_at_100_on_the_first_common_week(self):
        a = [point("2026-09-06", 5.0), point("2026-09-13", 5.5)]
        b = [point("2026-09-13", 6.0), point("2026-09-20", 6.3)]
        absolute, normalized, base = charts.comparison_figures({"A": a, "B": b}, "R$/litro")
        self.assertEqual(base, "2026-09-13")
        by_name = {t.name: t for t in normalized.data}
        self.assertEqual(list(by_name["A"].y)[1], 100.0)
        self.assertEqual(list(by_name["B"].y)[0], 100.0)
        self.assertAlmostEqual(list(by_name["B"].y)[1], 105.0)
        self.assertEqual(len(absolute.data), 2)

    def test_no_common_week_yields_no_index(self):
        a, b = [point("2026-08-02", 5.0)], [point("2026-09-13", 6.0)]
        _, normalized, base = charts.comparison_figures({"A": a, "B": b}, "R$/litro")
        self.assertIsNone(base)
        self.assertEqual(len(normalized.data), 0)

    def test_region_lines_keep_gaps_and_skip_regions_without_data(self):
        series = [{"week_start": "2026-09-06", "region": "litoral", "median": 6.7},
                  {"week_start": "2026-09-20", "region": "litoral", "median": 6.8},
                  {"week_start": "2026-09-06", "region": "interior", "median": 6.3}]
        fig = charts.regions_figure(series, views.REGION_LABELS, "R$/litro")
        by_name = {t.name: t for t in fig.data}
        self.assertEqual(set(by_name), {"Litoral", "Interior"})
        self.assertEqual(list(by_name["Litoral"].y), [6.7, None, 6.8])

    def test_interval_figure_draws_the_confidence_interval_around_each_estimate(self):
        fig = charts.interval_figure([("Gasolina", -5.6, -6.0, -5.2), ("GNV", -2.2, -4.9, 0.6)], "t", "x")
        trace = fig.data[0]
        self.assertEqual(list(trace.x), [-5.6, -2.2])
        self.assertAlmostEqual(trace.error_x.array[1], 2.8)
        self.assertAlmostEqual(trace.error_x.arrayminus[0], 0.4)

    def test_history_csv_is_excel_friendly_and_keeps_missing_values_empty(self):
        history = {"location": {"uf": "SP", "municipality": "CAMPINAS"}, "product": "GASOLINA_COMUM",
                   "items": [{**point("2026-09-27", 6.289), "weekly_change": {"value": None, "reason": "LOW_COVERAGE"}}]}
        raw = exports.history_csv(history)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        lines = raw.decode("utf-8-sig").split("\r\n")
        header, row = lines[0].split(";"), lines[1].split(";")
        record = dict(zip(header, row))
        self.assertEqual(record["mediana"], "6,2890")
        self.assertEqual(record["municipio"], "CAMPINAS")
        self.assertEqual(record["variacao_semanal"], "")
        self.assertEqual(record["motivo_sem_variacao"], "LOW_COVERAGE")

    def test_stations_csv_keeps_flags_and_blank_names(self):
        stations = [{"cnpj": "00000000000191", "name": None, "legal_name": "POSTO X LTDA", "brand": None,
                     "address": "RUA A", "neighborhood": None, "postal_code": "13000000", "municipality": "CAMPINAS",
                     "uf": "SP", "latest_price": 6.299, "latest_price_date": "2026-09-28",
                     "latest_price_flags": ["preco_extremo"]}]
        record = dict(zip(*[r.split(";") for r in exports.stations_csv(stations, "GASOLINA_COMUM")
                            .decode("utf-8-sig").split("\r\n")[:2]]))
        self.assertEqual(record["ultimo_preco"], "6,299")
        self.assertEqual(record["avisos"], "preco_extremo")
        self.assertEqual(record["nome"], "")


class TypedTableTests(unittest.TestCase):
    """Regressão: ordenar a coluna de datas por texto `dd/mm/aaaa` colocava 31/08 antes de 30/09."""

    DATES = ["2026-08-31", "2026-08-31", "2026-03-31", "2026-09-30", "2026-07-15"]

    def rows(self):
        return [{"Posto": f"POSTO {i}", "Data do preço": tables.to_date(d), "Último preço": 5.9 + i / 100}
                for i, d in enumerate(self.DATES, 1)]

    def test_text_dates_sort_by_day_first_which_is_the_bug(self):
        shown = [fmt.date_br(d) for d in self.DATES]
        # Por texto, o dia vem antes do mês: em ordem decrescente aparece 31/08, 31/03, 30/09, como na tela.
        self.assertEqual(sorted(shown, reverse=True),
                         ["31/08/2026", "31/08/2026", "31/03/2026", "30/09/2026", "15/07/2026"])
        self.assertNotEqual(sorted(shown), [fmt.date_br(d) for d in sorted(self.DATES)])

    def test_typed_dates_sort_by_the_calendar_and_display_in_brazilian_format(self):
        styler = tables.styled(self.rows(), {"Data do preço": tables.day, "Último preço": tables.money3})
        frame = styler.data
        ordered = frame.sort_values("Data do preço")["Data do preço"].tolist()
        self.assertEqual(ordered, [date(2026, 3, 31), date(2026, 7, 15), date(2026, 8, 31), date(2026, 8, 31),
                                   date(2026, 9, 30)])
        html = styler.to_html()
        self.assertIn("31/03/2026", html)
        self.assertIn("R$ 5,910", html)  # exibição brasileira, valor continua numérico
        self.assertNotIn("2026-03-31", html)
        self.assertTrue(pd.api.types.is_numeric_dtype(frame["Último preço"]))

    def test_missing_values_show_a_dash_or_nd_and_stay_missing_in_the_data(self):
        rows = [{"Posição": 1, "Variação semanal": 0.0123}, {"Posição": None, "Variação semanal": None}]
        styler = tables.styled(rows, {"Posição": tables.rank, "Variação semanal": fmt.percent},
                               {"Posição": "—"})
        html = styler.to_html()
        self.assertIn("+1,2%", html)
        self.assertIn("—", html)
        self.assertIn("N/D", html)
        self.assertTrue(styler.data["Posição"].isna().iloc[1])

    def test_to_date_handles_iso_and_missing(self):
        self.assertEqual(tables.to_date("2026-09-30"), date(2026, 9, 30))
        self.assertEqual(tables.to_date("2026-09-30T00:00:00Z"), date(2026, 9, 30))
        self.assertIsNone(tables.to_date(None))


# -- Páginas com API falsa ------------------------------------------------------------------


STAT = {"min": 5.87, "p25": 5.99, "median": 6.29, "mean": 6.274, "p75": 6.49, "max": 6.95, "stddev": 0.31}


def sample(status="ok", stations=25, obs=25, ratio=1.0, base=25.0, **extra):
    return {"observations": obs, "stations": stations, "coverage_status": status, "coverage_ratio": ratio,
            "baseline_median_stations": base, "municipalities": None, "low_coverage_municipalities": None, **extra}


class FakeApi:
    base_url = "http://api.test"

    def __init__(self, **over):
        self.over = over
        self.calls = []

    def freshness(self):
        return {"data_as_of": "2026-10-01", "source_retrieved_at": "2026-10-08T19:25:21Z", "published_ufs": ["SP"],
                "latest_week_start": "2026-09-27", "age_days": 9, "last_successful_load_at": "2026-10-11T00:54:26Z",
                "last_load": {"run_id": "r", "started_at": "2026-10-11T00:54:00Z", "finished_at": "2026-10-11T00:54:26Z",
                              "status": "warning", "quality_decision": "publicar_com_aviso", "rows_accepted": 179699,
                              "rows_quarantined": 0},
                "source": "ANP — Levantamento de Preços de Combustíveis", **self.over.get("fresh", {})}

    def products(self):
        return [{"code": "GASOLINA_COMUM", "label": "Gasolina comum", "category": "automotivo", "unit": "BRL/L"},
                {"code": "GNV", "label": "GNV", "category": "automotivo", "unit": "BRL/M3"}]

    def locations(self):
        return [{"uf": "SP", "municipality": n, "products": 2, "first_week_start": "2026-01-04",
                 "last_week_start": "2026-09-27"} for n in ("CAMPINAS", "JUNDIAI", "SANTOS", "SAO PAULO")]

    def latest(self, product, municipality=None):
        self.calls.append(("latest", product, municipality))
        if "latest_raises" in self.over:
            raise self.over["latest_raises"]
        state = municipality is None
        body = {"data_as_of": "2026-10-01", "source_retrieved_at": "2026-10-08T19:25:21Z",
                "location": {"uf": "SP", "municipality": municipality}, "product": product, "week_start": "2026-09-27",
                "week_end": "2026-10-03", "is_dataset_latest_week": True, "statistics": dict(STAT),
                "sample": (sample("not_applicable", 1251, 1251, None, None, municipalities=95,
                                  low_coverage_municipalities=3) if state else sample()),
                "weekly_change": {"value": -0.0156, "previous_week_start": "2026-09-20", "reason": None}}
        body.update(self.over.get("latest", {}))
        return body

    def history(self, product, municipality=None, start=None, end=None):
        weeks = [(date(2026, 9, 27) - timedelta(weeks=n)).isoformat() for n in range(11, -1, -1)]
        status = self.over.get("history_last_status", "ok")
        items = [point(w, 6.0 + i * 0.02 + (0 if municipality else 0.05), status=status if i == 11 else "ok")
                 for i, w in enumerate(weeks)]
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None, "location": {"uf": "SP", "municipality": municipality},
                "product": product, "start": weeks[0], "end": weeks[-1], "page": 1, "page_size": 200,
                "total": len(items), "items": items}

    def compare(self, product, municipalities, week_start=None):
        items = []
        for i, name in enumerate(municipalities):
            low = self.over.get("low_city") == name
            items.append({"location": {"uf": "SP", "municipality": name}, "statistics": {**STAT, "median": 6.0 + i / 10},
                          "sample": sample("low" if low else "ok", 2 if low else 8, 2 if low else 8, 0.25 if low else 1.0, 8.0),
                          "rank": None if low else i + 1, "difference_to_state": 0.1 * i - 0.05})
        return {"data_as_of": "2026-10-01", "source_retrieved_at": "2026-10-08T19:25:21Z", "product": product,
                "week_start": week_start or "2026-09-27", "week_end": "2026-10-03",
                "reference": {"location": {"uf": "SP", "municipality": None}, "statistics": {**STAT, "median": 6.05},
                              "sample": sample("not_applicable", 1251, 1251, None, None, municipalities=95,
                                               low_coverage_municipalities=3)},
                "items": items}

    def stations(self, municipality, product, limit=EXPORT_ROW_LIMIT):
        dates = self.over.get("station_dates", ["2026-09-28"] * 3)
        items = [{"cnpj": f"0000000000{i:04d}", "name": f"POSTO {i}", "legal_name": f"POSTO {i} LTDA", "brand": "BRANCA",
                  "address": "RUA A", "neighborhood": "CENTRO", "postal_code": "13000000", "municipality": municipality,
                  "uf": "SP", "first_seen_date": "2026-01-06", "last_seen_date": "2026-09-29",
                  "latest_price": 6.0 + i / 100, "latest_price_date": when,
                  "latest_price_flags": ["preco_extremo"] if i == 1 else []} for i, when in enumerate(dates, 1)]
        return {"product": product, "total": len(items), "items": items, "truncated": False, "data_as_of": "2026-10-01",
                "source_retrieved_at": None}

    def station_ranking(self, municipality, product, cheapest=True, size=5):
        total = self.over.get("ranking_total", 12)
        prices = [5.89, 5.95, 5.99, 6.05, 6.09, 6.39, 6.49, 6.55, 6.59, 6.65, 6.79, 6.99][:total]
        chosen = (prices if cheapest else prices[::-1])[:size]
        items = [{"cnpj": f"0000000000{i:04d}", "name": f"POSTO {price}", "legal_name": None, "brand": "BRANCA",
                  "address": "RUA A", "neighborhood": "CENTRO", "postal_code": None, "municipality": municipality,
                  "uf": "SP", "first_seen_date": "2026-01-06", "last_seen_date": "2026-09-30",
                  "latest_price": price, "latest_price_date": "2026-09-30",
                  "latest_price_flags": ["preco_extremo"] if price == 5.89 else []} for i, price in enumerate(chosen)]
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None, "product": product, "total": total,
                "latest_week_start": "2026-09-27", "page": 1, "page_size": size, "items": items}

    def brands(self, product, municipality=None):
        items = [] if self.over.get("no_brands") else [
            {"brand": "BRANCA", "stations": 12, "observations": 12, "median": 6.19, "mean": 6.2, "min": 5.89,
             "max": 6.49, "difference_to_reference": -0.2},
            {"brand": "IPIRANGA", "stations": 9, "observations": 9, "median": 6.49, "mean": 6.5, "min": 6.29,
             "max": 6.79, "difference_to_reference": 0.1},
            {"brand": "RAIZEN", "stations": 7, "observations": 7, "median": 6.59, "mean": 6.6, "min": 6.39,
             "max": 6.89, "difference_to_reference": 0.2}]
        return {"data_as_of": "2026-10-09", "source_retrieved_at": None,
                "location": {"uf": "SP", "municipality": municipality}, "product": product, "unit": "BRL/L",
                "week_start": "2026-10-04", "week_end": "2026-10-10", "reference_median": 6.39,
                "reference_stations": 30, "min_stations": 3, "hidden_brands": 2, "hidden_stations": 4, "items": items}

    def forecasts(self, product, municipality=None):
        if "forecast_raises" in self.over:
            raise self.over["forecast_raises"]
        model = {"name": "ultimo_valor", "label": "Último valor observado", "kind": "baseline",
                 "version": "2026-10-04-1a3225c5", "status": "approved", "origin_week_start": "2026-10-04",
                 "created_at": "2026-10-12T01:00:00Z",
                 "backtest": {"points": 24481, "origins": 27,
                              "published": {"mae": 0.1064, "weighted_mae": 0.0812, "bias": -0.0173,
                                            "interval_coverage": 0.753, "interval_width": 0.284},
                              "best_baseline": "ultimo_valor", "best_baseline_label": "Último valor observado",
                              "candidate": {"mae": 0.112, "weighted_mae": 0.0876, "bias": -0.0112,
                                            "interval_coverage": 0.766, "interval_width": 0.309},
                              "candidate_approved": False, "candidate_change": 0.0788,
                              "checks": {"melhora_minima_de_5pct_no_mae_ponderado": False,
                                         "cobertura_do_intervalo_na_faixa": True}}}
        base = {"data_as_of": "2026-10-09", "source_retrieved_at": "2026-10-12T00:06:34Z",
                "location": {"uf": "SP", "municipality": municipality}, "product": product, "unit": "BRL/L",
                "model": model, "origin_week_start": "2026-10-04", "interval_level": 0.8}
        if "forecast_reasons" in self.over:
            return {**base, "eligible": False, "reasons": self.over["forecast_reasons"], "history_weeks": 20,
                    "items": []}
        items = [{"horizon": h, "target_week_start": f"2026-10-{4 + 7 * h:02d}" if h < 4 else "2026-11-01",
                  "target_week_end": "2026-10-17", "point": 6.39, "lower": 6.39 - 0.1 * h, "upper": 6.39 + 0.1 * h}
                 for h in (1, 2, 3, 4)]
        items[0]["target_week_start"], items[1]["target_week_start"] = "2026-10-11", "2026-10-18"
        items[2]["target_week_start"] = "2026-10-25"
        return {**base, "eligible": True, "reasons": [], "history_weeks": 160, "items": items}

    def anomalies(self, product=None, municipality=None, weeks=4):
        rows = [{"location": {"uf": "SP", "municipality": place}, "product": "GASOLINA_COMUM",
                 "week_start": "2026-10-04", "week_end": "2026-10-10", "observed": 6.89, "expected": 6.29,
                 "lower": 6.09, "upper": 6.49, "difference": 0.6, "direction": "acima", "stations": 8,
                 "interval_level": 0.99} for place in ("CAMPINAS", None)]
        if "anomaly_rows" in self.over:
            rows = self.over["anomaly_rows"]
        return {"data_as_of": "2026-10-09", "source_retrieved_at": None, "model_version": "ultimo_valor 2026-10-04-x",
                "since_week_start": "2026-09-13", "page": 1, "page_size": 200, "total": len(rows), "items": rows}

    def ethanol(self, municipality=None, weeks=26):
        if self.over.get("ethanol_missing"):
            raise ApiError(404, "NO_DATA", "Sem dados.")
        ratios = self.over.get("ethanol_ratios", [0.66, 0.68, 0.72])
        items = [{"week_start": (date(2026, 9, 13) + timedelta(weeks=i)).isoformat(), "gasoline_median": 6.0,
                  "ethanol_median": 6.0 * r if r else None, "ratio": r, "pays": None if r is None else r <= 0.70,
                  "reason": None if r else "MISSING_PRODUCT"} for i, r in enumerate(ratios)]
        latest = next((i for i in reversed(items) if i["ratio"] is not None), None)
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None,
                "location": {"uf": "SP", "municipality": municipality}, "threshold": 0.70, "latest": latest,
                "items": items}

    def station_choice(self, product, municipality):
        latest = None if self.over.get("few_stations") else {
            "week_start": "2026-09-27", "week_end": "2026-10-03", "stations": 25, "median": 6.29, "min": 5.89,
            "p25": 6.09, "p75": 6.49, "saving": 0.40, "saving_tank": 20.0}
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None,
                "location": {"uf": "SP", "municipality": municipality}, "product": product, "unit": "BRL/L",
                "min_stations": 5, "tank_liters": 50, "latest": latest,
                "typical_saving": None if latest is None else 0.40, "typical_weeks": 0 if latest is None else 52,
                "typical_change": None if latest is None else 0.10}

    def regions(self, product, weeks=26):
        medians = {"capital": 6.29, "metropolitana": 6.39, "litoral": 6.79, "interior": 6.35}
        present = self.over.get("regions_present", list(medians))
        items = [{"week_start": "2026-09-27", "region": r, "label": views.REGION_LABELS[r], "median": medians[r],
                  "observations": 40, "stations": 40, "municipalities": 1 if r == "capital" else 5,
                  "difference_to_capital": (None if r == "capital" or "capital" not in present
                                            else round(medians[r] - medians["capital"], 4)),
                  "municipality_names": ["SAO PAULO"] if r == "capital" else ["A", "B", "C", "D", "E"]}
                 for r in medians if r in present]
        series = [{"week_start": w, "region": i["region"], "median": i["median"], "observations": 40, "stations": 40,
                   "municipalities": i["municipalities"]} for w in ("2026-09-20", "2026-09-27") for i in items]
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None, "product": product,
                "unit": "BRL/M3" if product == "GNV" else "BRL/L", "week_start": "2026-09-27",
                "week_end": "2026-10-03", "items": items, "series": series}

    def rankings(self, product, weeks=26):
        def item(name, region, share, ratio, saving, ranked=True):
            return {"location": {"uf": "SP", "municipality": name}, "region": region,
                    "ethanol": {"weeks": 26 if ranked else 3, "share_pays": share, "median_ratio": ratio,
                                "latest_ratio": ratio, "latest_week_start": "2026-09-27", "ranked": ranked},
                    "station_choice": {"weeks": 26 if ranked else 3, "typical_saving": saving,
                                       "latest_saving": saving, "latest_week_start": "2026-09-27", "ranked": ranked}}
        items = self.over.get("ranking_items", [
            item("CAMPINAS", "interior", 0.9, 0.66, 0.40), item("SANTOS", "litoral", 0.5, 0.70, 0.80),
            item("JUNDIAI", "interior", 0.9, 0.62, 0.30), item("SAO PAULO", "capital", 0.2, 0.72, 0.55),
            item("TIETE", "interior", 1.0, 0.55, 1.50, ranked=False)])
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None, "product": product,
                "unit": "BRL/M3" if product == "GNV" else "BRL/L", "start": "2026-04-05", "end": "2026-09-27",
                "weeks": 26, "min_weeks": 13, "threshold": 0.70, "min_stations": 5, "tank_liters": 50, "items": items}

    def margins(self, product, municipality=None, weeks=52):
        if self.over.get("no_margin"):
            items = [{"week_start": "2026-09-27", "retail_median": 6.39, "distribution": None, "margin": None,
                      "stations": 25, "reason": "NO_DISTRIBUTION"}]
        else:
            items = [{"week_start": w, "retail_median": 6.38, "distribution": 5.45, "margin": 0.93, "stations": 25,
                      "reason": None} for w in ("2026-08-16", "2026-08-23")]
            items.append({"week_start": "2026-08-30", "retail_median": 6.39, "distribution": None, "margin": None,
                          "stations": 25, "reason": "NO_DISTRIBUTION"})
        with_margin = [i for i in items if i["margin"] is not None]
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None,
                "location": {"uf": "SP", "municipality": municipality}, "product": product, "unit": "BRL/L",
                "note": "Não é lucro.", "distribution_latest_week": "2026-08-23" if with_margin else None,
                "latest": with_margin[-1] if with_margin else None, "items": items}

    def margin_municipalities(self, product):
        items = [{"location": {"uf": "SP", "municipality": n}, "retail_median": 6.4, "distribution": 5.4,
                  "margin": m, "stations": 8, "low_coverage": n == "SANTOS"}
                 for n, m in (("SANTOS", 1.2), ("CAMPINAS", 0.9))]
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None, "product": product, "unit": "BRL/L",
                "note": "", "week_start": "2026-08-23", "week_end": "2026-08-29", "state": None, "items": items}

    def margin_stations(self, product, municipality):
        items = [{"cnpj": "00000000000191", "name": "POSTO A", "legal_name": "POSTO A LTDA", "brand": "IPIRANGA",
                  "address": "RUA A", "neighborhood": "CENTRO", "price": 6.09, "collection_date": "2026-08-25",
                  "estimated_margin": 0.64, "extreme": False}]
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None,
                "location": {"uf": "SP", "municipality": municipality}, "product": product, "unit": "BRL/L",
                "note": "", "week_start": "2026-08-23", "week_end": "2026-08-29", "distribution": 5.45,
                "retail_median": 6.38, "items": items}

    def data_quality(self, week_start=None):
        return {"data_as_of": "2026-10-01", "source_retrieved_at": None,
                "last_load": self.freshness()["last_load"],
                "observations": {"observations_published": 179699, "observations_with_warning": 1021,
                                 "warning_counts": {"preco_extremo": 1021}, "observations_quarantined": 0,
                                 "quarantine_reasons": {}},
                "coverage": {"week_start": "2026-09-27", "series": 520, "ok": 480, "low": 3, "no_history": 37},
                "low_coverage": {"page": 1, "page_size": 200, "total": 3, "items": [
                    {"location": {"uf": "SP", "municipality": "IBITINGA"}, "product": "GASOLINA_COMUM", "stations": 2,
                     "baseline_median_stations": 7.5, "coverage_ratio": 0.267}]}}


class PageCase(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        st.cache_resource.clear()

    def run_page(self, script, api, query=None):
        with mock.patch.object(views, "make_client", return_value=api):
            at = AppTest.from_string(script, default_timeout=30)
            for key, value in (query or {}).items():
                at.query_params[key] = value
            at.run()
        return at

    @staticmethod
    def text_of(at):
        parts = []
        for kind in ("markdown", "caption", "warning", "info", "error", "success", "title", "subheader"):
            parts += [e.value for e in getattr(at, kind)]
        for metric in at.metric:
            parts += [metric.label, str(metric.value), str(metric.delta or "")]
        return "\n".join(str(p) for p in parts)


class HomePageTests(PageCase):
    def test_home_shows_dates_state_table_coverage_and_the_survey_notice(self):
        at = self.run_page(HOME, FakeApi())
        self.assertFalse(at.exception)
        text = self.text_of(at)
        self.assertIn("pesquisa semanal da ANP", text)
        self.assertIn("27/09/2026 a 03/10/2026", text)
        self.assertIn("01/10/2026", text)
        row = at.dataframe[0].value.iloc[0]
        # As células guardam o valor tipado; o texto brasileiro é só exibição (ver TypedTableTests).
        self.assertAlmostEqual(row["Mediana"], 6.29)
        self.assertAlmostEqual(row["Variação semanal"], -0.0156)
        self.assertEqual(row["Municípios com cobertura baixa"], 3)
        self.assertEqual(len(at.dataframe[0].value), 2)  # dois produtos
        values = {m.label: m.value for m in at.metric}
        self.assertEqual((values["Cobertura baixa"], values["Séries (município × produto)"]), ("3", "520"))
        # Cartões estreitos mostram só a data; o instante completo fica na ajuda do cartão.
        self.assertEqual(values["Arquivo baixado em"], "08/10/2026")
        self.assertEqual(values["Semana mais recente (início)"], "27/09/2026")
        self.assertEqual(len(at.warning), 0)

    def test_home_warns_about_stale_data_and_failed_load(self):
        fresh = {"age_days": 30, "last_load": {**FakeApi().freshness()["last_load"], "status": "failed"}}
        at = self.run_page(HOME, FakeApi(fresh=fresh))
        warnings = " ".join(w.value for w in at.warning)
        self.assertIn("30 dias", warnings)
        self.assertIn("falhou", warnings)

    def test_missing_download_record_is_stated_not_hidden(self):
        at = self.run_page(HOME, FakeApi(fresh={"source_retrieved_at": None}))
        values = {m.label: m.value for m in at.metric}
        self.assertEqual(values["Arquivo baixado em"], "sem registro")
        helps = " ".join(m.help or "" for m in at.metric)
        self.assertIn("sem registro de download", helps)

    def test_every_page_credits_the_anp_even_when_the_api_fails(self):
        for at in (self.run_page(HOME, FakeApi()),
                   self.run_page(EXPLORE, FakeApi(latest_raises=ApiUnavailable("A API não respondeu.")))):
            captions = " ".join(c.value for c in at.caption)
            self.assertIn("Levantamento de Preços de Combustíveis da ANP", captions)
            self.assertIn("calculados por este projeto", captions)


class RefuelSectionTests(PageCase):
    """Marco 8b: economia de escolher o posto e etanol × gasolina, na página do município e na inicial."""

    def test_saving_tank_comparison_and_ethanol_verdict(self):
        at = self.run_page(EXPLORE, FakeApi(ethanol_ratios=[0.66, 0.68]),
                           {"municipio": "CAMPINAS", "produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        self.assertEqual({m.label: m.value for m in at.metric}["Mais barato frente à mediana"], "R$ 0,40")
        captions = " ".join(c.value for c in at.caption)
        self.assertIn(r"R\$ 20,00 num tanque de 50 L", captions)     # cifrão escapado: não vira fórmula
        self.assertIn("**4,0 vezes**", captions)
        success = " ".join(s.value for s in at.success)
        self.assertIn("Etanol compensa:** custa 68,0%", success)        # a semana mais recente
        self.assertNotIn("nas semanas seguintes falta", captions)

    def test_gasoline_wins_when_ethanol_is_above_70_percent(self):
        at = self.run_page(EXPLORE, FakeApi(ethanol_ratios=[0.66, 0.74]), {"municipio": "CAMPINAS"})
        self.assertIn("Gasolina compensa:** o etanol custa 74,0%", " ".join(i.value for i in at.info))
        self.assertEqual(len(at.warning), 0)  # não é alerta: amarelo fica para dado velho e falhas

    def test_latest_ratio_from_an_older_week_is_said(self):
        at = self.run_page(EXPLORE, FakeApi(ethanol_ratios=[0.66, None]), {"municipio": "CAMPINAS"})
        self.assertIn("nas semanas seguintes falta um dos preços", " ".join(c.value for c in at.caption))

    def test_few_stations_and_no_ethanol_are_explained_not_errors(self):
        at = self.run_page(EXPLORE, FakeApi(few_stations=True, ethanol_missing=True), {"municipio": "CAMPINAS"})
        self.assertFalse(at.exception)
        self.assertEqual(len(at.error), 0)
        infos = " ".join(i.value for i in at.info)
        self.assertIn("Poucos postos pesquisados", infos)
        self.assertIn("Sem preços de etanol e gasolina comum", infos)

    def test_home_shows_the_state_ethanol_verdict(self):
        at = self.run_page(HOME, FakeApi(ethanol_ratios=[0.65]))
        self.assertIn("No estado (semana de 13/09/2026 a 19/09/2026): **Etanol compensa:**",
                      " ".join(s.value for s in at.success))


class ExplorePageTests(PageCase):
    def test_explore_cards_caption_tables_and_downloads(self):
        at = self.run_page(EXPLORE, FakeApi(), {"municipio": "CAMPINAS", "produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        metrics = {m.label: m for m in at.metric}
        self.assertEqual(metrics["Mediana"].value, "R$ 6,29")
        self.assertEqual(metrics["Mediana"].delta, "−1,6%")
        self.assertEqual(metrics["Média"].value, "R$ 6,27")
        self.assertEqual(metrics["Faixa (R$)"].value, "5,87 a 6,95")  # sem `$` no valor: o Streamlit leria LaTeX
        self.assertTrue(metrics["Mediana frente ao estado"].value.startswith(("+R$", "−R$", "R$")))
        text = self.text_of(at)
        self.assertIn("27/09/2026 a 03/10/2026", text)
        self.assertIn("25** observações em **25** postos", text)
        self.assertIn("R$/litro", text)
        self.assertEqual(len(at.get("plotly_chart")), 2)  # histórico + etanol × gasolina
        stations = at.dataframe[-1].value
        self.assertAlmostEqual(list(stations["Último preço"])[0], 6.01)
        self.assertEqual(pd.Timestamp(list(stations["Data do preço"])[0]).date(), date(2026, 9, 28))
        self.assertEqual(list(stations["Aviso"])[0], "preço extremo")
        self.assertEqual(len(at.get("download_button")), 2)
        self.assertEqual(at.query_params["municipio"], "CAMPINAS")

    def test_station_dates_reach_the_table_as_real_dates(self):
        dates = ["2026-08-31", "2026-08-31", "2026-03-31", "2026-09-30", "2026-09-30"]
        at = self.run_page(EXPLORE, FakeApi(station_dates=dates), {"municipio": "CAMPINAS"})
        self.assertFalse(at.exception)
        column = at.dataframe[-1].value["Data do preço"]
        shown = [pd.Timestamp(v).date() for v in column]
        self.assertEqual(sorted(shown), [date(2026, 3, 31), date(2026, 8, 31), date(2026, 8, 31),
                                         date(2026, 9, 30), date(2026, 9, 30)])
        self.assertNotIn(str, {type(v) for v in column})  # nada de texto "31/08/2026" para ordenar

    def test_low_coverage_week_is_flagged_and_change_is_not_shown(self):
        api = FakeApi(latest={"sample": sample("low", 2, 2, 0.25, 8.0),
                              "weekly_change": {"value": None, "previous_week_start": "2026-09-20", "reason": "LOW_COVERAGE"}})
        at = self.run_page(EXPLORE, api, {"municipio": "JUNDIAI"})
        warnings = " ".join(w.value for w in at.warning)
        self.assertIn("Cobertura baixa", warnings)
        self.assertIn("25%", warnings)
        mediana = next(m for m in at.metric if m.label == "Mediana")
        self.assertFalse(mediana.delta)
        self.assertIn("N/D (cobertura insuficiente)", self.text_of(at))

    def test_series_that_stopped_is_warned(self):
        at = self.run_page(EXPLORE, FakeApi(latest={"is_dataset_latest_week": False, "week_start": "2026-08-09",
                                                    "week_end": "2026-08-15"}), {"municipio": "SANTOS"})
        self.assertIn("não tem dados na semana mais recente", " ".join(w.value for w in at.warning))

    def test_api_error_is_shown_with_code_and_request_id(self):
        error = ApiError(404, "NO_DATA", "Não há preços publicados para este recorte.", "req-9")
        at = self.run_page(EXPLORE, FakeApi(latest_raises=error))
        self.assertFalse(at.exception)
        self.assertIn("Não há preços publicados", at.error[0].value)
        self.assertIn("NO_DATA", " ".join(c.value for c in at.caption))
        self.assertIn("req-9", " ".join(c.value for c in at.caption))

    def test_unavailable_api_is_a_friendly_message(self):
        at = self.run_page(EXPLORE, FakeApi(latest_raises=ApiUnavailable("A API não respondeu em http://x.")))
        self.assertFalse(at.exception)
        self.assertIn("Não foi possível consultar a API", at.error[0].value)
        self.assertIn("RADAR_API_URL", at.error[0].value)


class RankingPageTests(PageCase):
    def test_lists_five_cheapest_and_five_priciest_with_dates_and_week_rule(self):
        at = self.run_page(RANKING, FakeApi(), {"municipio": "CAMPINAS", "produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        cheapest, priciest = at.dataframe[0].value, at.dataframe[1].value
        self.assertEqual(list(cheapest["Preço"]), [5.89, 5.95, 5.99, 6.05, 6.09])
        self.assertEqual(list(priciest["Preço"]), [6.99, 6.79, 6.65, 6.59, 6.55])
        self.assertEqual(list(cheapest["Posição"]), [1, 2, 3, 4, 5])
        self.assertEqual(pd.Timestamp(list(cheapest["Data do preço"])[0]).date(), date(2026, 9, 30))
        self.assertEqual(list(cheapest["Aviso"])[0], "preço extremo")
        text = self.text_of(at)
        self.assertIn("27/09/2026 a 03/10/2026", text)
        self.assertIn("semana mais recente", text)
        self.assertIn("12** posto(s)", text)
        self.assertIn("Preço extremo", text)

    def test_city_without_current_prices_says_so_instead_of_listing_old_ones(self):
        at = self.run_page(RANKING, FakeApi(ranking_total=0), {"municipio": "JUNDIAI"})
        self.assertFalse(at.exception)
        self.assertEqual(len(at.dataframe), 0)
        self.assertIn("Nenhum posto de Jundiai", " ".join(w.value for w in at.warning))

    def test_tiny_sample_is_flagged(self):
        at = self.run_page(RANKING, FakeApi(ranking_total=2), {"municipio": "SANTOS"})
        self.assertIn("menos de 3 postos", " ".join(i.value for i in at.info))

    def test_overlap_between_the_two_lists_is_explained(self):
        at = self.run_page(RANKING, FakeApi(ranking_total=7), {"municipio": "SANTOS"})
        self.assertIn("em comum", self.text_of(at))


class BrandsPageTests(PageCase):
    def test_brand_table_chart_and_the_price_is_not_quality_notice(self):
        at = self.run_page(BRANDS, FakeApi(), {"municipio": "CAMPINAS"})
        self.assertFalse(at.exception)
        table = at.dataframe[0].value
        self.assertEqual(list(table["Bandeira"]), ["BRANCA", "IPIRANGA", "RAIZEN (Shell)"])
        self.assertAlmostEqual(list(table["Diferença p/ todos"])[0], -0.2)
        self.assertEqual(len(at.get("plotly_chart")), 1)
        text = self.text_of(at) + " ".join(i.value for i in at.info)
        self.assertIn("Preço não é qualidade", text)
        self.assertIn("a marca **Shell**", text)
        labels = json.loads(at.get("plotly_chart")[0].proto.spec)["data"][0]["y"]
        self.assertIn("RAIZEN (Shell) · 7 postos", labels)
        self.assertIn("2 bandeira(s) com menos de 3 postos", text)
        self.assertNotIn("adulter", text.lower())

    def test_no_reliable_brand_says_so(self):
        at = self.run_page(BRANDS, FakeApi(no_brands=True), {"municipio": "SANTOS"})
        self.assertFalse(at.exception)
        self.assertEqual(len(at.get("plotly_chart")), 0)
        self.assertIn("não há comparação confiável", " ".join(i.value for i in at.info))


class ForecastPageTests(PageCase):
    def test_forecast_shows_numbers_interval_chart_and_the_honest_model_notice(self):
        at = self.run_page(FORECAST, FakeApi(), {"municipio": "CAMPINAS", "produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        table = at.dataframe[0].value
        self.assertEqual(list(table["Horizonte"]), ["1 semana(s)", "2 semana(s)", "3 semana(s)", "4 semana(s)"])
        self.assertTrue(all(table["Mínimo"] <= table["Previsão"]) and all(table["Previsão"] <= table["Máximo"]))
        self.assertEqual(len(at.get("plotly_chart")), 1)
        text = self.text_of(at) + " ".join(i.value for i in at.info)
        self.assertIn("Último valor observado", text)
        self.assertIn("não foi aprovado", text)          # o candidato foi rejeitado e a página diz isso
        self.assertIn("24.481", text)                    # amostra do backtest
        self.assertIn("75%", text)                       # cobertura real do intervalo
        self.assertNotIn("garantia de", text)
        labels = {m.label for m in at.metric}
        self.assertTrue(any(label.startswith("Em 1 semana") for label in labels))

    def test_ineligible_series_shows_reasons_and_no_numbers(self):
        api = FakeApi(forecast_reasons=["menos_de_52_semanas_de_historico", "mediana_de_postos_abaixo_de_3"])
        at = self.run_page(FORECAST, api, {"municipio": "SANTOS"})
        self.assertFalse(at.exception)
        self.assertEqual(len(at.dataframe), 0)
        self.assertEqual(len(at.get("plotly_chart")), 0)
        warning = " ".join(w.value for w in at.warning)
        self.assertIn("menos de 52 semanas de histórico", warning)
        self.assertIn("menos de 3 postos", warning)

    def test_state_is_the_default_place(self):
        at = self.run_page(FORECAST, FakeApi(), {})
        self.assertFalse(at.exception)
        self.assertEqual(at.query_params["municipio"], "ESTADO DE SÃO PAULO")

    def test_missing_model_is_a_readable_message(self):
        from radar_combustiveis.dashboard.client import ApiError
        api = FakeApi(forecast_raises=ApiError(404, "NO_PUBLISHED_MODEL", "Ainda não há modelo.", "rid"))
        at = self.run_page(FORECAST, api, {})
        self.assertFalse(at.exception)
        self.assertIn("Ainda não há modelo", " ".join(e.value for e in at.error))


class AnomaliesPageTests(PageCase):
    def test_lists_unusual_variations_with_statistical_wording(self):
        at = self.run_page(ANOMALIES, FakeApi())
        self.assertFalse(at.exception)
        table = at.dataframe[0].value
        self.assertEqual(len(table), 2)
        self.assertAlmostEqual(list(table["Diferença"])[0], 0.6)
        self.assertEqual(list(table["Local"]), ["CAMPINAS", "Estado de São Paulo"])
        self.assertEqual(list(table["Sentido"]), ["acima", "acima"])
        text = self.text_of(at)
        self.assertIn("sinal estatístico", text)
        self.assertIn("não uma conclusão sobre os postos", text)
        self.assertNotIn("fraude", text.lower())
        self.assertNotIn("adulter", text.lower())

    def test_empty_period_says_so(self):
        at = self.run_page(ANOMALIES, FakeApi(anomaly_rows=[]))
        self.assertFalse(at.exception)
        self.assertIn("Nenhuma variação incomum", " ".join(i.value for i in at.info))
        self.assertEqual(len(at.dataframe), 0)


class ModelSectionTests(PageCase):
    def test_quality_page_reports_the_validation_and_the_rejected_candidate(self):
        at = self.run_page(QUALITY, FakeApi())
        self.assertFalse(at.exception)
        text = self.text_of(at)
        self.assertIn("Modelo de previsão e validação", text)
        self.assertIn("não foi aprovado", text)
        self.assertIn("❌", text)
        self.assertIn("✅", text)

    def test_quality_page_without_a_published_model_still_renders(self):
        from radar_combustiveis.dashboard.client import ApiError
        api = FakeApi(forecast_raises=ApiError(404, "NO_PUBLISHED_MODEL", "Ainda não há modelo.", "rid"))
        at = self.run_page(QUALITY, api)
        self.assertFalse(at.exception)
        self.assertIn("Ainda não há modelo de previsão publicado", " ".join(i.value for i in at.info))


class ComparePageTests(PageCase):
    def test_compare_table_ranks_and_reference_row(self):
        at = self.run_page(COMPARE, FakeApi(), {"produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        table = at.table[0].value
        self.assertEqual(list(table["Município"])[-1], "ESTADO DE SP (referência)")
        self.assertEqual([int(v) for v in list(table["Posição"])[:3]], [1, 2, 3])
        self.assertEqual(len(at.get("plotly_chart")), 2)  # absoluto e índice
        self.assertIn("vale 100", " ".join(c.value for c in at.caption))

    def test_low_coverage_city_has_no_rank_and_a_warning(self):
        at = self.run_page(COMPARE, FakeApi(low_city="CAMPINAS"), {"produto": "GASOLINA_COMUM"})
        table = at.table[0].value
        row = table[table["Município"] == "CAMPINAS"].iloc[0]
        self.assertTrue(pd.isna(row["Posição"]))  # sem posição; a tela mostra "—"
        html = at.table[0].proto.html if hasattr(at.table[0].proto, "html") else ""
        self.assertNotIn(">None<", html)
        self.assertEqual(row["Cobertura"], "Cobertura baixa")
        self.assertIn("cobertura baixa", " ".join(w.value for w in at.warning).lower())

    def test_fewer_than_two_municipalities_asks_for_more(self):
        at = self.run_page(COMPARE, FakeApi())
        at.multiselect[0].set_value(["CAMPINAS"]).run()
        self.assertFalse(at.exception)
        self.assertIn("pelo menos dois", " ".join(i.value for i in at.info))
        self.assertEqual(len(at.get("plotly_chart")), 0)


class RegionsPageTests(PageCase):
    def test_region_cards_table_and_chart_compare_with_the_capital(self):
        at = self.run_page(REGIONS, FakeApi(), {"produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        metrics = {m.label: (m.value, m.delta) for m in at.metric}
        self.assertEqual(metrics["Capital"], ("R$ 6,29", ""))
        self.assertEqual(metrics["Litoral"], ("R$ 6,79", "+R$ 0,50 frente à capital"))
        table = at.dataframe[0].value
        self.assertEqual(list(table["Região"]), ["Capital", "Metropolitana", "Litoral", "Interior"])
        self.assertEqual(table.iloc[0]["Diferença p/ capital"], 0.0)  # vazio apareceria como "None"
        self.assertIn("27/09/2026 a 03/10/2026", " ".join(c.value for c in at.caption))

    def test_rankings_are_ordered_and_skip_municipalities_without_enough_weeks(self):
        at = self.run_page(REGIONS, FakeApi(), {"produto": "GASOLINA_COMUM"})
        ethanol, choice = at.dataframe[1].value, at.dataframe[3].value
        # Mesma fração: desempata pela menor razão. Tietê tem poucas semanas e fica de fora.
        self.assertEqual(list(ethanol["Município"]), ["JUNDIAI", "CAMPINAS", "SANTOS", "SAO PAULO"])
        self.assertEqual(list(ethanol["Posição"]), [1, 2, 3, 4])
        self.assertEqual(list(choice["Município"]), ["SANTOS", "SAO PAULO", "CAMPINAS", "JUNDIAI"])
        self.assertAlmostEqual(choice.iloc[0]["Num tanque de 50 L"], 40.0)
        self.assertEqual(choice.iloc[0]["Região"], "Litoral")
        captions = " ".join(c.value for c in at.caption)
        self.assertIn("pelo menos 13 semanas: 4 municípios", captions)
        self.assertIn("05/04/2026 a 27/09/2026", captions)

    def test_missing_region_and_product_without_liters(self):
        at = self.run_page(REGIONS, FakeApi(regions_present=["litoral", "interior"]), {"produto": "GNV"})
        self.assertFalse(at.exception)
        metrics = {m.label: (m.value, m.delta) for m in at.metric}
        self.assertEqual(metrics["Capital"][0], fmt.ND)
        self.assertEqual(metrics["Litoral"], ("R$ 6,79", ""))  # sem capital, sem diferença
        self.assertNotIn("Num tanque de 50 L", at.dataframe[-1].value.columns)

    def test_no_ranked_municipality_is_explained(self):
        at = self.run_page(REGIONS, FakeApi(ranking_items=[]))
        self.assertFalse(at.exception)
        infos = " ".join(i.value for i in at.info)
        self.assertIn("Nenhum município tem semanas suficientes com preços de etanol", infos)
        self.assertIn("Nenhum município tem semanas suficientes com postos", infos)


class MarginsPageTests(PageCase):
    def test_state_view_shows_the_latest_week_with_both_prices_and_neutral_wording(self):
        at = self.run_page(MARGINS, FakeApi())
        self.assertFalse(at.exception)
        metrics = {m.label: (m.value, m.delta) for m in at.metric}
        self.assertEqual(metrics["Margem bruta estimada"], ("R$ 0,93", "15% do preço"))
        self.assertEqual(metrics["Distribuição (média)"][0], "R$ 5,45")
        markdown = " ".join(m.value for m in at.markdown)
        self.assertIn("Segundo os dados da ANP, no estado de São Paulo, a margem bruta", markdown)
        self.assertIn("**não é lucro**", markdown)
        self.assertNotIn("lucro de", markdown.lower())
        captions = " ".join(c.value for c in at.caption)
        self.assertIn("a distribuição vai até 23/08/2026", captions)
        self.assertIn("Preços de distribuição de combustíveis da ANP", captions)
        cities = at.dataframe[-1].value
        self.assertEqual(list(cities["Município"]), ["CAMPINAS", "SANTOS"])
        self.assertEqual(list(cities["Cobertura"]), ["normal", "baixa"])

    def test_municipality_view_lists_station_estimates(self):
        at = self.run_page(MARGINS, FakeApi(), {"municipio": "CAMPINAS", "produto": "GASOLINA_COMUM"})
        self.assertFalse(at.exception)
        self.assertIn("Segundo os dados da ANP, em CAMPINAS", " ".join(m.value for m in at.markdown))
        stations = at.dataframe[-1].value
        self.assertAlmostEqual(stations.iloc[0]["Margem bruta estimada"], 0.64)
        self.assertEqual(stations.iloc[0]["Bandeira"], "IPIRANGA")
        self.assertIn("custo real de compra de cada posto não é público", " ".join(c.value for c in at.caption))

    def test_without_distribution_it_says_so_and_gnv_is_not_offered(self):
        at = self.run_page(MARGINS, FakeApi(no_margin=True), {"produto": "GNV"})
        self.assertFalse(at.exception)
        self.assertIn("Sem semana com preço nos postos e de distribuição", " ".join(i.value for i in at.info))
        self.assertNotIn("GNV", at.selectbox[1].options)


class StudyPageTests(PageCase):
    """A página Estudo lê os relatórios congelados de reports/study/, não a API."""

    def test_frozen_results_with_window_findings_and_gate(self):
        api = FakeApi()
        at = self.run_page(STUDY, api)
        self.assertFalse(at.exception)
        self.assertEqual(api.calls, [])  # nada vem da API
        metrics = {m.label: (m.value, m.delta) for m in at.metric}
        results = json.loads((ROOT / "reports" / "study" / "resultados.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["Q1 · bandeira branca"], (fmt.percent(results["q1"]["primary"]["pct"] / 100),
                                                           "✅ estável"))
        self.assertEqual(metrics["Q2 · altas × quedas"][1], "❌ não estável")
        self.assertEqual(metrics["Q3 · reajustes se espalham?"][1], "❌ não estável")
        self.assertEqual(metrics["Escolher o posto economiza"][0], "R$ 0,40")
        info = " ".join(i.value for i in at.info)
        self.assertIn("13/11/2022 a 29/03/2026", info)
        self.assertIn("não mudam", info)
        captions = " ".join(c.value for c in at.caption)
        self.assertIn("Gate G1 não passou:** 1 de 3", captions)
        self.assertIn("reports/study/q1.md", captions)
        markdown = " ".join(m.value for m in at.markdown)
        self.assertIn("R\\$ 0,12", markdown)  # Q2 tem três valores em reais: cifrão escapado
        self.assertNotIn(" R$ ", markdown.replace("R\\$", ""))
        self.assertEqual(len(at.get("plotly_chart")), 2)

    def test_missing_reports_are_a_readable_error(self):
        with mock.patch.object(views.study_results, "REPORTS", ROOT / "nao-existe"):
            at = self.run_page(STUDY, FakeApi())
        self.assertFalse(at.exception)
        self.assertIn("não foram encontrados", at.error[0].value)


class QualityPageTests(PageCase):
    def test_quality_page_lists_coverage_and_limitations_honestly(self):
        at = self.run_page(QUALITY, FakeApi())
        self.assertFalse(at.exception)
        text = self.text_of(at)
        self.assertIn("Levantamento de Preços de Combustíveis", text)
        self.assertIn("179.699", text)
        coverage = next(f.value for f in at.dataframe if "Município" in f.value.columns)
        self.assertIn("IBITINGA", [str(v) for v in coverage["Município"]])
        self.assertIn("pesquisa por amostragem", text)
        self.assertIn("não indica irregularidade de postos", text)  # variação incomum não acusa ninguém
        self.assertNotIn("Não há previsões", text)                   # agora existem; a página não mente o contrário
        self.assertNotIn("http://api.test/docs", "")  # (link é caption; conferido abaixo)
        self.assertIn("http://api.test/docs", " ".join(c.value for c in at.caption))


# -- Integração: painel sobre a API real ----------------------------------------------------


class DashboardIntegrationTests(ApiCase):
    """Mesmos dados sintéticos de tests/test_api.py, lidos pelo painel através da API de verdade."""

    def setUp(self):
        st.cache_data.clear()
        st.cache_resource.clear()
        self.api = ApiClient(self.client)

    def run_page(self, script, query=None):
        with mock.patch.object(views, "make_client", return_value=self.api):
            at = AppTest.from_string(script, default_timeout=60)
            for key, value in (query or {}).items():
                at.query_params[key] = value
            at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def municipality_name(self, wanted):
        from radar_combustiveis.ingestion.normalize import normalize_text
        names = [loc["municipality"] for loc in self.api.locations()]
        return next(n for n in names if normalize_text(n) == normalize_text(wanted))

    def test_explore_shows_what_the_api_and_the_data_say(self):
        name = self.municipality_name("Campinas")
        at = self.run_page(EXPLORE, {"municipio": name, "produto": "GASOLINA_COMUM"})
        prices = list(self.expected[("Campinas", "GASOLINA_COMUM", 11)].values())
        metrics = {m.label: m.value for m in at.metric}
        import statistics
        self.assertEqual(metrics["Mediana"], fmt.brl(float(statistics.median(prices))))
        self.assertEqual(metrics["Faixa (R$)"], f"{fmt.decimal_br(float(min(prices)))} a {fmt.decimal_br(float(max(prices)))}")
        captions = " ".join(c.value for c in at.caption)
        self.assertIn(fmt.week_range_br(LAST.isoformat()), captions)
        self.assertIn(fmt.date_br(LAST_COLLECTION), captions)
        self.assertIn("**8** observações em **8** postos", captions)
        table = at.dataframe[-1].value
        self.assertEqual(len(table), 8)
        latest_prices = sorted(self.expected[("Campinas", "GASOLINA_COMUM", 11)].values())
        shown = sorted(float(v) for v in table["Último preço"])
        self.assertEqual(shown, [float(p) for p in latest_prices])
        self.assertEqual(len(at.get("download_button")), 2)

    def test_explore_warns_about_low_coverage_and_a_stopped_series(self):
        low = self.run_page(EXPLORE, {"municipio": self.municipality_name("Jundiaí"), "produto": "GASOLINA_COMUM"})
        self.assertIn("Cobertura baixa", " ".join(w.value for w in low.warning))
        stopped = self.run_page(EXPLORE, {"municipio": self.municipality_name("Itu"), "produto": "GASOLINA_COMUM"})
        self.assertIn("não tem dados na semana mais recente", " ".join(w.value for w in stopped.warning))

    def test_compare_ranks_exclude_low_coverage(self):
        names = [self.municipality_name(n) for n in ("Campinas", "Jundiaí", "São Carlos")]
        with mock.patch.object(views, "make_client", return_value=self.api):
            at = AppTest.from_string(COMPARE, default_timeout=60)
            at.query_params["produto"] = "GASOLINA_COMUM"
            at.run()
            at.multiselect[0].set_value(names).run()
        self.assertFalse(at.exception)
        table = at.table[0].value
        by_name = {r["Município"]: r for _, r in table.iterrows()}
        self.assertTrue(pd.isna(by_name[names[1]]["Posição"]))
        self.assertEqual(sorted(int(by_name[n]["Posição"]) for n in (names[0], names[2])), [1, 2])

    def test_regions_page_against_the_real_api(self):
        at = self.run_page(REGIONS, {"produto": "GASOLINA_COMUM"})
        metrics = {m.label: m.value for m in at.metric}
        import statistics
        everything = [p for (city, code, n), prices in self.expected.items()
                      if code == "GASOLINA_COMUM" and n == 11 for p in prices.values()]
        self.assertEqual(metrics["Interior"], fmt.brl(float(statistics.median(everything))))
        self.assertEqual(metrics["Capital"], fmt.ND)  # os dados sintéticos são todos do interior
        # 12 semanas sintéticas não chegam à metade da janela de 26: ninguém entra nos rankings, e a página diz.
        self.assertIn("Nenhum município tem semanas suficientes", " ".join(i.value for i in at.info))
        self.assertIn("pelo menos 13 semanas: 0 municípios", " ".join(c.value for c in at.caption))

    def test_home_and_quality_pages_render_against_the_real_api(self):
        home = self.run_page(HOME)
        values = {m.label: m.value for m in home.metric}
        self.assertEqual(values["Última coleta"], fmt.date_br(LAST_COLLECTION))
        self.assertGreaterEqual(len(home.dataframe[0].value), 3)  # gasolina, etanol e diesel S10 têm dados
        quality = self.run_page(QUALITY)
        from radar_combustiveis.ingestion.normalize import normalize_text
        low = [normalize_text(v) for v in quality.dataframe[-1].value["Município"]]
        self.assertIn("JUNDIAI", low)


if __name__ == "__main__":
    unittest.main()
