"""Banco PostgreSQL (Marco 4): migrações, carga, revisão, precedência, integridade e agregações.

Exige um servidor real. Defina RADAR_TEST_DATABASE_URL com uma URL de superusuário/criador de
bancos; cada teste cria e remove o próprio banco (`radar_test_*`), sem tocar no banco `radar`.
Com o contêiner do docker-compose.yml no ar (PowerShell):

    $pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
    $env:RADAR_TEST_DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/postgres"

Use 127.0.0.1, não localhost (IPv6 primeiro, ~30 s por conexão). Sem a variável, os testes são
ignorados e a suíte continua válida.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import statistics
import tempfile
import unittest
import uuid

try:
    import psycopg
    from psycopg import errors
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
except ImportError:  # pragma: no cover - dependência opcional para quem não usa o banco
    psycopg = None

from tests.test_ingestion import HISTORICAL_HEADER, WEEKLY_HEADER, read_csv, write_csv, write_xlsx
from tests.test_quality import make_cnpj

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.db.connection import connect  # noqa: E402
from radar_combustiveis.db.load import LoadError, load_database  # noqa: E402
from radar_combustiveis.db.migrate import MIGRATIONS_DIR, MigrationError, apply_migrations  # noqa: E402
from radar_combustiveis.ingestion.normalize import PRODUCTS  # noqa: E402
from radar_combustiveis.ingestion.pipeline import run_ingestion  # noqa: E402
from radar_combustiveis.quality.pipeline import run_quality  # noqa: E402
from radar_combustiveis.quality.rules import PRODUCT_UNITS  # noqa: E402

TEST_URL = os.environ.get("RADAR_TEST_DATABASE_URL")
AS_OF = date(2026, 10, 10)


def xrow(station, day, price, product="GASOLINA COMUM", unit="R$/l", city="Jundiaí", brand="BRANCA"):
    return [f"POSTO {station} LTDA", f"POSTO {station}", int(make_cnpj(station)), "RUA A", "10", None, "CENTRO",
            13201000, city, "SAO PAULO", product, unit, price, datetime(day.year, day.month, day.day), brand]


def week_name(start):
    return f"revendas_lpc_{start.isoformat()}_{(start + timedelta(days=6)).isoformat()}.xlsx"


def masked(cnpj):
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


@unittest.skipUnless(TEST_URL and psycopg, "RADAR_TEST_DATABASE_URL não definida: banco de teste indisponível")
class DatabaseCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        base = Path(folder.name)
        self.raw, self.out, self.quarantine = base / "raw", base / "processed", base / "quarantine"
        self.raw.mkdir()
        self.db_name = f"radar_test_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{self.db_name}"')
        self.addCleanup(self.drop_database)
        self.url = make_conninfo(TEST_URL, dbname=self.db_name)
        with connect(self.url) as conn:
            apply_migrations(conn)

    def drop_database(self):
        with psycopg.connect(TEST_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{self.db_name}" WITH (FORCE)')

    # -- auxiliares ---------------------------------------------------------------------------

    def write_week(self, start, rows):
        write_xlsx(self.raw / week_name(start), WEEKLY_HEADER, rows)

    def pipeline(self):
        """Ingestão e qualidade sobre o raw sintético; devolve o relatório de qualidade."""
        ingestion = run_ingestion(self.raw, self.out, self.quarantine, ("SP",))
        self.assertEqual(ingestion["errors"], [])
        return run_quality(self.out, self.quarantine, AS_OF)

    def load(self):
        return load_database(self.url, self.out, self.quarantine)

    def query(self, sql, params=()):
        with connect(self.url) as conn:
            return conn.execute(sql, params).fetchall()

    def scalar(self, sql, params=()):
        return self.query(sql, params)[0][0]

    def snapshot(self):
        """Estado comparável do banco para provar que uma operação não alterou nada."""
        tables = ["dim_location", "dim_product", "dim_station", "fact_price_observation", "quarantine_observation",
                  "source_file"]
        return {t: self.scalar(f"SELECT count(*) FROM {t}") for t in tables} | {
            "current": self.scalar("SELECT count(*) FROM fact_price_observation WHERE is_current_source_revision")}


class MigrationTests(DatabaseCase):
    def test_apply_is_idempotent_and_ordered(self):
        with connect(self.url) as conn:
            self.assertEqual(apply_migrations(conn), [])
        versions = [r[0] for r in self.query("SELECT version FROM schema_migration ORDER BY version")]
        self.assertEqual(versions, ["0001_schema.sql", "0002_marts.sql", "0003_api_reader.sql", "0004_forecasts.sql",
                                    "0005_external.sql", "0006_holdout_access.sql",
                                    "0007_live.sql"])

    def test_changed_applied_migration_is_rejected(self):
        copy = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, copy, True)
        for path in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copy(path, copy / path.name)
        (copy / "0001_schema.sql").write_text("-- alterada\n" + (copy / "0001_schema.sql").read_text(encoding="utf-8"),
                                              encoding="utf-8")
        with connect(self.url) as conn, self.assertRaises(MigrationError):
            apply_migrations(conn, copy)

    def test_failed_migration_leaves_nothing_behind(self):
        copy = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, copy, True)
        (copy / "0001_ok.sql").write_text("CREATE TABLE t_ok (id int);", encoding="utf-8")
        (copy / "0002_bad.sql").write_text("CREATE TABLE t_half (id int); SELECT 1/0;", encoding="utf-8")
        with connect(self.url) as conn:
            with self.assertRaises(psycopg.Error):
                apply_migrations(conn, copy)
        tables = {r[0] for r in self.query("SELECT table_name FROM information_schema.tables WHERE table_schema='radar'")}
        self.assertIn("t_ok", tables)
        self.assertNotIn("t_half", tables)
        self.assertNotIn("0002_bad.sql", {r[0] for r in self.query("SELECT version FROM schema_migration")})

    def test_dim_product_mirrors_normalization_and_quality_rules(self):
        rows = {r[0]: r[1] for r in self.query("SELECT canonical_name, unit FROM dim_product")}
        self.assertEqual(set(rows), set(PRODUCTS.values()))
        self.assertEqual(rows, PRODUCT_UNITS)


class LoadTests(DatabaseCase):
    def week_with(self, start, stations, price=lambda s: 5.90 + s / 100, **kw):
        self.write_week(start, [xrow(s, start + timedelta(days=2), price(s), **kw) for s in stations])

    def test_loads_dimensions_facts_and_audit_columns(self):
        start = date(2026, 9, 20)
        self.write_week(start, [xrow(1, date(2026, 9, 22), 5.99), xrow(2, date(2026, 9, 23), 6.19, product="ETANOL"),
                                xrow(3, date(2026, 9, 24), 110.0, product="GLP", unit="R$/13kg"),
                                xrow(2, date(2026, 9, 22), 5.89, brand=None)])
        report = self.pipeline()
        self.assertEqual(report["decision"], "publicar_com_aviso")  # última coleta há 16 dias
        summary = self.load()
        self.assertEqual((summary["status"], summary["rows_staged"], summary["inserted"]), ("warning", 3, 3))
        self.assertEqual(self.scalar("SELECT count(*) FROM fact_price_observation WHERE is_current_source_revision"), 3)
        self.assertEqual(self.scalar("SELECT count(*) FROM dim_station"), 2)  # o posto 3 só tem GLP
        self.assertEqual(self.query("SELECT uf, municipality_name_normalized FROM dim_location"), [("SP", "JUNDIAI")])
        facts = self.query("""
            SELECT s.cnpj, p.canonical_name, f.collection_date, f.week_start, f.sale_price, f.quality_status,
                   f.row_key, f.source_row_number
            FROM fact_price_observation f JOIN dim_station s USING (station_id) JOIN dim_product p USING (product_id)
            ORDER BY f.collection_date, s.cnpj""")
        self.assertEqual(facts[0][:6], (make_cnpj(1), "GASOLINA_COMUM", date(2026, 9, 22), date(2026, 9, 20),
                                        Decimal("5.99"), "ok"))
        self.assertTrue(all(f[3].weekday() == 6 for f in facts))  # semana começa no domingo
        self.assertEqual(facts[0][6], f"SP|JUNDIAI|{make_cnpj(1)}|GASOLINA_COMUM|BRL/L|2026-09-22")
        source = self.query("SELECT is_current, kinds, reference_start, reference_end, storage_uri FROM source_file")
        self.assertEqual(source, [(True, ["retail_observation"], date(2026, 9, 20), date(2026, 9, 26),
                                   "raw/" + week_name(start))])
        run = self.query("SELECT status, rows_accepted, rows_quarantined, quality_decision, finished_at IS NOT NULL "
                         "FROM ingestion_run")
        self.assertEqual(run, [("warning", 3, 0, "publicar_com_aviso", True)])

    def test_reload_is_idempotent(self):
        self.week_with(date(2026, 9, 20), range(1, 6))
        self.pipeline()
        first = self.load()
        before = self.snapshot()
        second = self.load()
        self.assertEqual((first["inserted"], second["inserted"], second["updated"], second["retired"]), (5, 0, 0, 0))
        self.assertEqual(second["unchanged"], 5)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.scalar("SELECT count(*) FROM ingestion_run WHERE status <> 'failed'"), 2)

    def test_new_file_adds_rows_without_touching_existing_ones(self):
        self.week_with(date(2026, 9, 13), range(1, 4))
        self.pipeline()
        self.load()
        self.week_with(date(2026, 9, 20), range(1, 6))
        self.pipeline()
        summary = self.load()
        self.assertEqual((summary["inserted"], summary["unchanged"], summary["retired"]), (5, 3, 0))
        self.assertEqual(self.scalar("SELECT count(*) FROM fact_price_observation WHERE is_current_source_revision"), 8)
        self.assertEqual(self.scalar("SELECT count(DISTINCT station_id) FROM fact_price_observation"), 5)
        self.assertEqual(self.query("SELECT min(first_seen_date), max(last_seen_date) FROM dim_station"),
                         [(date(2026, 9, 15), date(2026, 9, 22))])

    def test_source_revision_replaces_derived_rows_and_keeps_history(self):
        start = date(2026, 9, 20)
        self.week_with(start, range(1, 5))
        self.pipeline()
        self.load()
        # Revisão da ANP: mesmo nome, conteúdo diferente (um preço corrigido, um posto a menos, um novo).
        self.write_week(start, [xrow(1, date(2026, 9, 22), 6.45), xrow(2, date(2026, 9, 22), 5.92),
                                xrow(3, date(2026, 9, 22), 5.93), xrow(9, date(2026, 9, 22), 6.01)])
        self.pipeline()
        summary = self.load()
        self.assertEqual(summary["retired"], 4)  # as quatro linhas da revisão 1 deixam de ser vigentes
        self.assertEqual(summary["inserted"], 4)
        files = self.query("SELECT revision, is_current FROM source_file ORDER BY revision")
        self.assertEqual(files, [(1, False), (2, True)])
        current = dict(self.query("""
            SELECT s.cnpj, f.sale_price FROM fact_price_observation f JOIN dim_station s USING (station_id)
            WHERE f.is_current_source_revision"""))
        self.assertEqual(current, {make_cnpj(1): Decimal("6.45"), make_cnpj(2): Decimal("5.92"),
                                   make_cnpj(3): Decimal("5.93"), make_cnpj(9): Decimal("6.01")})
        self.assertEqual(self.scalar("SELECT count(*) FROM fact_price_observation"), 8)  # histórico preservado
        old = self.scalar("""SELECT count(*) FROM fact_price_observation f JOIN source_file sf USING (source_file_id)
                             WHERE sf.revision = 1 AND NOT f.is_current_source_revision""")
        self.assertEqual(old, 4)
        self.assertEqual(self.load()["inserted"], 0)  # estável depois da revisão

    def test_overlap_between_sources_keeps_one_current_row_after_the_weekly_file_arrives(self):
        cnpj = make_cnpj(7)
        historical = [["SE", "SP", "JUNDIAI", "POSTO 7", masked(cnpj), "RUA A", "10", "", "CENTRO", "13201-000",
                       "GASOLINA", day, price, "", "R$ / litro", "BRANCA"]
                      for day, price in (("29/06/2026", "6,50"), ("30/06/2026", "6,55"), ("01/06/2026", "6,40"))]
        write_csv(self.raw / "Preços semestrais - AUTOMOTIVOS_2026.01.csv", HISTORICAL_HEADER, historical)
        self.pipeline()
        self.load()
        self.assertEqual(self.scalar("SELECT count(*) FROM fact_price_observation WHERE is_current_source_revision"), 3)
        # Chega a semana publicada, com a mesma chave em 29/06 (preço 6.5 = 6,50) e uma nova em 01/07.
        self.write_week(date(2026, 6, 28), [xrow(7, date(2026, 6, 29), 6.5), xrow(7, date(2026, 7, 1), 6.6)])
        report = self.pipeline()
        self.assertEqual(report["reconciliation"]["rows_duplicate_removed"], 1)
        summary = self.load()
        self.assertEqual((summary["inserted"], summary["retired"]), (2, 1))
        current = self.query("""
            SELECT f.collection_date, sf.period_key, f.duplicate_sources FROM fact_price_observation f
            JOIN source_file sf USING (source_file_id) WHERE f.is_current_source_revision ORDER BY 1""")
        self.assertEqual([(c[0], c[1]) for c in current], [
            (date(2026, 6, 1), "Preços semestrais - AUTOMOTIVOS_2026.01"),
            (date(2026, 6, 29), "revendas_lpc_2026-06-28_2026-07-04"),
            (date(2026, 6, 30), "Preços semestrais - AUTOMOTIVOS_2026.01"),
            (date(2026, 7, 1), "revendas_lpc_2026-06-28_2026-07-04")])
        self.assertEqual(len(current[1][2]), 1)  # a cópia removida fica registrada
        self.assertEqual(self.scalar("SELECT count(*) FROM fact_price_observation"), 5)  # nada foi apagado

    def test_quarantine_rows_are_loaded_with_reasons_and_original_values(self):
        start = date(2026, 9, 20)
        rows = [xrow(s, date(2026, 9, 22), 5.90 + s / 100) for s in range(1, 41)]
        rows += [xrow(50, date(2026, 9, 22), 0.0), xrow(51, date(2026, 9, 22), 59.0)]
        self.write_week(start, rows)
        report = self.pipeline()
        self.assertEqual(report["reconciliation"]["rows_quarantined"], 2)
        summary = self.load()
        self.assertEqual((summary["rows_staged"], summary["rows_quarantined"]), (40, 2))
        reasons = self.query("SELECT reasons, collection_date, is_current, original->>'sale_price' "
                             "FROM quarantine_observation ORDER BY original->>'sale_price'")
        self.assertEqual(reasons, [(["preco_nao_positivo"], date(2026, 9, 22), True, "0.00"),
                                   (["preco_implausivel"], date(2026, 9, 22), True, "59.00")])
        self.assertEqual(self.scalar("SELECT count(*) FROM fact_price_observation"), 40)
        self.assertEqual(self.load()["rows_quarantined"], 2)
        self.assertEqual(self.scalar("SELECT count(*) FROM quarantine_observation"), 2)


class SafetyTests(DatabaseCase):
    def good_load(self):
        start = date(2026, 9, 20)
        self.write_week(start, [xrow(s, date(2026, 9, 22), 5.90 + s / 100) for s in range(1, 6)])
        self.pipeline()
        self.load()
        return self.snapshot()

    def failed_runs(self):
        return self.query("SELECT status, error_summary FROM ingestion_run WHERE status = 'failed'")

    def test_blocked_quality_refuses_the_load_and_changes_nothing(self):
        before = self.good_load()
        self.write_week(date(2026, 9, 27), [xrow(s, date(2026, 9, 29), 0.0) for s in range(1, 4)])
        self.assertEqual(self.pipeline()["decision"], "bloquear")
        with self.assertRaises(LoadError):
            self.load()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.failed_runs()), 1)
        self.assertIn("bloqueou", self.failed_runs()[0][1])

    def test_failure_in_the_middle_rolls_back_dimensions_and_files(self):
        before = self.good_load()
        self.write_week(date(2026, 9, 27), [xrow(s, date(2026, 9, 29), 5.90 + s / 100) for s in range(20, 23)])
        self.pipeline()
        staging = self.out / "staging" / "observations.csv"
        rows = read_csv(staging)
        victim = rows[-1]  # posto novo; o preço negativo só falha na inserção do fato
        text = staging.read_text(encoding="utf-8").replace(f",{victim['sale_price']},", ",-1,", 1)
        staging.write_text(text, encoding="utf-8")
        with self.assertRaises(psycopg.Error):
            self.load()
        self.assertEqual(self.snapshot(), before)  # nem a dimensão nem o arquivo de origem novos ficaram
        failed = self.failed_runs()
        self.assertEqual(len(failed), 1)
        self.assertNotIn(victim["cnpj"], failed[0][1])  # resumo sem valores de linha

    def test_inconsistent_output_files_are_refused(self):
        before = self.good_load()
        staging = self.out / "staging" / "observations.csv"
        lines = staging.read_text(encoding="utf-8").splitlines(keepends=True)
        staging.write_text("".join(lines[:-1]), encoding="utf-8")  # uma linha a menos que o relatório
        with self.assertRaises(LoadError):
            self.load()
        self.assertEqual(self.snapshot(), before)

    def test_unknown_product_is_refused(self):
        before = self.good_load()
        staging = self.out / "staging" / "observations.csv"
        staging.write_text(staging.read_text(encoding="utf-8").replace("GASOLINA_COMUM", "GASOLINA_X"),
                           encoding="utf-8")
        with self.assertRaises(LoadError):
            self.load()
        self.assertEqual(self.snapshot(), before)

    def test_database_rejects_inconsistent_rows(self):
        self.good_load()
        base = ("SELECT source_file_id, station_id, location_id, product_id FROM fact_price_observation LIMIT 1")
        with connect(self.url) as conn:
            sf, st, loc, prod = conn.execute(base).fetchone()
            run = conn.execute("SELECT run_id FROM ingestion_run LIMIT 1").fetchone()[0]
            key = conn.execute("SELECT row_key FROM fact_price_observation LIMIT 1").fetchone()[0]

            def insert(row_key, day, week, price, hash_value):
                with conn.transaction():
                    conn.execute("""
                        INSERT INTO fact_price_observation (source_file_id, station_id, location_id, product_id,
                            collection_date, week_start, sale_price, row_key, source_row_hash, source_row_number,
                            quality_status, is_current_source_revision, loaded_run_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 99, 'ok', true, %s)""",
                                 (sf, st, loc, prod, day, week, price, row_key, hash_value, run))

            with self.assertRaises(errors.UniqueViolation):  # mesma chave de negócio vigente
                insert(key, date(2026, 9, 22), date(2026, 9, 20), "5.00", "h1")
            with self.assertRaises(errors.CheckViolation):  # semana não começa no domingo
                insert("outra", date(2026, 9, 22), date(2026, 9, 21), "5.00", "h2")
            with self.assertRaises(errors.CheckViolation):  # preço não positivo
                insert("outra", date(2026, 9, 22), date(2026, 9, 20), "0", "h3")
            with self.assertRaises(errors.ForeignKeyViolation):  # produto inexistente
                with conn.transaction():
                    conn.execute("UPDATE fact_price_observation SET product_id = 999")
            with self.assertRaises(errors.UniqueViolation):  # duas revisões vigentes do mesmo período
                with conn.transaction():
                    conn.execute("""INSERT INTO source_file (source_file_id, run_id, sha256, period_key, revision,
                        is_current, kinds, storage_uri, size_bytes, first_seen_at)
                        SELECT '0123456789abcdef', %s, repeat('a', 64), period_key, 2, true, kinds, 'x', 1, now()
                        FROM source_file LIMIT 1""", (run,))


class MartTests(DatabaseCase):
    def test_weekly_aggregates_and_coverage_match_independent_calculations(self):
        start = date(2026, 7, 26)
        prices = {}
        for n in range(10):
            week = start + timedelta(weeks=n)
            monday = week + timedelta(days=1)
            rows = []
            for s in range(1, 9 if n < 9 else 3):  # Jundiaí perde cobertura na última semana
                price = round(5.90 + (s % 5) * 0.07 + n * 0.01, 2)
                prices.setdefault((week, "JUNDIAI"), []).append(Decimal(str(price)))
                rows.append(xrow(s, monday, price))
            for s in range(30, 38):
                price = round(6.20 + (s % 3) * 0.05, 2)
                prices.setdefault((week, "CAMPINAS"), []).append(Decimal(str(price)))
                rows.append(xrow(s, monday, price, city="Campinas"))
            self.write_week(week, rows)
        report = self.pipeline()
        self.assertNotEqual(report["decision"], "bloquear")
        self.load()

        mart = {(r[0], r[1]): r for r in self.query("""
            SELECT m.week_start, l.municipality_name_normalized, m.observation_count, m.station_count, m.price_min,
                   m.price_p25, m.price_median, m.price_mean, m.price_p75, m.price_max, m.price_stddev,
                   m.coverage_ratio, m.quality_flag
            FROM mart_weekly_city_price m JOIN dim_location l USING (location_id)""")}
        self.assertEqual(len(mart), 20)
        for (week, city), values in prices.items():
            row = mart[(week, city)]
            q1, med, q3 = statistics.quantiles(values, n=4, method="inclusive")
            self.assertEqual((row[2], row[3]), (len(values), len(values)))
            self.assertEqual((row[4], row[9]), (min(values), max(values)))
            for got, want in ((row[5], q1), (row[6], med), (row[8], q3)):
                self.assertAlmostEqual(float(got), float(want), places=4)
            self.assertAlmostEqual(float(row[7]), float(statistics.mean(values)), places=4)
            if len(values) > 1:
                self.assertAlmostEqual(float(row[10]), float(statistics.stdev(values)), places=4)

        last = mart[(start + timedelta(weeks=9), "JUNDIAI")]
        self.assertEqual((last[11], last[12]), (Decimal("0.250"), "cobertura_baixa"))  # 2 postos contra mediana 8
        self.assertEqual(mart[(start + timedelta(weeks=9), "CAMPINAS")][12], "ok")
        self.assertEqual(mart[(start + timedelta(weeks=3), "JUNDIAI")][12], "sem_historico")
        self.assertEqual(mart[(start + timedelta(weeks=8), "JUNDIAI")][12], "ok")

        # Segunda implementação (Python, relatório de qualidade) concorda com a do banco.
        coverage = {(date.fromisoformat(r["week_start"]), r["municipality_normalized"]): r
                    for r in read_csv(self.out / "quality" / "coverage_weekly.csv") if r["product"] == "GASOLINA_COMUM"}
        compared = 0
        for key, row in mart.items():
            expected = coverage[key]
            self.assertEqual(int(expected["stations"]), row[3], key)
            self.assertEqual(expected["low_coverage"] == "true", row[12] == "cobertura_baixa", key)
            self.assertEqual(expected["ratio_to_baseline"] == "", row[11] is None, key)
            if row[11] is not None:
                self.assertAlmostEqual(float(expected["ratio_to_baseline"]), float(row[11]), places=3)
            compared += 1
        self.assertEqual(compared, 20)

        state = self.query("SELECT week_start, uf, observation_count, station_count FROM mart_weekly_state_price "
                           "ORDER BY week_start")
        self.assertEqual(state[0], (start, "SP", 16, 16))
        self.assertEqual(state[-1], (start + timedelta(weeks=9), "SP", 10, 10))


if __name__ == "__main__":
    unittest.main()
