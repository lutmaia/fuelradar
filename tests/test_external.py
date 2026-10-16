"""Fontes externas (Marco 9): leitura, disponibilidade (*as-of*), qualidade, download e carga.

Dados sintéticos de resposta conhecida; os testes de carga exigem RADAR_TEST_DATABASE_URL.
"""

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import uuid

try:
    import psycopg
    from psycopg.conninfo import make_conninfo
except ImportError:  # pragma: no cover
    psycopg = None

from tests.test_ingestion import write_xlsx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.db.connection import connect  # noqa: E402
from radar_combustiveis.db.migrate import apply_migrations  # noqa: E402
from radar_combustiveis.external import asof, fetch, load, parse, pipeline, quality, sources  # noqa: E402
from radar_combustiveis.ingestion.download import DownloadError, append_log  # noqa: E402

TEST_URL = os.environ.get("RADAR_TEST_DATABASE_URL")
DIST_HEADER = ["DATA INICIAL", "DATA FINAL", "REGIÃO", "ESTADO", "PRODUTO", "UNIDADE DE MEDIDA",
               "PREÇO MÉDIO DISTRIBUIÇÃO", "DESVIO PADRÃO"]
DIST_MUN_HEADER = DIST_HEADER[:4] + ["MUNICÍPIO"] + DIST_HEADER[4:]
PREAMBLE = ("AGÊNCIA NACIONAL DO PETRÓLEO", "INTERVALO DE TEMPO: SEMANAL", "")


def sunday(n):
    return date(2026, 8, 2) + timedelta(weeks=n)


def dist_rows(weeks=4, uf="SAO PAULO", product="GASOLINA C COMUM", base=5.40):
    return [[datetime.combine(sunday(n), datetime.min.time()), datetime.combine(sunday(n) + timedelta(days=6),
             datetime.min.time()), "SUDESTE", uf, product, "R$/l", base + n / 100, 0.05] for n in range(weeks)]


class FakeSheet:
    """Planilha com a interface do xlrd, no formato da ANP de produtores."""

    def __init__(self, rows):
        self.rows = rows
        self.nrows, self.ncols = len(rows), max(len(r) for r in rows)

    def cell_value(self, r, c):
        row = self.rows[r]
        return row[c] if c < len(row) else ""


def excel(day):
    return float((day - date(1899, 12, 30)).days)


def producer_sheet(weeks=3):
    rows = [["Agência Nacional do Petróleo"], [""], ["Produto", "Período", "", "Região", "", "", "", "", "Brasil"],
            ["", "(A partir de 2013)", "", "Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", ""]]
    for n in range(weeks):
        start = sunday(n) + timedelta(days=1)  # semana de segunda a domingo
        rows.append(["Gasolina A Comum (R$/litro)", excel(start), excel(start + timedelta(days=6)),
                     3.1, 3.2, "***", 3.3, 3.4 + n / 100, 3.35])
    rows.append(["Querosene de Aviação - QAV (R$/litro)", excel(sunday(0)), excel(sunday(0) + timedelta(days=6)),
                 4.0, 4.0, 4.0, 4.0, 4.0, 4.0])
    rows.append(["Nota: a estimativa de atualização é de doze dias.", "", "", "", "", "", "", "", ""])
    return FakeSheet(rows)


# -- Leitura ----------------------------------------------------------------------------------


class ParseTests(unittest.TestCase):
    def test_dollar_json(self):
        rows = parse.parse_dollar(json.dumps([{"data": "01/11/2022", "valor": "5.1500"},
                                              {"data": "03/11/2022", "valor": "5.1349"}]).encode())
        self.assertEqual([(r["period_start"], r["value"], r["geo"], r["product"]) for r in rows],
                         [(date(2022, 11, 1), 5.15, "BR", "USD_BRL_VENDA"), (date(2022, 11, 3), 5.1349, "BR", "USD_BRL_VENDA")])
        for bad in (b"<html>", b"[]", json.dumps([{"data": "x", "valor": "1"}]).encode()):
            with self.assertRaises(parse.FormatError):
                parse.parse_dollar(bad)

    def test_producers_keep_known_products_and_skip_missing_regions(self):
        rows = parse.parse_producers_sheet(producer_sheet())
        self.assertEqual({r["product"] for r in rows}, {"GASOLINA_A_COMUM"})  # QAV não é usado
        week0 = [r for r in rows if r["period_start"] == sunday(0) + timedelta(days=1)]
        self.assertEqual({r["geo"]: r["value"] for r in week0},
                         {"NORTE": 3.1, "NORDESTE": 3.2, "SUL": 3.3, "SUDESTE": 3.4, "BRASIL": 3.35})  # sem Centro-Oeste (***)
        self.assertEqual({r["geo_level"] for r in week0 if r["geo"] == "BRASIL"}, {"pais"})
        self.assertEqual(week0[0]["period_end"] - week0[0]["period_start"], timedelta(days=6))

    def test_producers_with_other_columns_are_refused(self):
        sheet = producer_sheet()
        sheet.rows[3][7] = "Sudoeste"
        with self.assertRaises(parse.FormatError):
            parse.parse_producers_sheet(sheet)
        with self.assertRaises(parse.FormatError):
            parse.parse_producers_sheet(FakeSheet([["Outra planilha"]] * 3))

    def test_distribution_keeps_target_uf_known_products_and_skips_dashes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "estados.xlsx"
            rows = dist_rows(3) + dist_rows(2, uf="RIO DE JANEIRO") + dist_rows(1, product="QUEROSENE")
            rows.append([datetime(2026, 8, 30), datetime(2026, 9, 5), "SUDESTE", "SAO PAULO", "ETANOL HIDRATADO COMUM",
                         "R$/l", "-", "-"])
            write_xlsx(path, DIST_HEADER, rows, PREAMBLE)
            got = parse.parse_distribution(path, ("SP",))
        self.assertEqual(len(got), 3)
        self.assertEqual({(r["geo_level"], r["geo"], r["product"], r["unit"]) for r in got},
                         {("uf", "SP", "GASOLINA_COMUM", "BRL/L")})
        self.assertEqual(got[1]["value"], 5.41)

    def test_distribution_municipal_file_uses_normalized_names(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "municipios.xlsx"
            rows = [r[:4] + ["São José dos Campos"] + r[4:] for r in dist_rows(2)]
            write_xlsx(path, DIST_MUN_HEADER, rows, PREAMBLE)
            got = parse.parse_distribution(path, ("SP",))
        self.assertEqual({(r["geo_level"], r["geo"]) for r in got}, {("municipio", "SAO JOSE DOS CAMPOS")})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "outra.xlsx"
            write_xlsx(path, ["DATA", "VALOR"], [[1, 2]], PREAMBLE)
            with self.assertRaises(parse.FormatError):
                parse.parse_distribution(path, ("SP",))


# -- Disponibilidade e as-of ------------------------------------------------------------------


class AvailabilityTests(unittest.TestCase):
    def test_rules_by_source(self):
        self.assertEqual(sources.rule_available_at("bcb_sgs_1", date(2026, 10, 13)), date(2026, 10, 14))
        self.assertEqual(sources.rule_available_at("anp_produtores", date(2026, 10, 4)), date(2026, 10, 16))
        self.assertEqual(sources.rule_available_at("anp_distribuicao", date(2026, 8, 29)), date(2026, 9, 30))
        self.assertEqual(sources.rule_available_at("anp_distribuicao", date(2026, 12, 5)), date(2027, 1, 31))
        self.assertEqual(sources.rule_available_at("anp_distribuicao", date(2026, 11, 30)), date(2026, 12, 31))

    def test_first_download_before_the_rule_wins_but_never_moves_later(self):
        self.assertEqual(sources.available_at("anp_produtores", date(2026, 10, 4), date(2026, 10, 15)),
                         date(2026, 10, 15))
        self.assertEqual(sources.available_at("anp_distribuicao", date(2023, 1, 7), date(2026, 10, 15)),
                         date(2023, 2, 28))  # histórico baixado hoje: vale a regra

    def test_as_of_uses_only_what_was_available(self):
        obs = [{"period_end": date(2026, 8, 29), "available_at": date(2026, 9, 30), "value": 5.45},
               {"period_end": date(2026, 8, 22), "available_at": date(2026, 9, 30), "value": 5.44},
               {"period_end": date(2026, 7, 25), "available_at": date(2026, 8, 31), "value": 5.40}]
        self.assertEqual(asof.as_of(obs, date(2026, 9, 29))["value"], 5.40)
        self.assertEqual(asof.as_of(obs, date(2026, 9, 30))["value"], 5.45)
        self.assertIsNone(asof.as_of(obs, date(2026, 8, 30)))


# -- Qualidade --------------------------------------------------------------------------------


def row(start, value=5.4, product="GASOLINA_COMUM", geo="SP", level="uf", source="anp_distribuicao", days=6):
    return {"source_id": source, "product": product, "geo_level": level, "geo": geo, "uf": "SP", "period_start": start,
            "period_end": start + timedelta(days=days), "value": value, "stddev": None, "unit": "BRL/L"}


class QualityTests(unittest.TestCase):
    def test_clean_weekly_series_is_ok(self):
        rows = [row(sunday(n)) for n in range(4)]
        self.assertEqual(quality.check("anp_distribuicao", rows, sunday(3) + timedelta(days=30))["decision"], "ok")

    def test_critical_problems_block_the_source(self):
        cases = {"repetida": [row(sunday(0)), row(sunday(0))],
                 "fora da faixa": [row(sunday(0), value=54.0)],
                 "período incoerente": [row(sunday(0), days=3)],
                 "nenhuma linha": []}
        for expected, rows in cases.items():
            report = quality.check("anp_distribuicao", rows, sunday(1))
            self.assertEqual(report["decision"], "bloquear", expected)
            self.assertIn(expected, " ".join(report["critical"]), expected)

    def test_gaps_and_lag_are_warnings(self):
        rows = [row(sunday(0)), row(sunday(3))]
        report = quality.check("anp_distribuicao", rows, sunday(3) + timedelta(days=100))
        self.assertEqual(report["decision"], "aviso")
        self.assertIn("2 semana(s) sem valor", " ".join(report["warnings"]))
        self.assertIn("dias antes do download", " ".join(report["warnings"]))
        municipal = [row(sunday(0), level="municipio", geo="ITU"), row(sunday(3), level="municipio", geo="ITU")]
        self.assertEqual(quality.check("anp_distribuicao", municipal, sunday(3))["decision"], "ok")


# -- Download ---------------------------------------------------------------------------------


class FetchTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.raw, self.log = Path(folder.name) / "raw", Path(folder.name) / "processed" / "downloads.jsonl"
        self.raw.mkdir()
        self.items = [("bcb_sgs_1", "sgs1.json", "https://api.bcb.gov.br/x")]

    def run_with(self, content, now):
        def fake_fetch(url, dest, **_):
            if isinstance(content, Exception):
                raise content
            Path(dest).write_bytes(content)
            import hashlib
            return {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content), "head": content[:8],
                    "content_type": "application/json", "http_status": 200}
        with mock.patch.object(fetch, "fetch_to_file", fake_fetch):
            return fetch.download(self.raw, self.log, now, self.items)

    def test_new_content_is_saved_same_content_is_not_and_errors_keep_the_last_file(self):
        first = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
        report = self.run_with(b'[{"data": "01/11/2022", "valor": "5.15"}]', first)
        self.assertEqual(len(report["saved"]), 1)
        saved = self.raw / report["saved"][0]
        self.assertTrue(saved.exists())
        again = self.run_with(b'[{"data": "01/11/2022", "valor": "5.15"}]', first + timedelta(days=1))
        self.assertEqual((again["saved"], again["duplicate"]), ([], ["sgs1.json"]))
        failed = self.run_with(DownloadError("HTTP 503"), first + timedelta(days=2))
        self.assertEqual(len(failed["errors"]), 1)
        latest = fetch.latest_files(self.log)[("bcb_sgs_1", "sgs1.json")]
        self.assertEqual(latest["raw_path"], report["saved"][0])
        self.assertEqual(latest["first_retrieved_at"], first.isoformat(timespec="seconds"))
        self.assertEqual(latest["retrieved_at"], (first + timedelta(days=1)).isoformat(timespec="seconds"))

    def test_error_pages_are_not_saved(self):
        report = self.run_with(b"<html>erro</html>", datetime(2026, 10, 14, tzinfo=timezone.utc))
        self.assertEqual((report["saved"], len(report["errors"])), ([], 1))
        self.assertEqual(list((self.raw).rglob("*.json")), [])
        self.items = [("anp_produtores", "p.xls", "https://www.gov.br/x")]
        self.assertEqual(len(self.run_with(b"PK\x03\x04xx", datetime(2026, 10, 14, tzinfo=timezone.utc))["errors"]), 1)


# -- Carga no banco ---------------------------------------------------------------------------


@unittest.skipUnless(TEST_URL and psycopg, "RADAR_TEST_DATABASE_URL não definida: banco de teste indisponível")
class LoadTests(unittest.TestCase):
    def setUp(self):
        self.db = f"radar_test_ext_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{self.db}"')
        self.addCleanup(self.drop)
        self.url = make_conninfo(TEST_URL, dbname=self.db)
        with connect(self.url) as conn:
            apply_migrations(conn)

    def drop(self):
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{self.db}" WITH (FORCE)')

    @staticmethod
    def record(sha, retrieved, first=None):
        return {"sha256": sha * 64, "name": "estados.xlsx", "url": "https://www.gov.br/x",
                "raw_path": f"external/anp_distribuicao/{sha}/estados.xlsx", "retrieved_at": retrieved,
                "first_retrieved_at": first or retrieved}

    def rows(self, conn):
        return conn.execute("""SELECT period_start, value, available_at, revised, first_retrieved_at::date
                               FROM external_observation ORDER BY period_start""").fetchall()

    def test_load_is_idempotent_marks_revisions_and_keeps_availability(self):
        weeks = [row(sunday(n), value=5.40 + n / 100) for n in range(3)]
        with connect(self.url) as conn:
            first = load.load_source(conn, "anp_distribuicao", [(self.record("a", "2026-10-15T10:00:00+00:00"), weeks)])
            self.assertEqual((first["inserted"], first["updated"], first["total"]), (3, 0, 3))
            again = load.load_source(conn, "anp_distribuicao", [(self.record("a", "2026-10-16T10:00:00+00:00",
                                                                             "2026-10-15T10:00:00+00:00"), weeks)])
            self.assertEqual((again["inserted"], again["updated"]), (0, 0))
            # A ANP corrige a semana 1 e publica a semana 3 num arquivo novo, baixado em 22/10.
            revised = [dict(weeks[1], value=5.50), row(sunday(3), value=5.43)]
            third = load.load_source(conn, "anp_distribuicao", [(self.record("b", "2026-10-22T10:00:00+00:00"), revised)])
            self.assertEqual((third["inserted"], third["updated"], third["revised"], third["total"]), (1, 1, 1, 4))
            got = self.rows(conn)
        self.assertEqual([(r[0], float(r[1]), r[3]) for r in got],
                         [(sunday(0), 5.40, False), (sunday(1), 5.50, True), (sunday(2), 5.42, False),
                          (sunday(3), 5.43, False)])
        # 2026-08-08 é sábado de agosto: regra = 30/09, antes do primeiro download (15/10).
        self.assertEqual(got[0][2], date(2026, 9, 30))
        self.assertEqual(got[1][4], date(2026, 10, 15))  # a revisão não muda quando o valor apareceu
        with connect(self.url) as conn:
            files = conn.execute("SELECT count(*) FROM external_file").fetchone()[0]
            sources_ = conn.execute("SELECT count(*) FROM external_source").fetchone()[0]
        self.assertEqual((files, sources_), (2, 3))

    def test_blocked_source_is_not_loaded_and_others_are(self):
        with tempfile.TemporaryDirectory() as folder:
            raw, processed = Path(folder) / "raw", Path(folder) / "processed"
            ok = raw / "external" / "bcb_sgs_1" / "r" / "sgs1.json"
            ok.parent.mkdir(parents=True)
            ok.write_bytes(json.dumps([{"data": "01/11/2022", "valor": "5.15"}]).encode())
            bad = raw / "external" / "anp_distribuicao" / "r" / "estados.xlsx"
            bad.parent.mkdir(parents=True)
            write_xlsx(bad, DIST_HEADER, dist_rows(2, base=54.0), PREAMBLE)  # preço impossível
            log = processed / "external" / "downloads.jsonl"
            log.parent.mkdir(parents=True)
            for source, name, path in (("bcb_sgs_1", "sgs1.json", ok), ("anp_distribuicao", "estados.xlsx", bad)):
                import hashlib
                append_log(log, {
                    "source_id": source, "name": name, "url": "https://x", "action": "saved",
                    "retrieved_at": "2026-10-15T10:00:00+00:00", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "raw_path": path.relative_to(raw).as_posix()})
            with connect(self.url) as conn:
                report = pipeline.run(raw, processed, ("SP",), conn=conn, download=False,
                                      now=datetime(2026, 10, 15, tzinfo=timezone.utc))
                loaded = dict(conn.execute("SELECT source_id, count(*) FROM external_observation GROUP BY 1").fetchall())
            self.assertTrue((processed / "external" / "quality.json").exists())
        self.assertEqual(report["sources"]["anp_distribuicao"]["decision"], "bloquear")
        self.assertEqual(report["sources"]["anp_produtores"]["decision"], "bloquear")  # nenhum arquivo
        self.assertEqual(loaded, {"bcb_sgs_1": 1})


if __name__ == "__main__":
    unittest.main()
