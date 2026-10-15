"""Pacote instantâneo do demonstrativo: cliente instantâneo × API real nas mesmas consultas.

Mesmo banco sintético de tests/test_api.py, com um modelo publicado (previsões e variações
incomuns) e dois postos sem nome fantasia. O pacote é gerado pela API e lido pelo cliente
instantâneo; as respostas têm de ser iguais às da API, exceto CNPJ e razão social, que não vão ao
pacote. Também confere o painel inteiro em modo instantâneo.
"""

from datetime import date, timedelta
import gzip
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from tests.test_api import (ApiCase, LAST, N_WEEKS, WEEK0, distribution_row, insert_published_model,  # noqa: E402
                            week)
from radar_combustiveis import snapshot  # noqa: E402
from radar_combustiveis.dashboard import views  # noqa: E402
from radar_combustiveis.dashboard.client import ApiClient, ApiError  # noqa: E402
from radar_combustiveis.dashboard.snapshot import SnapshotClient  # noqa: E402
from radar_combustiveis.db.connection import SCHEMA, connect  # noqa: E402
from radar_combustiveis.ingestion.normalize import normalize_text  # noqa: E402

logging.getLogger("streamlit").setLevel(logging.ERROR)


def tearDownModule():
    from streamlit.testing.v1 import app_test  # mesmo cuidado de tests/test_dashboard.py
    app_test.TMP_DIR.cleanup()


PAGES = ("home", "explore", "stations_ranking", "brands_page", "forecasts_page", "anomalies_page", "compare",
         "regions_page", "margins_page", "study_page", "quality", "live_page")


class PackageUnitTests(unittest.TestCase):
    def test_public_station_drops_cnpj_and_legal_name(self):
        item = {"cnpj": "12345678000199", "name": "AUTO POSTO X LTDA", "legal_name": "AUTO POSTO X LTDA",
                "brand": "BRANCA", "address": "RUA A"}
        self.assertEqual(snapshot.public_station(item, {"12345678000199": "POSTO X"}),
                         {**item, "cnpj": None, "legal_name": None, "name": "POSTO X"})
        self.assertEqual(snapshot.public_station(item, {})["name"], "Posto bandeira branca")
        self.assertEqual(snapshot.public_name("IPIRANGA"), "Posto IPIRANGA")
        self.assertEqual(snapshot.public_name(None), "Posto sem bandeira informada")

    def test_age_is_counted_from_today_not_from_the_build_day(self):
        package = {"calls": {snapshot.call_key("locations"): [],
                             snapshot.call_key("freshness"): {"data_as_of": "2026-10-09", "age_days": 2}}}
        client = SnapshotClient(package, today=date(2026, 11, 9))
        self.assertEqual(client.freshness()["age_days"], 31)

    def test_missing_query_and_stored_errors_become_api_errors(self):
        package = {"calls": {snapshot.call_key("locations"): [],
                             snapshot.call_key("forecasts", "GNV", None): {"__error__": {
                                 "status": 404, "code": "NO_PUBLISHED_MODEL", "message": "sem modelo"}}}}
        client = SnapshotClient(package)
        with self.assertRaises(ApiError) as caught:
            client.forecasts("GNV")
        self.assertEqual(caught.exception.code, "NO_PUBLISHED_MODEL")
        with self.assertRaises(ApiError) as caught:
            client.brands("GNV")
        self.assertEqual(caught.exception.code, "NOT_IN_SNAPSHOT")


class SnapshotContractTests(ApiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        insert_published_model(cls.admin_url)
        from radar_combustiveis.external import load as external_load
        rows = ([distribution_row("CAMPINAS", "municipio", n, 5.5) for n in range(9)]
                + [distribution_row("SP", "uf", n, 5.4) for n in range(9)])
        record = {"sha256": "d" * 64, "name": "distribuicao.xlsx", "url": "https://www.gov.br/x",
                  "raw_path": "external/x.xlsx", "retrieved_at": "2026-10-10T12:00:00+00:00",
                  "first_retrieved_at": "2026-10-10T12:00:00+00:00"}
        with connect(cls.admin_url) as conn:
            external_load.load_source(conn, "anp_distribuicao", [(record, rows)])
        with psycopg.connect(cls.admin_url) as conn:  # dois postos sem nome fantasia, como 62% dos reais
            conn.execute("UPDATE dim_station SET trade_name = NULL WHERE trade_name IN ('POSTO 1', 'POSTO 30')")
            cls.unnamed = [r[0] for r in conn.execute(
                "SELECT legal_name FROM dim_station WHERE trade_name IS NULL").fetchall()]
            cls.cnpjs = [r[0] for r in conn.execute("SELECT cnpj FROM dim_station").fetchall()]
        cls.api = ApiClient(cls.client)
        options = f"-c search_path={SCHEMA} -c timezone=UTC"
        with psycopg.connect(cls.api_url, options=options, row_factory=dict_row) as conn:
            cls.package = snapshot.build(cls.api, conn)
        folder = tempfile.mkdtemp()
        cls.path = Path(folder) / "pacote.json.gz"
        snapshot.write(cls.package, cls.path)
        cls.addClassCleanup(lambda: (cls.path.unlink(), os.rmdir(folder)))
        cls.snap = SnapshotClient.from_file(cls.path)

    def name(self, wanted):
        return next(loc["municipality"] for loc in self.api.locations()
                    if normalize_text(loc["municipality"]) == normalize_text(wanted))

    def same(self, method, *args):
        got, want = getattr(self.snap, method)(*args), getattr(self.api, method)(*args)
        self.assertEqual(got, want, f"{method}{args}")
        return got

    def same_error(self, method, *args):
        with self.assertRaises(ApiError) as api_error:
            getattr(self.api, method)(*args)
        with self.assertRaises(ApiError) as snap_error:
            getattr(self.snap, method)(*args)
        self.assertEqual((snap_error.exception.status, snap_error.exception.code),
                         (api_error.exception.status, api_error.exception.code))

    def test_history_slices_match_the_api_including_freshness(self):
        cities = [None] + [self.name(n) for n in ("Campinas", "Jundiaí", "Itu", "Tietê")]
        ranges = [(None, None), (week(2).isoformat(), week(6).isoformat()), (WEEK0.isoformat(), LAST.isoformat()),
                  (week(9).isoformat(), None), ((WEEK0 - timedelta(weeks=20)).isoformat(), week(1).isoformat()),
                  (week(5).isoformat(), week(5).isoformat())]
        for product in ("GASOLINA_COMUM", "ETANOL_HIDRATADO", "DIESEL_S10"):
            for city in cities:
                for start, end in ranges:
                    self.same("history", product, city, start, end)
        self.same_error("history", "GASOLINA_COMUM", "Atlântida", None, None)
        self.same_error("history", "QUEROSENE", None, None, None)
        self.same_error("history", "GASOLINA_COMUM", None, week(5).isoformat(), week(2).isoformat())

    def test_compare_ranks_ties_low_coverage_and_missing_data_like_the_api(self):
        names = [self.name(n) for n in ("Campinas", "Jundiaí", "São Carlos", "Itu", "Tietê")]
        for product in ("GASOLINA_COMUM", "ETANOL_HIDRATADO"):
            for n in (0, 4, 7, N_WEEKS - 1):  # semana 0: empate São Carlos × Itu; última: Jundiaí com cobertura baixa
                self.same("compare", product, names, week(n).isoformat())
                self.same("compare", product, names[:2], week(n).isoformat())
            self.same("compare", product, names[2:], None)
        self.same("compare", "GASOLINA_COMUM", ["campinas", names[1]], LAST.isoformat())  # caixa e acento
        self.same_error("compare", "GASOLINA_COMUM", ["Atlântida", names[0]], None)

    def test_precomputed_answers_are_the_api_answers(self):
        for product in ("GASOLINA_COMUM", "ETANOL_HIDRATADO", "DIESEL_S10", "GNV"):
            for city in [None] + [loc["municipality"] for loc in self.api.locations()]:
                for method, args in (("latest", (product, city)), ("brands", (product, city)),
                                     ("forecasts", (product, city))):
                    try:
                        self.same(method, *args)
                    except ApiError:
                        self.same_error(method, *args)
            self.same("regions", product, 26) if product != "GNV" else self.same_error("regions", product, 26)
            self.same("rankings", product, 26)
        for product in ("GASOLINA_COMUM", "GNV"):
            for city in (None, self.name("Campinas"), self.name("Itu")):
                try:
                    self.same("margins", product, city, 52)
                except ApiError:
                    self.same_error("margins", product, city, 52)
        self.same("margin_municipalities", "GASOLINA_COMUM")
        self.same_error("margin_municipalities", "ETANOL_HIDRATADO")
        self.same("ethanol", None, 1)
        self.same("ethanol", self.name("Jundiaí"), 26)
        self.same("station_choice", "GASOLINA_COMUM", self.name("Campinas"))
        for method in ("products", "locations", "data_quality"):
            self.same(method)
        fresh, api_fresh = self.snap.freshness(), self.api.freshness()
        self.assertEqual({k: v for k, v in fresh.items() if k != "age_days"},
                         {k: v for k, v in api_fresh.items() if k != "age_days"})

    def test_anomaly_filters_match_the_api(self):
        campinas, jundiai = self.name("Campinas"), self.name("Jundiaí")
        for product in (None, "GASOLINA_COMUM", "DIESEL_S10"):
            for city in (None, campinas, jundiai):
                for weeks in (1, 4, 8, 12):
                    self.same("anomalies", product, city, weeks)

    def test_stations_are_the_api_lists_without_cnpj_or_legal_name(self):
        for city in ("Campinas", "Jundiaí", "Tietê"):
            name = self.name(city)
            for method, args in (("stations", (name, "GASOLINA_COMUM")),
                                 ("station_ranking", (name, "GASOLINA_COMUM", True)),
                                 ("station_ranking", (name, "GASOLINA_COMUM", False))):
                got, want = getattr(self.snap, method)(*args), getattr(self.api, method)(*args)
                self.assertEqual([i["latest_price"] for i in got["items"]], [i["latest_price"] for i in want["items"]])
                self.assertEqual({k: v for k, v in got.items() if k != "items"},
                                 {k: v for k, v in want.items() if k != "items"})
                for g, w in zip(got["items"], want["items"]):
                    self.assertIsNone(g["cnpj"])
                    self.assertIsNone(g["legal_name"])
                    self.assertEqual({k: v for k, v in g.items() if k not in ("cnpj", "legal_name", "name")},
                                     {k: v for k, v in w.items() if k not in ("cnpj", "legal_name", "name")})
        got = self.snap.margin_stations("GASOLINA_COMUM", self.name("Campinas"))
        want = self.api.margin_stations("GASOLINA_COMUM", self.name("Campinas"))
        self.assertEqual([(i["price"], i["estimated_margin"]) for i in got["items"]],
                         [(i["price"], i["estimated_margin"]) for i in want["items"]])
        self.assertTrue(got["items"])
        self.assertTrue(all(i["cnpj"] is None and i["legal_name"] is None for i in got["items"]))
        names = {i["name"] for i in self.snap.stations(self.name("Jundiaí"), "GASOLINA_COMUM")["items"]}
        self.assertIn("Posto bandeira branca", names)  # o POSTO 1, sem nome fantasia
        self.assertIn("POSTO 2", names)

    def test_package_has_no_cnpj_nor_legal_name_of_unnamed_stations(self):
        raw = gzip.open(self.path).read().decode("utf-8")
        self.assertTrue(self.unnamed)
        for legal_name in self.unnamed:
            self.assertNotIn(f'"{legal_name}"', raw)
        for cnpj in self.cnpjs:
            self.assertNotIn(cnpj, raw)
        self.assertEqual(re.findall(r'"cnpj":"', raw), [])

    def test_every_dashboard_page_runs_from_the_package(self):
        from streamlit.testing.v1 import app_test
        # tests/test_dashboard.py apaga a pasta compartilhada do AppTest ao terminar; recria se preciso.
        os.makedirs(app_test.TMP_DIR.name, exist_ok=True)
        st.cache_data.clear()
        st.cache_resource.clear()
        with mock.patch.dict(os.environ, {"RADAR_SNAPSHOT": str(self.path)}):
            for page in PAGES:
                st.cache_resource.clear()
                at = AppTest.from_string(f"from radar_combustiveis.dashboard import views\n"
                                         f"views.guarded(views.{page})()", default_timeout=60)
                at.run()
                self.assertFalse(at.exception, (page, [e.value for e in at.exception]))
                self.assertEqual([e.value for e in at.error], [], page)
                captions = " ".join(c.value for c in at.caption)
                self.assertIn("**Demonstrativo:**", captions, page)
                self.assertNotIn("Documentação interativa da API", captions, page)
