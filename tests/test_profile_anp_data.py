"""Fixtures sintéticas pequenas: não dependem de arquivos em data/raw."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from openpyxl import Workbook

from scripts.profile_anp_data import (
    ProfileError, identify_header, main, normalize_cnpj, normalize_product,
    normalize_text, normalize_uf, normalize_unit, parse_date, parse_money,
    profile_file, profile_rows, sha256,
    normalize_identifier, compare_sources, Scope,
)


HEADER = ["CNPJ", "ESTADO", "MUNICÍPIO", "PRODUTO", "UNIDADE DE MEDIDA", "PREÇO DE REVENDA", "DATA DA COLETA"]
ROW = [12345678000100, "SAO PAULO", "Jundiaí", "GASOLINA COMUM", "R$ / litro", "5,99", "21/09/2026"]
HISTORICAL_HEADER = ["Regiao - Sigla", "Estado - Sigla", "Municipio", "Revenda", "CNPJ da Revenda",
                     "Nome da Rua", "Numero Rua", "Complemento", "Bairro", "Cep", "Produto",
                     "Data da Coleta", "Valor de Venda", "Valor de Compra", "Unidade de Medida", "Bandeira"]
HISTORICAL_ROW = ["SE", "SP", "Jundiaí", "REVENDA SINTETICA", " 00.123.456/0001-00",
                  "RUA TESTE", "12", "", "CENTRO", "01234-567", "GASOLINA", "05/01/2026", "5,99", "", "R$ / litro", "BRANCA"]


class HistoricalTests(unittest.TestCase):
    def test_historical_header_and_original_normalized_pairs(self):
        result = profile_rows([HISTORICAL_HEADER, HISTORICAL_ROW])
        self.assertEqual(result["kind"], "retail_observation")
        self.assertEqual(result["column_count"], 16)
        self.assertEqual(result["canonical_mapping"]["cnpj"], "CNPJ da Revenda")
        self.assertEqual(result["sp"]["unique_cnpj_count"], 1)
        self.assertEqual(result["normalization_pairs"]["product"], [{"original": "GASOLINA", "normalized": "GASOLINA_COMUM", "rows": 1}])
        self.assertEqual(result["normalization_pairs"]["municipality"][0]["original"], "Jundiaí")
        self.assertEqual(result["normalization_pairs"]["municipality"][0]["normalized"], "JUNDIAI")
        self.assertEqual(HISTORICAL_ROW[4], " 00.123.456/0001-00")

    def test_identifiers_exact_or_recoverable(self):
        self.assertEqual(normalize_identifier(" 00.123.456/0001-00", 14), ("00123456000100", "exact_masked_text"))
        self.assertEqual(normalize_identifier("01234-567", 8), ("01234567", "exact_masked_text"))
        self.assertEqual(normalize_identifier("01234567", 8), ("01234567", "exact_text"))
        self.assertEqual(normalize_identifier(1234567, 8), ("01234567", "padded_native_integer"))
        self.assertEqual(normalize_identifier(123456000100, 14), ("00123456000100", "padded_native_integer"))

    def test_ambiguous_identifiers_never_padded(self):
        for value in ["1234567", "1.234567E+6", "1234567.0", 1234567.0]:
            with self.subTest(value=value):
                normalized, status = normalize_identifier(value, 8)
                self.assertIsNone(normalized)
                self.assertTrue(status.startswith("ambiguous"))
        for value in [-1234567, "-1234567", "123456789", True]:
            self.assertEqual(normalize_identifier(value, 8)[1], "invalid")

    def test_ambiguous_cnpj_excluded_from_key_but_row_preserved(self):
        row = HISTORICAL_ROW.copy()
        row[4], row[9] = "1.23456E+11", "1234567"
        result = profile_rows([HISTORICAL_HEADER, row])
        self.assertEqual(result["sp"]["rows"], 1)
        self.assertEqual(result["sp"]["unique_cnpj_count"], 0)
        self.assertEqual(result["quality"]["rows_without_complete_candidate_key"], 1)
        self.assertEqual(result["sp_identifier_status"]["cnpj"]["ambiguous_numeric_text"], 1)
        self.assertEqual(result["ambiguous_identifier_row_numbers"]["postal_code"], [2])

    def test_unspecified_diesel_not_silently_s500(self):
        self.assertEqual(normalize_product("DIESEL"), "DIESEL_NAO_ESPECIFICADO")
        self.assertNotEqual(normalize_product("DIESEL"), normalize_product("DIESEL S500"))

    def test_bom_crcrlf_and_historical_csv_in_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "historical.csv"
            path.write_bytes((";".join(HISTORICAL_HEADER) + "\r\r\n" + ";".join(HISTORICAL_ROW) + "\r\r\n").encode("utf-8-sig"))
            original_hash = sha256(path)
            direct = profile_file(path, None)
            self.assertEqual(direct["encoding"], "utf-8-sig")
            self.assertEqual(direct["sheets"][0]["rows"], 1)
            self.assertEqual(direct["sheets"][0]["blank_rows_after_header"], 2)
            zip_path = Path(folder) / "historical.zip"
            with ZipFile(zip_path, "w") as archive:
                archive.write(path, "nested/historical.csv")
            zipped_hash = sha256(zip_path)
            zipped = profile_file(zip_path, None)
            self.assertEqual(direct["sheets"], zipped["contents"][0]["sheets"])
            self.assertEqual(original_hash, sha256(path))
            self.assertEqual(zipped_hash, sha256(zip_path))

    def test_key_conflict_price_and_overlap_across_formats(self):
        combined = {"sp": Scope(), "jundiai": Scope(), "keys": set(), "duplicates": 0, "sources": []}
        changed = HISTORICAL_ROW.copy()
        changed[12] = "6,09"
        history = profile_rows([HISTORICAL_HEADER, HISTORICAL_ROW, changed], combined)
        weekly = [123456000100, "SAO PAULO", "JUNDIAI", "GASOLINA COMUM", "R$/l", 5.99, datetime(2026, 1, 5)]
        profile_rows([HEADER, weekly], combined)
        for i, source in enumerate(combined["sources"]):
            source["source"] = str(i)
        result = compare_sources(combined["sources"])[0]
        self.assertEqual(history["quality"]["sp_candidate_key_price_conflicts"], 1)
        self.assertEqual(result["shared_candidate_keys"], 1)
        self.assertEqual(result["shared_collection_dates"], 1)
        self.assertEqual(result["shared_keys_conflicting_price_sets"], 1)

    def test_identical_key_price_and_disjoint_dates(self):
        sources = [{"source": "a", "keys": {("key",): {Decimal("5.99")}}, "dates": {date(2026, 1, 5)}},
                   {"source": "b", "keys": {("key",): {Decimal("5.99")}}, "dates": {date(2026, 1, 5)}}]
        self.assertEqual(compare_sources(sources)[0]["shared_keys_same_price_set"], 1)
        sources[1] = {"source": "b", "keys": {("different",): {Decimal("6.00")}}, "dates": {date(2026, 9, 1)}}
        self.assertEqual(compare_sources(sources)[0]["shared_candidate_keys"], 0)
        self.assertEqual(compare_sources(sources)[0]["shared_collection_dates"], 0)


class NormalizationTests(unittest.TestCase):
    def test_header_after_preamble(self):
        iterator = iter([["Relatório"], [], HEADER, ROW])
        number, names, mapping, kind = identify_header(iterator)
        self.assertEqual(number, 3)
        self.assertEqual(names, HEADER)
        self.assertEqual(mapping["uf"], 1)
        self.assertEqual(kind, "retail_observation")
        self.assertEqual(next(iterator), ROW)

    def test_missing_required_column(self):
        with self.assertRaisesRegex(ProfileError, "sale_price"):
            identify_header(iter([HEADER[:5] + HEADER[6:]]))

    def test_unknown_header(self):
        with self.assertRaisesRegex(ProfileError, "não identificado"):
            identify_header(iter([["foo", "bar"]]))

    def test_money(self):
        for original, expected in [("5,99", "5.99"), ("1.234,56", "1234.56"), (5.9, "5.9"), ("-1,20", "-1.20"), (0, "0")]:
            with self.subTest(original=original):
                self.assertEqual(parse_money(original), Decimal(expected))
        for original in [None, "-", "", "N/A"]:
            self.assertIsNone(parse_money(original))
        for original in ["NaN", "Infinity", "cinco", "1.23,45", True]:
            with self.subTest(original=original), self.assertRaises(ValueError):
                parse_money(original)

    def test_uf(self):
        for text in ["SP", " sp ", "SAO PAULO", "São Paulo", "São   Paulo"]:
            self.assertEqual(normalize_uf(text), "SP")
        self.assertEqual(normalize_uf("Rio de Janeiro"), "RJ")
        self.assertIsNone(normalize_uf("SUDESTE"))
        self.assertIsNone(normalize_uf(None))

    def test_products(self):
        for text in ["GASOLINA", "gasolina comum"]:
            self.assertEqual(normalize_product(text), "GASOLINA_COMUM")
        self.assertEqual(normalize_product("ETANOL"), normalize_product("ETANOL HIDRATADO"))
        self.assertEqual(normalize_product("ÓLEO DIESEL"), "DIESEL_S500")
        self.assertEqual(normalize_product("OLEO DIESEL S10"), "DIESEL_S10")
        self.assertNotEqual(normalize_product("GASOLINA ADITIVADA"), normalize_product("GASOLINA"))
        self.assertIsNone(normalize_product("novo combustível"))

    def test_municipality_units_identifiers(self):
        self.assertEqual(normalize_text(" Jundiaí "), "JUNDIAI")
        self.assertEqual(normalize_unit("R$/m³"), "BRL/M3")
        self.assertEqual(normalize_unit("R$ / 13 kg"), "BRL/13KG")
        self.assertIsNone(normalize_unit("litros"))
        self.assertEqual(normalize_cnpj(123456780001), "00123456780001")
        self.assertIsNone(normalize_cnpj(123.4))

    def test_dates(self):
        for text in ["21/09/2026", "2026-09-21", datetime(2026, 9, 21), date(2026, 9, 21)]:
            self.assertEqual(parse_date(text), date(2026, 9, 21))
        self.assertIsNone(parse_date(None))
        for text in ["31/02/2026", "09/21/2026", 46286]:
            with self.assertRaises(ValueError):
                parse_date(text)


class ProfileTests(unittest.TestCase):
    def test_sp_jundiai_dedup_and_no_glp_in_automotive(self):
        glp = ROW.copy()
        glp[0], glp[3], glp[4] = 99999999000100, "GLP", "R$ / 13 kg"
        rj = ROW.copy()
        rj[1] = "RJ"
        result = profile_rows([HEADER, ROW, ROW, glp, rj])
        self.assertEqual(result["rows"], 4)
        self.assertEqual(result["sp"]["rows"], 3)
        self.assertEqual(result["jundiai"]["rows"], 3)
        self.assertEqual(result["sp"]["unique_cnpj_count"], 2)
        self.assertEqual(result["sp"]["automotive_unique_cnpj_count"], 1)
        self.assertEqual(result["quality"]["exact_duplicate_rows"], 1)
        self.assertEqual(result["quality"]["sp_candidate_key_duplicates"], 1)

    def test_price_flags_and_missing_counts(self):
        rows = []
        for value in [None, "-", "ruim", "-1,00", "0", "5,99"]:
            row = ROW.copy()
            row[5] = value
            rows.append(row)
        result = profile_rows([HEADER, *rows])
        price = next(iter(result["prices_sp"].values()))
        self.assertEqual(price["missing"], 2)
        self.assertEqual(price["non_numeric"], 1)
        self.assertEqual(price["negative"], 1)
        self.assertEqual(price["zero"], 1)
        self.assertEqual(result["columns"][5]["missing"], 2)

    def test_monthly_not_individual_observation(self):
        header = ["MÊS", "PRODUTO", "REGIÃO", "ESTADO", "MUNICÍPIO", "NÚMERO DE POSTOS PESQUISADOS", "UNIDADE DE MEDIDA", "PREÇO MÉDIO REVENDA"]
        row = [datetime(2026, 1, 1), "GASOLINA COMUM", "SUDESTE", "SAO PAULO", "JUNDIAI", 200, "R$/l", 6.0]
        result = profile_rows([header, row])
        self.assertEqual(result["kind"], "monthly_aggregate")
        self.assertIsNone(result["sp"]["unique_cnpj_count"])
        self.assertEqual(result["sp_reported_station_count_range"], [200, 200])
        self.assertNotIn("collection_date", result["dates"])

    def test_invalid_date_and_missing_municipality(self):
        row = ROW.copy()
        row[2], row[6] = None, "31/02/2026"
        result = profile_rows([HEADER, row])
        self.assertEqual(result["quality"]["invalid_collection_date"], 1)
        self.assertEqual(result["quality"]["rows_without_complete_candidate_key"], 1)
        self.assertEqual(result["sp"]["municipality_count"], 0)

    def test_unexpected_extra_column(self):
        with self.assertRaisesRegex(ProfileError, "fora das colunas"):
            profile_rows([HEADER, ROW + ["surpresa"]])

    def test_empty_data_rejected(self):
        with self.assertRaisesRegex(ProfileError, "nenhuma linha"):
            profile_rows([HEADER, [None] * len(HEADER)])

    def test_regional_cannot_be_assigned_to_sp(self):
        header = ["MÊS", "PRODUTO", "REGIÃO", "NÚMERO DE POSTOS PESQUISADOS", "UNIDADE DE MEDIDA", "PREÇO MÉDIO REVENDA"]
        row = [datetime(2026, 1, 1), "GASOLINA COMUM", "SUDESTE", 200, "R$/l", 6]
        result = profile_rows([header, row])
        self.assertFalse(result["sp_identifiable"])
        self.assertIsNone(result["sp"])

    def test_price_outlier_is_flagged_not_removed(self):
        rows = []
        for value in [5, 5, 5, 5, 20]:
            row = ROW.copy()
            row[5] = value
            rows.append(row)
        result = profile_rows([HEADER, *rows])
        price = next(iter(result["prices_sp"].values()))
        self.assertEqual(price["potential_outliers"], 1)
        self.assertEqual(result["rows"], 5)

    def test_cp1252_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "small.csv"
            path.write_bytes((";".join(HEADER) + "\n" + ";".join(map(str, ROW)) + "\n").encode("cp1252"))
            result = profile_file(path, None)
            self.assertEqual(result["encoding"], "cp1252")
            self.assertEqual(result["sheets"][0]["sp"]["rows"], 1)

    def test_csv_and_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "small.csv"
            csv_path.write_text(";".join(HEADER) + "\n" + ";".join(map(str, ROW)) + "\n", encoding="utf-8")
            before = sha256(csv_path)
            result = profile_file(csv_path, None)
            self.assertEqual(result["delimiter"], ";")
            self.assertEqual(result["sheets"][0]["sp"]["rows"], 1)
            self.assertEqual(sha256(csv_path), before)
            zip_path = Path(folder) / "small.zip"
            with ZipFile(zip_path, "w") as archive:
                archive.write(csv_path, "nested/small.csv")
            result = profile_file(zip_path, None)
            self.assertEqual(result["contents"][0]["sheets"][0]["rows"], 1)
            self.assertFalse((Path(folder) / "nested").exists())

    def test_zip_unexpected_content(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("surprise.txt", "not ANP")
            with self.assertRaisesRegex(ProfileError, "conteúdo inesperado"):
                profile_file(path, None)

    def test_xlsx_cli_report_and_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "raw"
            source.mkdir()
            path = source / "small.xlsx"
            output = Path(folder) / "reports"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["Preambulo"])
            sheet.append(HEADER)
            sheet.append(ROW)
            workbook.save(path)
            workbook.close()
            before = sha256(path)
            with redirect_stdout(io.StringIO()):
                code = main([str(path), "--output-dir", str(output)])
            self.assertEqual(code, 0)
            data = json.loads((output / "profile.json").read_text(encoding="utf-8"))
            self.assertEqual(data["files"][0]["sheets"][0]["header_row"], 2)
            self.assertEqual(data["combined_retail"]["sp"]["unique_cnpj_count"], 1)
            self.assertEqual(before, sha256(path))
            zip_path = source / "small.zip"
            with ZipFile(zip_path, "w") as archive:
                archive.write(path, "small.xlsx")
            zipped = profile_file(zip_path, None)
            self.assertEqual(zipped["contents"][0]["sheets"][0]["rows"], 1)

    def test_cli_rejects_output_in_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "small.csv"
            path.write_text("irrelevant")
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main([str(path), "--output-dir", folder])
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
