"""API de leitura (Marco 5) contra um PostgreSQL real com dados sintéticos.

Exige RADAR_TEST_DATABASE_URL (ver tests/test_database.py) e o httpx, usado pelo TestClient do
FastAPI. O conjunto é carregado uma vez por classe e a API lê com o usuário somente leitura, o
mesmo desenho da execução real. Os valores esperados são calculados aqui, de forma independente,
a partir dos preços gerados. Sem banco ou sem httpx, os testes são ignorados.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import unittest
from unittest import mock
import uuid

try:
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
except ImportError:  # pragma: no cover
    psycopg = None
try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - httpx ausente
    TestClient = None

from tests.test_database import week_name, xrow
from tests.test_ingestion import WEEKLY_HEADER, write_xlsx
from tests.test_quality import make_cnpj

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.api import routes  # noqa: E402
from radar_combustiveis.api.app import create_app  # noqa: E402
from radar_combustiveis.api.database import api_database_url  # noqa: E402
from radar_combustiveis.db.connection import connect  # noqa: E402
from radar_combustiveis.db.load import load_database  # noqa: E402
from radar_combustiveis.db.migrate import apply_migrations  # noqa: E402
from radar_combustiveis.ingestion.normalize import normalize_text  # noqa: E402
from radar_combustiveis.ingestion.pipeline import run_ingestion  # noqa: E402
from radar_combustiveis.quality.pipeline import run_quality  # noqa: E402

TEST_URL = os.environ.get("RADAR_TEST_DATABASE_URL")
WEEK0 = date(2026, 7, 12)  # domingo
N_WEEKS = 12
LAST = WEEK0 + timedelta(weeks=N_WEEKS - 1)  # 2026-09-27
LAST_COLLECTION = LAST + timedelta(days=1)
TODAY = date(2026, 10, 10)


def week(n):
    return WEEK0 + timedelta(weeks=n)


def q2(value):
    return Decimal(str(round(value, 2)))


# nome na fonte -> (estações, semanas, preço por (estação, semana), produto, nome da fonte do produto)
CITIES = {
    "Jundiaí": {"stations": range(1, 9), "weeks": range(N_WEEKS)},
    "Campinas": {"stations": range(30, 38), "weeks": range(N_WEEKS)},
    "São Carlos": {"stations": range(60, 63), "weeks": range(N_WEEKS)},
    "Itu": {"stations": range(50, 53), "weeks": range(0, 5)},        # some depois da semana 4
    "Tietê": {"stations": range(70, 72), "weeks": range(11, 12)},    # só na última semana
}


def gasoline_price(city, s, n):
    return {"Jundiaí": lambda: 5.90 + (s % 5) * 0.07 + n * 0.01,
            "Campinas": lambda: 6.20 + (s % 3) * 0.05 + n * 0.02,
            # Na semana 0 a mediana de São Carlos (6,12) empata com a de Itu: cobre o empate no ranking.
            "São Carlos": lambda: 6.10 + (s % 3) * 0.02 + n * 0.015,
            "Itu": lambda: 6.10 + (s % 3) * 0.02,
            "Tietê": lambda: 6.40 + (s % 2) * 0.10}[city]()


def build_rows():
    """Linhas por semana e o que se espera delas: {(cidade, produto, n): {estação: preço}}."""
    rows, expected = {n: [] for n in range(N_WEEKS)}, {}
    for city, spec in CITIES.items():
        for n in spec["weeks"]:
            monday = week(n) + timedelta(days=1)
            stations = list(spec["stations"])
            if city == "Jundiaí" and n == N_WEEKS - 1:
                stations = stations[:2]  # perde cobertura na última semana
            for s in stations:
                price = q2(gasoline_price(city, s, n))
                expected.setdefault((city, "GASOLINA_COMUM", n), {})[s] = price
                rows[n].append(xrow(s, monday, float(price), city=city))
            extra = {"Jundiaí": ("ETANOL", "ETANOL_HIDRATADO", range(1, 5), lambda s: 4.10 + (s % 3) * 0.03 + n * 0.02),
                     "Campinas": ("DIESEL S10", "DIESEL_S10", range(30, 33), lambda s: 5.80 + n * 0.01)}.get(city)
            if extra:
                source, code, extra_stations, formula = extra
                for s in extra_stations:
                    price = q2(formula(s))
                    expected.setdefault((city, code, n), {})[s] = price
                    rows[n].append(xrow(s, monday, float(price), product=source, city=city))
    return rows, expected


def summary(values):
    values = sorted(values)
    q1, med, q3 = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else (values[0],) * 3
    return {"min": min(values), "p25": q1, "median": med, "mean": statistics.mean(values), "p75": q3, "max": max(values)}


@unittest.skipUnless(TEST_URL and psycopg and TestClient,
                     "RADAR_TEST_DATABASE_URL ou httpx indisponível: testes da API ignorados")
class ApiCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, base, True)
        raw, cls.out, quarantine = base / "raw", base / "processed", base / "quarantine"
        raw.mkdir()
        cls.rows, cls.expected = build_rows()
        for n, rows in cls.rows.items():
            write_xlsx(raw / week_name(week(n)), WEEKLY_HEADER, rows)
        ingestion = run_ingestion(raw, cls.out, quarantine, ("SP",))
        assert ingestion["errors"] == [], ingestion["errors"]
        report = run_quality(cls.out, quarantine, TODAY)
        assert report["decision"] != "bloquear", report["decision"]

        cls.db_name = f"radar_test_api_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{cls.db_name}"')
        cls.addClassCleanup(cls.drop_database, cls.db_name)
        cls.admin_url = make_conninfo(TEST_URL, dbname=cls.db_name)
        with connect(cls.admin_url) as conn:
            apply_migrations(conn)
        load_database(cls.admin_url, cls.out, quarantine)

        with psycopg.connect(cls.admin_url, autocommit=True) as conn:
            # Cada arquivo semanal "baixado" três dias e meio depois do início da semana.
            conn.execute("""UPDATE source_file SET retrieved_at =
                            ((reference_start + 3)::timestamp + interval '12 hours') AT TIME ZONE 'UTC'""")
        cls.role, password = f"radar_api_test_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
        with psycopg.connect(cls.admin_url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE radar_reader").format(
                sql.Identifier(cls.role), sql.Literal(password)))
        cls.addClassCleanup(cls.drop_role, cls.role)
        cls.password = password
        cls.api_url = cls.url_for(cls.db_name)

        cls.app = create_app(cls.api_url)
        cls.client = TestClient(cls.app)
        cls.client.__enter__()
        cls.addClassCleanup(cls.client.__exit__, None, None, None)

    @classmethod
    def url_for(cls, db_name):
        return make_conninfo(TEST_URL, dbname=db_name, user=cls.role, password=cls.password)

    @staticmethod
    def drop_database(name):
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')

    @staticmethod
    def drop_role(name):
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))

    # -- auxiliares ---------------------------------------------------------------------------

    def get(self, path, **params):
        return self.client.get(path, params=params)

    def ok(self, path, **params):
        response = self.get(path, **params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def assertError(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        body = response.json()
        self.assertEqual(set(body), {"error"})
        error = body["error"]
        self.assertEqual(error["code"], code)
        self.assertTrue(error["message"])
        self.assertEqual(error["request_id"], response.headers["x-request-id"])
        return error

    def assertStats(self, got, values):
        want = summary(values)
        for key, value in want.items():
            self.assertAlmostEqual(got[key], float(value), places=4, msg=key)

    def admin_query(self, query, params=()):
        with psycopg.connect(self.admin_url) as conn:
            return conn.execute(query, params).fetchall()

    def values(self, city, product, n):
        return list(self.expected[(city, product, n)].values())

    def state_values(self, product, n):
        return [p for (c, pr, k), prices in self.expected.items() if pr == product and k == n for p in prices.values()]

    @staticmethod
    def make_client(url, **kwargs):
        return TestClient(create_app(url, **kwargs), raise_server_exceptions=False)


class HealthAndMetadataTests(ApiCase):
    def test_live_and_ready(self):
        self.assertEqual(self.ok("/health/live"), {"status": "ok"})
        self.assertEqual(self.ok("/health/ready"), {"status": "ready"})

    def test_ready_is_503_before_any_load_and_data_endpoints_report_no_data(self):
        name = f"radar_test_api_empty_{uuid.uuid4().hex[:8]}"
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{name}"')
        self.addCleanup(self.drop_database, name)
        with connect(make_conninfo(TEST_URL, dbname=name)) as conn:
            apply_migrations(conn)
        with self.make_client(self.url_for(name)) as client:
            self.assertError(client.get("/health/ready"), 503, "NOT_READY")
            self.assertEqual(client.get("/health/live").status_code, 200)
            self.assertError(client.get("/api/v1/prices/latest", params={"product": "GASOLINA_COMUM"}), 404, "NO_DATA")

    def test_database_down_is_503_and_live_stays_up(self):
        with self.make_client("postgresql://radar_api:x@127.0.0.1:1/radar", pool_timeout=1) as client, \
                self.assertLogs("radar.api", "WARNING"):
            self.assertEqual(client.get("/health/live").status_code, 200)
            error = self.assertError(client.get("/health/ready"), 503, "DATABASE_UNAVAILABLE")
            self.assertNotIn("127.0.0.1", json.dumps(error))

    def test_freshness(self):
        with mock.patch.object(routes, "today", return_value=TODAY):
            body = self.ok("/api/v1/metadata/freshness")
        self.assertEqual(body["published_ufs"], ["SP"])
        self.assertEqual(body["data_as_of"], LAST_COLLECTION.isoformat())
        self.assertEqual(body["latest_week_start"], LAST.isoformat())
        self.assertEqual(body["age_days"], (TODAY - LAST_COLLECTION).days)
        self.assertEqual(datetime.fromisoformat(body["source_retrieved_at"]),
                         datetime.fromisoformat(f"{(LAST + timedelta(days=3)).isoformat()}T12:00:00+00:00"))
        self.assertIn(body["last_load"]["status"], {"success", "warning"})
        self.assertIsNotNone(body["last_successful_load_at"])
        self.assertIn("ANP", body["source"])

    def test_products(self):
        body = self.ok("/api/v1/products")
        codes = {p["code"]: p for p in body["items"]}
        self.assertEqual(set(codes), {"GASOLINA_COMUM", "GASOLINA_ADITIVADA", "ETANOL_HIDRATADO", "DIESEL_COMUM",
                                      "DIESEL_S10", "GNV"})
        self.assertEqual(codes["GNV"]["unit"], "BRL/M3")
        self.assertEqual(codes["GASOLINA_COMUM"]["unit"], "BRL/L")
        self.assertNotIn("GLP", codes)
        self.assertEqual(body["data_as_of"], LAST_COLLECTION.isoformat())

    def test_locations_listing_search_and_pagination(self):
        body = self.ok("/api/v1/locations")
        names = [i["municipality"] for i in body["items"]]
        self.assertEqual(len(names), 5)
        self.assertEqual(names, sorted(names, key=normalize_text))
        self.assertEqual((body["total"], body["page"], body["published_ufs"]), (5, 1, ["SP"]))
        itu = next(i for i in body["items"] if normalize_text(i["municipality"]) == "ITU")
        self.assertEqual((itu["first_week_start"], itu["last_week_start"]), (week(0).isoformat(), week(4).isoformat()))
        self.assertEqual(itu["products"], 1)
        jundiai = next(i for i in body["items"] if normalize_text(i["municipality"]) == "JUNDIAI")
        self.assertEqual(jundiai["products"], 2)  # gasolina e etanol

        found = self.ok("/api/v1/locations", q="sao carl")["items"]
        self.assertEqual([normalize_text(i["municipality"]) for i in found], ["SAO CARLOS"])
        self.assertEqual(self.ok("/api/v1/locations", q="%")["total"], 0)  # sem curingas

        first = self.ok("/api/v1/locations", page_size=2, page=1)
        third = self.ok("/api/v1/locations", page_size=2, page=3)
        beyond = self.ok("/api/v1/locations", page_size=2, page=9)
        self.assertEqual((len(first["items"]), first["total"], len(third["items"])), (2, 5, 1))
        self.assertEqual((beyond["items"], beyond["total"]), ([], 5))


class PriceTests(ApiCase):
    def test_latest_city_matches_independent_calculation(self):
        body = self.ok("/api/v1/prices/latest", municipality="Campinas", product="GASOLINA_COMUM")
        self.assertEqual(body["location"]["uf"], "SP")
        self.assertEqual(normalize_text(body["location"]["municipality"]), "CAMPINAS")
        self.assertEqual(body["product"], "GASOLINA_COMUM")
        self.assertEqual((body["week_start"], body["week_end"]), (LAST.isoformat(), (LAST + timedelta(days=6)).isoformat()))
        self.assertTrue(body["is_dataset_latest_week"])
        self.assertStats(body["statistics"], self.values("Campinas", "GASOLINA_COMUM", 11))
        self.assertEqual(body["sample"]["observations"], 8)
        self.assertEqual(body["sample"]["stations"], 8)
        self.assertEqual(body["sample"]["coverage_status"], "ok")
        self.assertEqual(body["data_as_of"], LAST_COLLECTION.isoformat())
        self.assertEqual(datetime.fromisoformat(body["source_retrieved_at"]),
                         datetime.fromisoformat(f"{(LAST + timedelta(days=3)).isoformat()}T12:00:00+00:00"))
        previous = statistics.median(self.values("Campinas", "GASOLINA_COMUM", 10))
        current = statistics.median(self.values("Campinas", "GASOLINA_COMUM", 11))
        self.assertAlmostEqual(body["weekly_change"]["value"], float(current / previous - 1), places=4)
        self.assertEqual(body["weekly_change"]["previous_week_start"], week(10).isoformat())
        self.assertIsNone(body["weekly_change"]["reason"])

    def test_latest_state_aggregate(self):
        body = self.ok("/api/v1/prices/latest", product="gasolina_comum")  # código sem distinção de caixa
        self.assertIsNone(body["location"]["municipality"])
        self.assertStats(body["statistics"], self.state_values("GASOLINA_COMUM", 11))
        sample = body["sample"]
        self.assertEqual(sample["observations"], len(self.state_values("GASOLINA_COMUM", 11)))
        self.assertEqual(sample["coverage_status"], "not_applicable")
        self.assertEqual((sample["municipalities"], sample["low_coverage_municipalities"]), (4, 1))

    def test_latest_low_coverage_has_no_weekly_change(self):
        body = self.ok("/api/v1/prices/latest", municipality="Jundiaí", product="GASOLINA_COMUM")
        self.assertEqual(body["sample"]["coverage_status"], "low")
        self.assertAlmostEqual(body["sample"]["coverage_ratio"], 0.25)
        self.assertEqual(body["sample"]["baseline_median_stations"], 8)
        self.assertEqual(body["sample"]["stations"], 2)
        self.assertIsNone(body["weekly_change"]["value"])
        self.assertEqual(body["weekly_change"]["reason"], "LOW_COVERAGE")

    def test_latest_of_series_that_stopped_is_flagged_and_uses_its_own_freshness(self):
        body = self.ok("/api/v1/prices/latest", municipality="Itu", product="GASOLINA_COMUM")
        self.assertEqual(body["week_start"], week(4).isoformat())
        self.assertFalse(body["is_dataset_latest_week"])
        self.assertEqual(body["data_as_of"], (week(4) + timedelta(days=1)).isoformat())
        self.assertEqual(datetime.fromisoformat(body["source_retrieved_at"]),
                         datetime.fromisoformat(f"{(week(4) + timedelta(days=3)).isoformat()}T12:00:00+00:00"))

    def test_single_week_series_has_no_previous_week_and_no_history(self):
        body = self.ok("/api/v1/prices/latest", municipality="Tietê", product="GASOLINA_COMUM")
        self.assertIsNone(body["weekly_change"]["value"])
        self.assertEqual(body["weekly_change"]["reason"], "NO_PREVIOUS_WEEK")
        self.assertEqual(body["sample"]["coverage_status"], "no_history")
        self.assertIsNone(body["sample"]["coverage_ratio"])

    def test_municipality_lookup_ignores_case_accents_and_spaces(self):
        results = [self.ok("/api/v1/prices/latest", municipality=name, product="GASOLINA_COMUM")
                   for name in ("São Carlos", "sao carlos", "SAO CARLOS", "  São   Carlos ")]
        self.assertTrue(all(r["location"] == results[0]["location"] for r in results))
        self.assertTrue(all(r["statistics"] == results[0]["statistics"] for r in results))

    def test_other_products_are_separate_series(self):
        ethanol = self.ok("/api/v1/prices/latest", municipality="Jundiaí", product="ETANOL_HIDRATADO")
        self.assertStats(ethanol["statistics"], self.values("Jundiaí", "ETANOL_HIDRATADO", 11))
        self.assertEqual(ethanol["sample"]["stations"], 4)
        self.assertEqual(ethanol["sample"]["coverage_status"], "ok")
        diesel = self.ok("/api/v1/prices/latest", municipality="Campinas", product="DIESEL_S10")
        self.assertEqual(diesel["sample"]["stations"], 3)

    def test_not_found_and_validation_errors(self):
        self.assertError(self.get("/api/v1/prices/latest", municipality="Atlântida", product="GASOLINA_COMUM"),
                         404, "LOCATION_NOT_FOUND")
        self.assertError(self.get("/api/v1/prices/latest", municipality="Campinas", product="QUEROSENE"),
                         404, "PRODUCT_NOT_FOUND")
        self.assertError(self.get("/api/v1/prices/latest", municipality="Campinas", product="GLP"),
                         404, "PRODUCT_NOT_FOUND")
        self.assertError(self.get("/api/v1/prices/latest", municipality="Campinas", product="GASOLINA_COMUM",
                                  uf="RJ"), 422, "UF_NOT_PUBLISHED")
        error = self.assertError(self.get("/api/v1/prices/latest", municipality="Campinas",
                                          product="GASOLINA_COMUM", uf="XYZ"), 422, "VALIDATION_ERROR")
        self.assertEqual(error and self.get("/api/v1/prices/latest", product="GASOLINA_COMUM", uf="XYZ")
                         .json()["error"]["details"][0]["field"], "uf")
        self.assertError(self.get("/api/v1/prices/latest", municipality="Campinas"), 422, "VALIDATION_ERROR")  # sem produto
        self.assertEqual(self.get("/api/v1/prices/latest", municipality="Campinas", product="GASOLINA_COMUM",
                                  uf="sp").status_code, 200)

    def test_hostile_text_is_just_an_unknown_municipality(self):
        for text in ("'; DROP TABLE dim_location; --", "%", "_", "Campinas%", "\x00x"[1:], "a" * 80):
            response = self.get("/api/v1/prices/latest", municipality=text, product="GASOLINA_COMUM")
            self.assertEqual(response.status_code, 404, text)
        self.assertError(self.get("/api/v1/prices/latest", municipality="a" * 81, product="GASOLINA_COMUM"),
                         422, "VALIDATION_ERROR")
        self.assertEqual(self.ok("/api/v1/prices/latest", municipality="Campinas", product="GASOLINA_COMUM")["sample"]["stations"], 8)


class HistoryTests(ApiCase):
    def test_full_series_matches_independent_calculation(self):
        body = self.ok("/api/v1/prices/history", municipality="Jundiaí", product="GASOLINA_COMUM")
        items = body["items"]
        self.assertEqual(body["total"], N_WEEKS)
        self.assertEqual([i["week_start"] for i in items], [week(n).isoformat() for n in range(N_WEEKS)])
        for n, item in enumerate(items):
            self.assertStats(item["statistics"], self.values("Jundiaí", "GASOLINA_COMUM", n))
            self.assertEqual(item["sample"]["stations"], len(self.values("Jundiaí", "GASOLINA_COMUM", n)))
        self.assertEqual(items[0]["weekly_change"]["reason"], "NO_PREVIOUS_WEEK")
        self.assertEqual(items[1]["sample"]["coverage_status"], "no_history")
        self.assertEqual(items[8]["sample"]["coverage_status"], "ok")
        self.assertEqual(items[-1]["sample"]["coverage_status"], "low")
        self.assertEqual(items[-1]["weekly_change"]["reason"], "LOW_COVERAGE")
        change = statistics.median(self.values("Jundiaí", "GASOLINA_COMUM", 5)) / \
            statistics.median(self.values("Jundiaí", "GASOLINA_COMUM", 4)) - 1
        self.assertAlmostEqual(items[5]["weekly_change"]["value"], float(change), places=4)
        self.assertEqual(body["data_as_of"], LAST_COLLECTION.isoformat())
        self.assertEqual((body["start"], body["end"]), ((LAST - timedelta(weeks=51)).isoformat(), LAST.isoformat()))

    def test_range_uses_the_week_before_the_start_for_the_first_change(self):
        body = self.ok("/api/v1/prices/history", municipality="Jundiaí", product="GASOLINA_COMUM",
                       start=week(3).isoformat(), end=week(5).isoformat())
        self.assertEqual([i["week_start"] for i in body["items"]], [week(n).isoformat() for n in (3, 4, 5)])
        first = body["items"][0]["weekly_change"]
        change = statistics.median(self.values("Jundiaí", "GASOLINA_COMUM", 3)) / \
            statistics.median(self.values("Jundiaí", "GASOLINA_COMUM", 2)) - 1
        self.assertAlmostEqual(first["value"], float(change), places=4)
        self.assertEqual(first["previous_week_start"], week(2).isoformat())
        self.assertEqual(body["data_as_of"], (week(5) + timedelta(days=1)).isoformat())

    def test_gaps_are_not_filled_and_a_gap_blocks_the_change(self):
        body = self.ok("/api/v1/prices/history", municipality="Itu", product="GASOLINA_COMUM")
        self.assertEqual(len(body["items"]), 5)  # semanas 5 a 11 não existem para Itu
        self.assertEqual(body["data_as_of"], (week(4) + timedelta(days=1)).isoformat())

    def test_state_series(self):
        body = self.ok("/api/v1/prices/history", product="GASOLINA_COMUM")
        self.assertIsNone(body["location"]["municipality"])
        self.assertEqual(body["total"], N_WEEKS)
        for n, item in enumerate(body["items"]):
            self.assertStats(item["statistics"], self.state_values("GASOLINA_COMUM", n))
            self.assertEqual(item["sample"]["coverage_status"], "not_applicable")
        last = body["items"][-1]["sample"]
        self.assertEqual((last["municipalities"], last["low_coverage_municipalities"]), (4, 1))

    def test_pagination(self):
        page = self.ok("/api/v1/prices/history", municipality="Campinas", product="GASOLINA_COMUM",
                       page_size=5, page=3)
        self.assertEqual((len(page["items"]), page["total"], page["page"], page["page_size"]), (2, N_WEEKS, 3, 5))
        self.assertEqual(page["items"][0]["week_start"], week(10).isoformat())

    def test_range_limits(self):
        base = {"municipality": "Campinas", "product": "GASOLINA_COMUM"}
        self.assertError(self.get("/api/v1/prices/history", **base, start="2020-01-05", end=LAST.isoformat()),
                         422, "RANGE_TOO_LARGE")
        self.assertError(self.get("/api/v1/prices/history", **base, start=week(5).isoformat(), end=week(2).isoformat()),
                         422, "INVALID_RANGE")
        self.assertError(self.get("/api/v1/prices/history", **base, start="não-é-data"), 422, "VALIDATION_ERROR")
        far = self.ok("/api/v1/prices/history", **base, start="2020-01-05", end="2020-12-27")
        self.assertEqual((far["items"], far["total"], far["data_as_of"]), ([], 0, None))

    def test_page_limits_are_validated(self):
        base = {"municipality": "Campinas", "product": "GASOLINA_COMUM"}
        for extra in ({"page_size": 201}, {"page_size": 0}, {"page": 0}):
            self.assertError(self.get("/api/v1/prices/history", **base, **extra), 422, "VALIDATION_ERROR")


class CompareTests(ApiCase):
    def test_ranking_excludes_low_coverage_and_compares_with_state(self):
        body = self.ok("/api/v1/prices/compare", product="GASOLINA_COMUM",
                       municipality=["Campinas", "Jundiaí", "São Carlos", "Tietê"])
        self.assertEqual(body["week_start"], LAST.isoformat())
        by_name = {normalize_text(i["location"]["municipality"]): i for i in body["items"]}
        self.assertIsNone(by_name["JUNDIAI"]["rank"])  # cobertura baixa fica fora do ranking
        self.assertEqual(by_name["JUNDIAI"]["sample"]["coverage_status"], "low")
        medians = {c: statistics.median(self.values(city, "GASOLINA_COMUM", 11))
                   for c, city in (("CAMPINAS", "Campinas"), ("SAO CARLOS", "São Carlos"), ("TIETE", "Tietê"))}
        order = sorted(medians, key=lambda c: (medians[c], c))
        self.assertEqual([by_name[c]["rank"] for c in order], [1, 2, 3])
        self.assertEqual([i["location"]["municipality"] for i in body["items"][:3]],
                         [by_name[c]["location"]["municipality"] for c in order])
        self.assertIsNone(body["items"][-1]["rank"])

        state_median = statistics.median(self.state_values("GASOLINA_COMUM", 11))
        self.assertAlmostEqual(body["reference"]["statistics"]["median"], float(state_median), places=4)
        self.assertIsNone(body["reference"]["location"]["municipality"])
        for name, item in by_name.items():
            city = {"CAMPINAS": "Campinas", "SAO CARLOS": "São Carlos", "TIETE": "Tietê", "JUNDIAI": "Jundiaí"}[name]
            diff = statistics.median(self.values(city, "GASOLINA_COMUM", 11)) - state_median
            self.assertAlmostEqual(item["difference_to_state"], float(diff), places=4)
        self.assertEqual(body["data_as_of"], LAST_COLLECTION.isoformat())

    def test_ties_share_the_rank(self):
        body = self.ok("/api/v1/prices/compare", product="GASOLINA_COMUM",
                       municipality=["Campinas", "São Carlos", "Itu"], week_start=week(0).isoformat())
        items = {normalize_text(i["location"]["municipality"]): i for i in body["items"]}
        self.assertEqual(items["ITU"]["statistics"]["median"], items["SAO CARLOS"]["statistics"]["median"])
        self.assertEqual({k: v["rank"] for k, v in items.items()}, {"ITU": 1, "SAO CARLOS": 1, "CAMPINAS": 3})

    def test_municipality_without_data_in_the_week_is_listed_as_no_data(self):
        body = self.ok("/api/v1/prices/compare", product="GASOLINA_COMUM", municipality=["Campinas", "Tietê"],
                       week_start=week(10).isoformat())
        by_name = {normalize_text(i["location"]["municipality"]): i for i in body["items"]}
        self.assertEqual(by_name["TIETE"]["sample"]["coverage_status"], "no_data")
        self.assertIsNone(by_name["TIETE"]["statistics"])
        self.assertIsNone(by_name["TIETE"]["rank"])
        self.assertEqual(by_name["CAMPINAS"]["rank"], 1)

    def test_validation(self):
        names = [f"Cidade {i}" for i in range(11)]
        self.assertError(self.get("/api/v1/prices/compare", product="GASOLINA_COMUM", municipality=names),
                         422, "VALIDATION_ERROR")
        self.assertError(self.get("/api/v1/prices/compare", product="GASOLINA_COMUM"), 422, "VALIDATION_ERROR")
        self.assertError(self.get("/api/v1/prices/compare", product="GASOLINA_COMUM", municipality=["Campinas"],
                                  week_start=(LAST + timedelta(days=1)).isoformat()), 422, "INVALID_WEEK")
        error = self.assertError(self.get("/api/v1/prices/compare", product="GASOLINA_COMUM",
                                          municipality=["Campinas", "Atlântida", "Nárnia"]), 404, "LOCATION_NOT_FOUND")
        self.assertIn("Atlântida", error["message"])
        self.assertIn("Nárnia", error["message"])


class StationsTests(ApiCase):
    def test_stations_with_latest_price(self):
        body = self.ok("/api/v1/stations", municipality="Campinas", product="GASOLINA_COMUM")
        self.assertEqual(body["total"], 8)
        self.assertEqual(body["product"], "GASOLINA_COMUM")
        names = [i["name"] for i in body["items"]]
        self.assertEqual(names, sorted(names))
        expected = self.expected[("Campinas", "GASOLINA_COMUM", 11)]
        for item in body["items"]:
            station = int(item["name"].split()[-1])
            self.assertEqual(item["cnpj"], make_cnpj(station))
            self.assertAlmostEqual(item["latest_price"], float(expected[station]), places=4)
            self.assertEqual(item["latest_price_date"], LAST_COLLECTION.isoformat())
            self.assertEqual(normalize_text(item["municipality"]), "CAMPINAS")
            self.assertEqual((item["uf"], item["brand"]), ("SP", "BRANCA"))

    def test_product_filter_keeps_only_stations_that_sell_it(self):
        ethanol = self.ok("/api/v1/stations", municipality="Jundiaí", product="ETANOL_HIDRATADO")
        self.assertEqual(ethanol["total"], 4)
        everything = self.ok("/api/v1/stations", municipality="Jundiaí")
        self.assertEqual(everything["total"], 8)
        self.assertTrue(all(i["latest_price"] is None for i in everything["items"]))
        # Posto 1 vendeu etanol e gasolina; o último preço depende do produto pedido.
        gasoline = self.ok("/api/v1/stations", municipality="Jundiaí", product="GASOLINA_COMUM")
        one = next(i for i in gasoline["items"] if i["name"] == "POSTO 1")
        self.assertAlmostEqual(one["latest_price"], float(self.expected[("Jundiaí", "GASOLINA_COMUM", 11)][1]), places=4)

    def test_pagination_and_state_wide_listing(self):
        page = self.ok("/api/v1/stations", page_size=10, page=2)
        self.assertEqual(page["total"], 8 + 8 + 3 + 3 + 2)
        self.assertEqual(len(page["items"]), 10)
        beyond = self.ok("/api/v1/stations", page_size=10, page=9)
        self.assertEqual((beyond["items"], beyond["total"]), ([], 24))
        self.assertError(self.get("/api/v1/stations", municipality="Atlântida"), 404, "LOCATION_NOT_FOUND")
        self.assertError(self.get("/api/v1/stations", product="QUEROSENE"), 404, "PRODUCT_NOT_FOUND")


class DataQualityTests(ApiCase):
    def test_summary_matches_the_database(self):
        body = self.ok("/api/v1/data-quality")
        published, flagged = self.admin_query("""
            SELECT count(*), count(*) FILTER (WHERE quality_status = 'warning')
            FROM fact_price_observation WHERE is_current_source_revision""".replace("FROM fact", "FROM radar.fact"))[0]
        self.assertEqual(body["observations"]["observations_published"], published)
        self.assertEqual(body["observations"]["observations_with_warning"], flagged)
        self.assertEqual(body["observations"]["observations_quarantined"], 0)
        self.assertEqual(body["last_load"]["quality_decision"] in {"publicar", "publicar_com_aviso"}, True)
        coverage = body["coverage"]
        self.assertEqual(coverage["week_start"], LAST.isoformat())
        counts = {}
        for flag, baseline in self.admin_query("""
                SELECT quality_flag, baseline_median_stations FROM radar.mart_weekly_city_price
                WHERE week_start = %s""", (LAST,)):
            key = "sem_historico" if flag == "ok" and baseline == 0 else flag  # série nova: base zero
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(counts["sem_historico"], 1)  # só a série nova (Tietê, gasolina)
        self.assertEqual((coverage["ok"], coverage["low"], coverage["no_history"]),
                         (counts.get("ok", 0), counts.get("cobertura_baixa", 0), counts.get("sem_historico", 0)))
        self.assertEqual(coverage["series"], sum(counts.values()))
        low = {(normalize_text(i["location"]["municipality"]), i["product"]): i for i in body["low_coverage"]["items"]}
        self.assertEqual(body["low_coverage"]["total"], coverage["low"])
        jundiai = low[("JUNDIAI", "GASOLINA_COMUM")]
        self.assertEqual((jundiai["stations"], jundiai["baseline_median_stations"]), (2, 8))
        self.assertAlmostEqual(jundiai["coverage_ratio"], 0.25)

    def test_other_week_and_validation(self):
        body = self.ok("/api/v1/data-quality", week_start=week(2).isoformat())
        self.assertEqual(body["coverage"]["week_start"], week(2).isoformat())
        self.assertEqual(body["coverage"]["low"], 0)
        self.assertError(self.get("/api/v1/data-quality", week_start=(week(2) + timedelta(days=1)).isoformat()),
                         422, "INVALID_WEEK")


class InfrastructureTests(ApiCase):
    def test_unknown_route_and_method_use_the_error_format(self):
        self.assertError(self.get("/api/v1/nao-existe"), 404, "NOT_FOUND")
        self.assertError(self.client.post("/api/v1/products"), 405, "METHOD_NOT_ALLOWED")

    def test_forecasts_and_anomalies_are_not_published_yet(self):
        paths = set(self.client.get("/openapi.json").json()["paths"])
        self.assertEqual(paths, {
            "/health/live", "/health/ready", "/api/v1/metadata/freshness", "/api/v1/products", "/api/v1/locations",
            "/api/v1/prices/latest", "/api/v1/prices/history", "/api/v1/prices/compare", "/api/v1/stations",
            "/api/v1/data-quality"})
        self.assertError(self.get("/api/v1/forecasts"), 404, "NOT_FOUND")
        self.assertEqual(self.client.get("/docs").status_code, 200)

    def test_openapi_documents_error_responses(self):
        spec = self.client.get("/openapi.json").json()
        responses = spec["paths"]["/api/v1/prices/latest"]["get"]["responses"]
        self.assertTrue({"200", "404", "422"} <= set(responses))
        self.assertIn("ErrorResponse", json.dumps(responses["404"]))

    def test_request_id_is_echoed_or_replaced(self):
        good = self.client.get("/health/live", headers={"X-Request-ID": "abc-123.DEF_4"})
        self.assertEqual(good.headers["x-request-id"], "abc-123.DEF_4")
        bad = self.client.get("/health/live", headers={"X-Request-ID": "tem espaco e <script>"})
        self.assertNotEqual(bad.headers["x-request-id"], "tem espaco e <script>")
        self.assertRegex(bad.headers["x-request-id"], r"^[0-9a-f]{32}$")
        error = self.client.get("/api/v1/nada", headers={"X-Request-ID": "req-42"})
        self.assertEqual(error.json()["error"]["request_id"], "req-42")

    def test_connection_is_read_only_and_least_privilege(self):
        with self.app.state.pool.connection() as conn:
            self.assertEqual(conn.execute("SHOW default_transaction_read_only").fetchone()["default_transaction_read_only"], "on")
            self.assertEqual(conn.execute("SHOW transaction_isolation").fetchone()["transaction_isolation"], "repeatable read")
        for statement in ("DELETE FROM dim_product", "UPDATE dim_station SET brand = 'X'",
                          "INSERT INTO dim_product (canonical_name, source_name, category, unit, active) "
                          "VALUES ('X', 'X', 'glp', 'BRL/L', false)", "REFRESH MATERIALIZED VIEW mart_weekly_city_price",
                          "DROP TABLE dim_product", "CREATE TABLE t (id int)"):
            with self.app.state.pool.connection() as conn, self.assertRaises(psycopg.Error, msg=statement):
                conn.execute(statement)
        for statement in ("SELECT original FROM quarantine_observation", "SELECT storage_uri FROM source_file",
                          "SELECT error_summary FROM ingestion_run", "SELECT * FROM schema_migration"):
            with self.app.state.pool.connection() as conn, \
                    self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=statement):
                conn.execute(statement)

    def test_responses_do_not_leak_internals(self):
        for path, params in (("/api/v1/stations", {"municipality": "Campinas"}), ("/api/v1/metadata/freshness", {}),
                             ("/api/v1/data-quality", {}), ("/api/v1/products", {})):
            text = self.client.get(path, params=params).text
            for secret in ("storage_uri", "postgresql://", self.password, self.role, "error_summary", "source_row_hash"):
                self.assertNotIn(secret, text, f"{path}: {secret}")

    def test_unexpected_error_is_500_without_internal_details(self):
        with self.make_client(self.api_url) as client, self.assertLogs("radar.api", "ERROR"), \
                mock.patch.object(routes.queries, "published_products", side_effect=RuntimeError("segredo-interno")):
            response = client.get("/api/v1/products")
        error = self.assertError(response, 500, "INTERNAL_ERROR")
        self.assertNotIn("segredo-interno", json.dumps(error))

    def test_slow_query_is_cancelled_with_503(self):
        def slow(conn):
            conn.execute("SELECT pg_sleep(5)")
        with self.make_client(self.api_url, statement_timeout_ms=300) as client, \
                self.assertLogs("radar.api", "WARNING"), \
                mock.patch.object(routes.queries, "dataset_freshness", side_effect=slow):
            response = client.get("/api/v1/products")
        self.assertError(response, 503, "QUERY_TIMEOUT")

    def test_configuration_requires_a_database_url(self):
        with self.assertRaises(ValueError):
            api_database_url({})
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("API_DATABASE_URL", None)
            with self.assertRaises(ValueError):
                create_app()

    def test_unpublished_ufs_follow_the_configuration(self):
        with self.make_client(self.api_url, target_ufs=("RJ",)) as client:
            self.assertError(client.get("/api/v1/prices/latest", params={"product": "GASOLINA_COMUM", "uf": "SP"}),
                             422, "UF_NOT_PUBLISHED")


if __name__ == "__main__":
    unittest.main()
