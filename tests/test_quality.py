"""Qualidade (Marco 3) com manifesto e observações sintéticas; não dependem de data/."""

import csv
from datetime import date, timedelta
from decimal import Decimal
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import check_quality  # noqa: E402
from radar_combustiveis.ingestion.observations import OBSERVATION_COLUMNS  # noqa: E402
from radar_combustiveis.quality.pipeline import run_quality  # noqa: E402
from radar_combustiveis.quality.rules import (  # noqa: E402
    canonical_price, cnpj_check_digits_ok, price_bounds, row_reasons, week_start,
)

AS_OF = date(2026, 10, 10)


def make_cnpj(n):
    """CNPJ sintético válido (cálculo independente do código testado)."""
    base = f"{n:08d}0001"
    for size in (12, 13):
        weights = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if size == 12 else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        rest = sum(int(d) * w for d, w in zip(base, weights)) % 11
        base += str(0 if rest < 2 else 11 - rest)
    return base


def obs(station=1, day="2026-09-21", price="5.99", product="GASOLINA_COMUM", unit="BRL/L",
        city="JUNDIAI", **overrides):
    cnpj = overrides.pop("cnpj", make_cnpj(station))
    row = {column: "" for column in OBSERVATION_COLUMNS}
    row.update(uf="SP", municipality_original=city, municipality_normalized=city,
               legal_name="POSTO SINTETICO", brand="BRANCA", cnpj=cnpj, cnpj_status="exact_native_integer",
               address="RUA A", cep="13201000", cep_status="exact_native_integer",
               product_original=product, product=product,
               product_category="glp" if product == "GLP" else "automotivo",
               unit_original=unit, unit=unit, collection_date=day, sale_price=price)
    row.update(overrides)
    if "row_key" not in overrides:
        complete = row["cnpj"] and row["product"] and row["unit"] and row["municipality_normalized"]
        row["row_key"] = "|".join([row["uf"], row["municipality_normalized"], row["cnpj"], row["product"],
                                   row["unit"], row["collection_date"]]) if complete else ""
    return row


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class QualityCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.out = Path(folder.name) / "processed"
        self.quarantine = Path(folder.name) / "quarantine"
        self.manifest = {"manifest_version": 1, "files": []}

    def add_file(self, file_id, rows, start=None, end=None, accepted=None, ingested=True,
                 columns=OBSERVATION_COLUMNS, current=True):
        output = f"observations/{file_id}.csv"
        path = self.out / output
        path.parent.mkdir(parents=True, exist_ok=True)
        for number, row in enumerate(rows, start=2):
            row["source_file_id"] = row["source_file_id"] or file_id
            if not row.get("source_row_number"):
                row["source_row_number"] = str(number)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, columns, lineterminator="\n", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        self.manifest["files"].append({
            "source_file_id": file_id, "sha256": file_id * 4, "size_bytes": 1, "paths": [f"{file_id}.csv"],
            "kinds": ["retail_observation"], "period_key": file_id, "reference_start": start,
            "reference_end": end, "revision": 1, "is_current": current, "first_seen_at": "x",
            "source_url": None, "retrieved_at": None,
            "ingestion": {"output": output, "rows_accepted": len(rows) if accepted is None else accepted,
                          "target_ufs": ["SP"]} if ingested else None,
        })

    def run_quality(self, as_of=AS_OF):
        (self.out / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        return run_quality(self.out, self.quarantine, as_of)

    def published(self):
        return read_csv(self.out / "staging" / "observations.csv")

    def quarantined(self):
        return read_csv(self.quarantine / "quality_observations.csv")


class RulesTest(unittest.TestCase):
    def test_canonical_price_does_not_round(self):
        self.assertEqual(canonical_price(Decimal("7.3")), "7.30")
        self.assertEqual(canonical_price(Decimal("7.30")), "7.30")
        self.assertEqual(canonical_price(Decimal("5.999")), "5.999")
        self.assertEqual(canonical_price(Decimal("6")), "6.00")
        self.assertEqual(canonical_price(None), "")

    def test_week_starts_on_sunday(self):
        self.assertEqual(week_start(date(2026, 9, 27)), date(2026, 9, 27))  # domingo
        self.assertEqual(week_start(date(2026, 10, 3)), date(2026, 9, 27))  # sábado
        self.assertEqual(week_start(date(2026, 9, 28)), date(2026, 9, 27))

    def test_cnpj_check_digits(self):
        self.assertTrue(cnpj_check_digits_ok("11222333000181"))
        self.assertTrue(cnpj_check_digits_ok(make_cnpj(4567)))
        self.assertFalse(cnpj_check_digits_ok("11222333000182"))
        self.assertFalse(cnpj_check_digits_ok("1122233300018"))
        # Exemplo alfanumérico publicado pela Receita Federal (12ABC34501DE35).
        self.assertTrue(cnpj_check_digits_ok("12ABC34501DE35"))

    def test_row_reasons_cover_contract(self):
        period = (date(2026, 9, 20), date(2026, 9, 26))
        self.assertEqual(row_reasons(obs(), period, AS_OF), ([], []))
        cases = {
            "preco_nao_positivo": obs(price="0"),
            "preco_ausente_ou_ilegivel": obs(price=""),
            "data_invalida": obs(day="2026-02-30"),
            "data_futura": obs(day="2026-10-11"),
            "data_fora_do_periodo_do_arquivo": obs(day="2026-09-27"),
            "uf_ausente": obs(uf=""),
            "municipio_ausente": obs(city=""),
            "cnpj_ausente": obs(cnpj="", cnpj_status="missing"),
            "cnpj_malformado": obs(cnpj="", cnpj_status="ambiguous_short_text"),
            "cnpj_digito_verificador_invalido": obs(cnpj="11222333000182"),
            "produto_desconhecido": obs(product=""),
            "unidade_desconhecida": obs(unit=""),
            "unidade_incompativel": obs(product="GNV", unit="BRL/L"),
        }
        for reason, row in cases.items():
            with self.subTest(reason=reason):
                self.assertIn(reason, row_reasons(row, period, AS_OF)[0])
        flags = row_reasons(obs(cep="", cep_status="ambiguous_numeric", brand="", address=""), period, AS_OF)[1]
        self.assertEqual(flags, ["cep_ambiguo_ou_invalido", "bandeira_ausente", "endereco_ausente"])

    def test_price_bounds(self):
        self.assertIsNone(price_bounds([Decimal("6")] * 29))
        prices = [Decimal("5.90") + Decimal("0.01") * (i % 20) for i in range(40)]
        bounds = price_bounds(prices)
        self.assertTrue(bounds["plausible"][1] > bounds["fence"][1] > Decimal("6.09"))


class PipelineTest(QualityCase):
    def week_rows(self, day="2026-09-21", stations=range(1, 41), price=lambda s: f"{5.90 + (s % 20) / 100:.2f}"):
        return [obs(station=s, day=day, price=price(s)) for s in stations]

    def test_valid_and_invalid_rows_reconcile(self):
        rows = self.week_rows() + [
            obs(station=101, price="0"), obs(station=102, product="", row_key=""),
            obs(station=103, product="GNV", unit="BRL/L"), obs(station=104, cnpj="11222333000182"),
            obs(station=105, day="2026-09-27"), obs(station=106, product="GLP", unit="BRL/13KG", price="110"),
            obs(station=107, brand=""),
        ]
        report = self.run_quality_with(rows)
        self.assertEqual(report["decision"], "publicar_com_aviso")  # 5 de 47 em quarentena > 1%
        rec = report["reconciliation"]
        self.assertTrue(rec["balanced"])
        self.assertEqual((rec["rows_published"], rec["rows_quarantined"], rec["rows_out_of_scope_product"]), (41, 5, 1))
        reasons = {r["source_row_number"]: r["quality_reasons"] for r in self.quarantined()}
        self.assertEqual(sorted(reasons.values()), sorted([
            "preco_nao_positivo", "produto_desconhecido", "unidade_incompativel",
            "cnpj_digito_verificador_invalido", "data_fora_do_periodo_do_arquivo"]))
        flagged = [r for r in self.published() if r["quality_flags"]]
        self.assertEqual([r["quality_flags"] for r in flagged], ["bandeira_ausente"])
        self.assertNotIn("GLP", {r["product"] for r in self.published()})
        self.assertEqual(report["samples"]["preco_nao_positivo"][0]["sale_price"], "0.00")
        self.assertNotIn("cnpj", report["samples"]["preco_nao_positivo"][0])

    def run_quality_with(self, rows):
        self.add_file("week", rows, "2026-09-20", "2026-09-26")
        return self.run_quality()

    def test_identical_copies_across_sources_keep_weekly(self):
        semester = [obs(station=1, day="2026-06-29", price="7.30"), obs(station=2, day="2026-06-29", price="6.10")]
        weekly = [obs(station=1, day="2026-06-29", price="7.3"), obs(station=2, day="2026-06-29", price="6.20")]
        self.add_file("semester", semester, "2026-01-01", "2026-06-30")
        self.add_file("week", weekly, "2026-06-28", "2026-07-04")
        report = self.run_quality()
        published = self.published()
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["source_file_id"], "week")
        self.assertEqual(published[0]["sale_price"], "7.30")
        self.assertEqual(published[0]["duplicate_sources"], "semester:2")
        conflict = self.quarantined()
        self.assertEqual({r["source_file_id"] for r in conflict}, {"semester", "week"})
        self.assertEqual({r["quality_reasons"] for r in conflict}, {"conflito_de_preco_mesma_chave"})
        self.assertEqual(report["reconciliation"]["rows_duplicate_removed"], 1)
        self.assertTrue(report["reconciliation"]["balanced"])

    def test_diesel_labels_share_one_key_and_s10_stays_apart(self):
        semester = [obs(station=1, day="2026-06-29", price="6.49", product="DIESEL_COMUM",
                        product_original="DIESEL"),
                    obs(station=1, day="2026-06-29", price="6.99", product="DIESEL_S10")]
        weekly = [obs(station=1, day="2026-06-29", price="6.49", product="DIESEL_COMUM",
                      product_original="DIESEL S500"),
                  obs(station=1, day="2026-06-29", price="6.99", product="DIESEL_S10")]
        self.add_file("semester", semester, "2026-01-01", "2026-06-30")
        self.add_file("week", weekly, "2026-06-28", "2026-07-04")
        report = self.run_quality()
        self.assertEqual(sorted(r["product"] for r in self.published()), ["DIESEL_COMUM", "DIESEL_S10"])
        self.assertEqual(report["reconciliation"]["rows_duplicate_removed"], 2)
        self.assertEqual(self.quarantined(), [])

    def test_implausible_price_quarantined_and_rare_price_only_flagged(self):
        rows = self.week_rows() + [obs(station=201, price="64.90"), obs(station=202, price="7.40")]
        report = self.run_quality_with(rows)
        self.assertEqual([r["quality_reasons"] for r in self.quarantined()], ["preco_implausivel"])
        rare = [r for r in self.published() if r["sale_price"] == "7.40"]
        self.assertEqual(rare[0]["quality_flags"], "preco_extremo")
        self.assertEqual(report["counts"]["flag:preco_extremo"], 1)

    def test_rerun_is_idempotent_and_compares_with_previous(self):
        self.run_quality_with(self.week_rows())
        snapshot = {p: p.read_bytes() for p in self.out.rglob("*.csv")}
        report = self.run_quality()
        self.assertFalse(any(report["outputs_written"].values()))
        self.assertEqual(report["comparison"]["delta"], {})
        self.assertEqual({p: p.read_bytes() for p in self.out.rglob("*.csv")}, snapshot)
        self.assertEqual(len(list((self.out / "quality" / "runs").glob("*.json"))), 2)

    def test_only_current_revision_is_evaluated(self):
        self.add_file("old", [obs(price="9.99")], "2026-09-20", "2026-09-26", current=False)
        self.add_file("new", [obs(price="6.09")], "2026-09-20", "2026-09-26")
        self.run_quality()
        self.assertEqual([r["source_file_id"] for r in self.published()], ["new"])


class CriticalTest(QualityCase):
    def publish_baseline(self):
        self.add_file("good", [obs()], "2026-09-20", "2026-09-26")
        report = self.run_quality()
        self.assertEqual(report["decision"], "publicar_com_aviso")  # última coleta há 19 dias
        return (self.out / "staging" / "observations.csv").read_bytes()

    def assert_blocked(self, rule, baseline):
        report = self.run_quality()
        self.assertEqual(report["decision"], "bloquear")
        self.assertIn(rule, {f["rule"] for f in report["critical_failures"]})
        self.assertFalse(any(report["outputs_written"].values()))
        self.assertEqual((self.out / "staging" / "observations.csv").read_bytes(), baseline)
        self.assertEqual(list((self.out / "staging").glob("*.tmp")), [])

    def test_empty_file_blocks_and_keeps_previous_output(self):
        baseline = self.publish_baseline()
        self.add_file("empty", [], "2026-09-27", "2026-10-03")
        self.assert_blocked("arquivo_vazio", baseline)

    def test_no_valid_price_blocks(self):
        baseline = self.publish_baseline()
        self.add_file("zeros", [obs(day="2026-09-28", price="0")], "2026-09-27", "2026-10-03")
        self.assert_blocked("nenhum_preco_valido", baseline)

    def test_no_date_in_period_blocks(self):
        baseline = self.publish_baseline()
        self.add_file("shifted", [obs(day="2026-09-21")], "2026-09-27", "2026-10-03")
        self.assert_blocked("nenhuma_data_no_periodo", baseline)

    def test_load_duplication_blocks(self):
        baseline = self.publish_baseline()
        self.add_file("twice", [obs(day="2026-09-28"), obs(day="2026-09-28", source_row_number="2")],
                      "2026-09-27", "2026-10-03")
        self.assert_blocked("duplicacao_da_carga", baseline)

    def test_count_mismatch_with_manifest_blocks(self):
        baseline = self.publish_baseline()
        self.add_file("short", [obs(day="2026-09-28")], "2026-09-27", "2026-10-03", accepted=5)
        self.assert_blocked("duplicacao_da_carga", baseline)

    def test_extreme_reduction_blocks(self):
        start = date(2026, 8, 2)
        for n in range(4):
            week = start + timedelta(weeks=n)
            self.add_file(f"w{n}", [obs(station=s, day=(week + timedelta(days=1)).isoformat()) for s in range(1, 21)],
                          week.isoformat(), (week + timedelta(days=6)).isoformat())
        self.assertNotEqual(self.run_quality()["decision"], "bloquear")
        baseline = (self.out / "staging" / "observations.csv").read_bytes()
        week = start + timedelta(weeks=4)
        self.add_file("tiny", [obs(station=s, day=(week + timedelta(days=1)).isoformat()) for s in range(1, 6)],
                      week.isoformat(), (week + timedelta(days=6)).isoformat())
        self.assert_blocked("reducao_extrema", baseline)

    def test_not_ingested_and_wrong_columns_block(self):
        baseline = self.publish_baseline()
        self.add_file("missing", [obs()], ingested=False)
        self.add_file("columns", [obs()], "2026-09-20", "2026-09-26", columns=OBSERVATION_COLUMNS[:-1])
        report = self.run_quality()
        self.assertEqual({f["rule"] for f in report["critical_failures"]},
                         {"arquivo_nao_ingerido", "colunas_ou_formato_invalidos"})
        self.assertEqual((self.out / "staging" / "observations.csv").read_bytes(), baseline)

    def test_cli_exit_codes(self):
        self.add_file("empty", [], "2026-09-27", "2026-10-03")
        (self.out / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        args = ["--out", str(self.out), "--quarantine", str(self.quarantine), "--as-of", "2026-10-10"]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(check_quality.main(args), 1)
            self.manifest["files"].clear()
            self.add_file("good", [obs()], "2026-09-20", "2026-09-26")
            (self.out / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
            self.assertEqual(check_quality.main(args), 0)


class ExcludedSourcesTest(QualityCase):
    """Arquivo da fonte com defeito conhecido: ignorado por inteiro, declarado no relatório (ADR 0006)."""

    def test_known_defective_file_is_skipped_reported_and_does_not_block(self):
        self.add_file("good", [obs()], "2026-09-20", "2026-09-26")
        self.add_file("broken", [], "2026-09-27", "2026-10-03")
        blocked = self.run_quality()
        self.assertEqual(blocked["decision"], "bloquear")
        self.assertEqual(blocked["excluded_sources"], [])

        (self.out / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        report = run_quality(self.out, self.quarantine, AS_OF,
                             {"broken" * 4: {"file": "broken.csv", "reason": "resumo sob cabeçalho de postos"}})
        self.assertNotEqual(report["decision"], "bloquear")
        self.assertEqual(report["critical_failures"], [])
        self.assertEqual([(e["source_file_id"], e["reason"]) for e in report["excluded_sources"]],
                         [("broken", "resumo sob cabeçalho de postos")])
        self.assertTrue(any("excluído por defeito conhecido" in w for w in report["warnings"]))
        self.assertEqual(report["reconciliation"]["rows_ingested"], 1)
        self.assertEqual([f["source_file_id"] for f in report["files"]], ["good"])

    def test_a_corrected_file_has_another_hash_and_is_not_excluded(self):
        self.add_file("fixed", [], "2026-09-27", "2026-10-03")  # sha256 diferente do excluído
        (self.out / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        report = run_quality(self.out, self.quarantine, AS_OF, {"x" * 64: {"file": "x", "reason": "y"}})
        self.assertEqual(report["excluded_sources"], [])
        self.assertEqual(report["decision"], "bloquear")


class CoverageTest(QualityCase):
    def test_low_coverage_recurring_absence_and_missing_weekdays(self):
        start = date(2026, 7, 26)
        for n in range(10):
            week = start + timedelta(weeks=n)
            monday = week + timedelta(days=1)
            rows = [obs(station=s, day=monday.isoformat()) for s in range(1, 9 if n < 9 else 3)]
            rows += [obs(station=s, city="CAMPINAS", day=monday.isoformat()) for s in range(60, 68)]
            if n < 9:
                rows.append(obs(station=50, city="UBATUBA", day=monday.isoformat()))
            self.add_file(f"w{n}", rows, week.isoformat(), (week + timedelta(days=6)).isoformat())
        report = self.run_quality()
        coverage = report["coverage"]
        self.assertEqual(coverage["latest_week"], "2026-09-27")
        self.assertEqual(coverage["last_collection_date"], "2026-09-28")
        self.assertEqual(coverage["delay_days"], 12)
        self.assertEqual(coverage["recurring_absent_latest_week"], ["UBATUBA"])
        self.assertEqual(coverage["low_coverage_latest_week"], 1)  # Jundiaí: 2 postos contra mediana 8
        self.assertIn("2026-09-22", coverage["weekdays_without_collection"])
        self.assertNotIn("2026-09-28", coverage["weekdays_without_collection"])
        weekly = read_csv(self.out / "quality" / "coverage_weekly.csv")
        ubatuba = [r for r in weekly if r["municipality_normalized"] == "UBATUBA" and r["week_start"] == "2026-09-27"]
        self.assertEqual((ubatuba[0]["stations"], ubatuba[0]["low_coverage"]), ("0", "false"))  # mediana 1 < 3
        series = {r["municipality_normalized"]: r for r in read_csv(self.out / "quality" / "coverage_series.csv")}
        self.assertEqual((series["UBATUBA"]["weeks_present"], series["UBATUBA"]["weeks_in_range"]), ("9", "10"))
        self.assertEqual(report["decision"], "publicar_com_aviso")


if __name__ == "__main__":
    unittest.main()
