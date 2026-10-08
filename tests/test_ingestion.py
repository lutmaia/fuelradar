"""Ingestão local com fixtures sintéticas pequenas; não dependem de arquivos em data/raw."""

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from zipfile import ZipFile

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from radar_combustiveis.config import load_target_ufs, parse_target_ufs  # noqa: E402
from radar_combustiveis.ingestion.manifest import period_key, reference_period  # noqa: E402
from radar_combustiveis.ingestion.pipeline import run_ingestion  # noqa: E402

WEEKLY_HEADER = ["RAZÃO", "FANTASIA", "CNPJ", "ENDEREÇO", "NÚMERO", "COMPLEMENTO", "BAIRRO", "CEP",
                 "MUNICÍPIO", "ESTADO", "PRODUTO", "UNIDADE DE MEDIDA", "PREÇO DE REVENDA",
                 "DATA DA COLETA", "BANDEIRA"]


def weekly_row(cnpj=12345678000100, uf="SAO PAULO", city="Jundiaí", product="GASOLINA COMUM",
               unit="R$/l", price=5.99, day=21, cep=13201000, brand="BRANCA"):
    return ["POSTO TESTE LTDA", "POSTO TESTE", cnpj, "RUA A", "10", None, "CENTRO", cep, city, uf,
            product, unit, price, datetime(2026, 9, day), brand]


HISTORICAL_HEADER = ["Regiao - Sigla", "Estado - Sigla", "Municipio", "Revenda", "CNPJ da Revenda",
                     "Nome da Rua", "Numero Rua", "Complemento", "Bairro", "Cep", "Produto",
                     "Data da Coleta", "Valor de Venda", "Valor de Compra", "Unidade de Medida", "Bandeira"]


def historical_row(uf="SP", city="Jundiaí", cnpj=" 00.123.456/0001-00", product="GASOLINA",
                   date="05/01/2026", price="5,99"):
    return ["SE", uf, city, "REVENDA SINTETICA", cnpj, "RUA TESTE", "12", "", "CENTRO", "01234-567",
            product, date, price, "", "R$ / litro", "BRANCA"]


def write_xlsx(path, header, rows, preamble=("Levantamento sintético",)):
    workbook = Workbook()
    sheet = workbook.active
    for line in preamble:
        sheet.append([line])
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


def write_csv(path, header, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
        writer.writerow(header)
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class IngestionCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.base = Path(folder.name)
        self.raw = self.base / "raw"
        self.out = self.base / "processed"
        self.quarantine = self.base / "quarantine"
        self.raw.mkdir()

    def run_ingestion(self, ufs=("SP",)):
        return run_ingestion(self.raw, self.out, self.quarantine, ufs)

    def manifest(self):
        return json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))

    def observations(self, entry):
        return read_csv(self.out / entry["ingestion"]["output"])

    def raw_hashes(self):
        return {p.relative_to(self.raw).as_posix(): digest(p) for p in self.raw.rglob("*") if p.is_file()}


class WeeklyXlsxTests(IngestionCase):
    def make_weekly(self, name="revendas_lpc_2026-09-20_2026-09-26.xlsx", extra=()):
        rows = [weekly_row(), weekly_row(product="GLP", unit="R$/13kg", price=110.0, cnpj=987654321098),
                weekly_row(uf="RIO DE JANEIRO", city="Niterói"),
                weekly_row(price=None), weekly_row(uf="SAO PAULO", day=22, price="abc"), *extra]
        write_xlsx(self.raw / name, WEEKLY_HEADER, rows)

    def test_ingests_only_target_uf_with_audit_columns(self):
        self.make_weekly()
        report = self.run_ingestion()
        self.assertEqual(report["errors"], [])
        entry = self.manifest()["files"][0]
        stats = entry["ingestion"]
        self.assertEqual((stats["rows_read"], stats["rows_accepted"], stats["rows_out_of_scope"],
                          stats["rows_rejected"]), (5, 2, 1, 2))
        self.assertEqual(stats["rows_read"], stats["rows_accepted"] + stats["rows_out_of_scope"] + stats["rows_rejected"])
        self.assertEqual((stats["rows_automotive"], stats["rows_glp"]), (1, 1))
        rows = self.observations(entry)
        self.assertEqual({r["uf"] for r in rows}, {"SP"})
        gasoline = rows[0]
        self.assertEqual(gasoline["cnpj"], "12345678000100")
        self.assertEqual(gasoline["cep"], "13201000")
        self.assertEqual(gasoline["municipality_original"], "Jundiaí")
        self.assertEqual(gasoline["municipality_normalized"], "JUNDIAI")
        self.assertEqual(gasoline["product"], "GASOLINA_COMUM")
        self.assertEqual(gasoline["unit"], "BRL/L")
        self.assertEqual(gasoline["sale_price"], "5.99")
        self.assertEqual(gasoline["collection_date"], "2026-09-21")
        self.assertEqual(gasoline["row_key"], "SP|JUNDIAI|12345678000100|GASOLINA_COMUM|BRL/L|2026-09-21")
        # Preâmbulo (1) + cabeçalho (2): primeira linha de dados é a 3 do Excel.
        self.assertEqual(gasoline["source_row_number"], "3")
        self.assertEqual(gasoline["source_sha256"], entry["sha256"])
        self.assertEqual(gasoline["source_file_id"], entry["source_file_id"])
        self.assertEqual(gasoline["ingestion_run_id"], report["run_id"])
        self.assertEqual(rows[1]["product_category"], "glp")
        self.assertEqual(entry["reference_start"], "2026-09-20")
        self.assertEqual(entry["reference_end"], "2026-09-26")

    def test_rejected_rows_go_to_quarantine_with_reason(self):
        self.make_weekly()
        self.run_ingestion()
        entry = self.manifest()["files"][0]
        rejected = read_csv(self.quarantine / entry["ingestion"]["quarantine"])
        self.assertEqual([(r["source_row_number"], r["reason"]) for r in rejected],
                         [("6", "preco_de_venda_ausente"), ("7", "preco_de_venda_invalido")])
        self.assertIn("abc", rejected[1]["original_values"])

    def test_rerun_is_idempotent(self):
        self.make_weekly()
        first = self.run_ingestion()
        manifest_bytes = (self.out / "manifest.json").read_bytes()
        entry = self.manifest()["files"][0]
        output = self.out / entry["ingestion"]["output"]
        output_bytes = output.read_bytes()
        second = self.run_ingestion()
        self.assertEqual(len(first["ingested"]), 1)
        self.assertEqual((second["events"], second["ingested"], second["errors"]), ([], [], []))
        self.assertFalse(second["manifest_written"])
        self.assertEqual((self.out / "manifest.json").read_bytes(), manifest_bytes)
        self.assertEqual(output.read_bytes(), output_bytes)
        self.assertEqual(len(self.manifest()["files"]), 1)
        self.assertEqual(len(read_csv(output)), 2)

    def test_changed_content_with_same_name_is_new_revision(self):
        self.make_weekly()
        self.run_ingestion()
        first = self.manifest()["files"][0]
        first_output_bytes = (self.out / first["ingestion"]["output"]).read_bytes()
        self.make_weekly(extra=[weekly_row(cnpj=11111111000111, day=23)])
        report = self.run_ingestion()
        files = self.manifest()["files"]
        self.assertEqual([(f["revision"], f["is_current"]) for f in files], [(1, False), (2, True)])
        self.assertEqual(report["events"][0]["event"], "revision")
        self.assertEqual(len(report["ingested"]), 1)
        self.assertEqual(files[1]["ingestion"]["rows_accepted"], 3)
        self.assertEqual((self.out / files[0]["ingestion"]["output"]).read_bytes(), first_output_bytes)
        self.assertNotEqual(files[0]["source_file_id"], files[1]["source_file_id"])

    def test_same_content_in_two_paths_is_one_entry(self):
        self.make_weekly()
        (self.raw / "copia").mkdir()
        shutil.copy2(self.raw / "revendas_lpc_2026-09-20_2026-09-26.xlsx",
                     self.raw / "copia" / "revendas_lpc_2026-09-20_2026-09-26.xlsx")
        report = self.run_ingestion()
        files = self.manifest()["files"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["revision"], 1)
        self.assertEqual(files[0]["paths"], ["copia/revendas_lpc_2026-09-20_2026-09-26.xlsx",
                                             "revendas_lpc_2026-09-20_2026-09-26.xlsx"])
        self.assertEqual(len(report["ingested"]), 1)

    def test_changing_target_ufs_reprocesses_the_current_file(self):
        self.make_weekly()
        self.run_ingestion(("SP",))
        report = self.run_ingestion(("SP", "RJ"))
        entry = self.manifest()["files"][0]
        self.assertEqual(len(report["ingested"]), 1)
        self.assertEqual(entry["ingestion"]["target_ufs"], ["SP", "RJ"])
        self.assertEqual({r["uf"] for r in self.observations(entry)}, {"SP", "RJ"})
        self.assertEqual(entry["ingestion"]["rows_out_of_scope"], 0)

    def test_raw_is_never_modified(self):
        self.make_weekly()
        write_csv(self.raw / "historico.csv", HISTORICAL_HEADER, [historical_row()])
        before = self.raw_hashes()
        self.run_ingestion()
        self.run_ingestion()
        self.assertEqual(self.raw_hashes(), before)
        self.assertEqual(sorted(before), ["historico.csv", "revendas_lpc_2026-09-20_2026-09-26.xlsx"])

    def test_output_inside_raw_is_refused(self):
        self.make_weekly()
        with self.assertRaisesRegex(ValueError, "dentro de data/raw"):
            run_ingestion(self.raw, self.raw / "processed", self.quarantine, ("SP",))
        with self.assertRaisesRegex(ValueError, "dentro de data/raw"):
            run_ingestion(self.raw, self.out, self.raw, ("SP",))
        self.assertEqual(list(self.raw.glob("**/processed")), [])


class HistoricalCsvTests(IngestionCase):
    def test_historical_csv_and_duplicates_are_kept(self):
        write_csv(self.raw / "Preços semestrais - AUTOMOTIVOS_2026.01.csv", HISTORICAL_HEADER, [
            historical_row(), historical_row(), historical_row(uf="RJ", city="Niterói"),
            historical_row(product="DIESEL", date="06/01/2026"), historical_row(date="31/02/2026"),
            historical_row(uf="XX"),
        ])
        self.assertEqual(self.run_ingestion()["errors"], [])
        entry = self.manifest()["files"][0]
        stats = entry["ingestion"]
        self.assertEqual((stats["rows_read"], stats["rows_accepted"], stats["rows_out_of_scope"],
                          stats["rows_rejected"], stats["duplicate_keys"]), (6, 3, 1, 2, 1))
        self.assertEqual((stats["municipalities"], stats["unique_cnpj"]), (1, 1))
        self.assertEqual((stats["collection_date_min"], stats["collection_date_max"]), ("2026-01-05", "2026-01-06"))
        rows = self.observations(entry)
        self.assertEqual(rows[0]["cnpj"], "00123456000100")
        self.assertEqual(rows[0]["cnpj_status"], "exact_masked_text")
        self.assertEqual(rows[0]["product"], "GASOLINA_COMUM")
        self.assertEqual(rows[0]["product_original"], "GASOLINA")
        self.assertEqual(rows[0]["region"], "SE")
        self.assertEqual(rows[2]["product"], "DIESEL_NAO_ESPECIFICADO")
        self.assertEqual(rows[0]["row_key"], rows[1]["row_key"])
        self.assertEqual(rows[0]["source_row_hash"], rows[1]["source_row_hash"])
        self.assertEqual(entry["reference_start"], "2026-01-05")
        reasons = [r["reason"] for r in read_csv(self.quarantine / stats["quarantine"])]
        self.assertEqual(reasons, ["data_da_coleta_invalida", "uf_invalida_ou_ausente"])

    def test_ambiguous_cnpj_is_kept_without_digits_or_key(self):
        write_csv(self.raw / "h.csv", HISTORICAL_HEADER, [historical_row(cnpj="1234567")])
        self.run_ingestion()
        row = self.observations(self.manifest()["files"][0])[0]
        self.assertEqual((row["cnpj"], row["cnpj_status"], row["row_key"]), ("", "ambiguous_short_text", ""))
        self.assertEqual(row["sale_price"], "5.99")

    def test_csv_inside_zip_records_member(self):
        csv_path = self.base / "h.csv"
        write_csv(csv_path, HISTORICAL_HEADER, [historical_row()])
        with ZipFile(self.raw / "historico.zip", "w") as archive:
            archive.write(csv_path, "dentro/h.csv")
        self.run_ingestion()
        row = self.observations(self.manifest()["files"][0])[0]
        self.assertEqual(row["source_member"], "dentro/h.csv")


class FailureAndScopeTests(IngestionCase):
    def test_aggregate_is_registered_but_not_ingested(self):
        write_xlsx(self.raw / "mensal-municipios.xlsx",
                   ["MÊS", "MUNICÍPIO", "PRODUTO", "UNIDADE DE MEDIDA", "PREÇO MÉDIO REVENDA",
                    "NÚMERO DE POSTOS PESQUISADOS"],
                   [[datetime(2026, 1, 1), "SAO PAULO", "GASOLINA COMUM", "R$/l", 5.9, 40]])
        report = self.run_ingestion()
        entry = self.manifest()["files"][0]
        self.assertEqual((entry["kinds"], entry["ingestion"]), (["monthly_aggregate"], None))
        self.assertEqual(report["ingested"], [])
        self.assertFalse((self.out / "observations").exists())

    def test_unknown_schema_is_reported_and_not_registered(self):
        (self.raw / "estranho.csv").write_text("A;B\n1;2\n", encoding="utf-8")
        write_csv(self.raw / "bom.csv", HISTORICAL_HEADER, [historical_row()])
        report = self.run_ingestion()
        self.assertEqual([(e["path"], e["stage"]) for e in report["errors"]], [("estranho.csv", "detect")])
        self.assertEqual([f["paths"] for f in self.manifest()["files"]], [["bom.csv"]])

    def test_critical_failure_mid_file_publishes_nothing(self):
        write_csv(self.raw / "h.csv", HISTORICAL_HEADER, [
            historical_row(), historical_row() + ["valor fora das colunas"]])
        report = self.run_ingestion()
        self.assertEqual([(e["stage"], "fora das colunas" in e["error"]) for e in report["errors"]],
                         [("ingest", True)])
        self.assertIsNone(self.manifest()["files"][0]["ingestion"])
        self.assertEqual(list((self.out / "observations").glob("*")), [])
        self.assertEqual(list(self.quarantine.glob("*")), [])
        # Corrigir o arquivo cria revisão nova; a falha anterior não bloqueia.
        write_csv(self.raw / "h.csv", HISTORICAL_HEADER, [historical_row()])
        self.assertEqual(self.run_ingestion()["errors"], [])
        self.assertEqual([f["revision"] for f in self.manifest()["files"]], [1, 2])


class ConfigAndNamingTests(unittest.TestCase):
    def test_target_ufs(self):
        self.assertEqual(parse_target_ufs('["SP"]'), ("SP",))
        self.assertEqual(parse_target_ufs('["SP", "RJ"]'), ("SP", "RJ"))
        self.assertEqual(load_target_ufs({}), ("SP",))
        self.assertEqual(load_target_ufs({"TARGET_UFS": '["MG"]'}), ("MG",))
        for bad in ["SP", "[]", '["XX"]', '["SP","SP"]', "[1]", '"SP"', "{}"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_target_ufs(bad)

    def test_csv_delimiter_comes_from_header(self):
        import io
        from radar_combustiveis.ingestion.readers import SourceFormatError, detect_csv_format
        for delimiter in [";", ",", "\t", "|"]:
            with self.subTest(delimiter=delimiter):
                data = delimiter.join(HISTORICAL_HEADER) + "\n1" + delimiter + "a,b;c\n"
                encoding, dialect = detect_csv_format(io.BytesIO(data.encode("utf-8-sig")))
                self.assertEqual((encoding, dialect.delimiter), ("utf-8-sig", delimiter))
        with self.assertRaises(SourceFormatError):
            detect_csv_format(io.BytesIO(b"semdelimitador\n1\n"))

    def test_period_helpers(self):
        self.assertEqual(period_key("x/revendas_lpc_2026-09-20_2026-09-26.xlsx"), "revendas_lpc_2026-09-20_2026-09-26")
        self.assertEqual(reference_period("revendas_lpc_2026-09-20_2026-09-26.xlsx"), ("2026-09-20", "2026-09-26"))
        self.assertEqual(reference_period("Preços semestrais - AUTOMOTIVOS_2026.01.csv"), (None, None))


if __name__ == "__main__":
    unittest.main()
