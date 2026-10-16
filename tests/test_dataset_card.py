"""Ficha do conjunto de dados (Marco 13): lacunas, causas e textos, sem banco."""

from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis import dataset_card  # noqa: E402
from radar_combustiveis.config import load_excluded_sources  # noqa: E402

D = date.fromisoformat


class GapTests(unittest.TestCase):
    def test_gaps_grouped_by_cause(self):
        weeks = [D("2026-01-04"), D("2026-01-11"), D("2026-02-08"), D("2026-02-22")]
        defective = {D("2026-01-25"), D("2026-02-01")}
        self.assertEqual(dataset_card.gaps(weeks, defective), [
            [D("2026-01-18"), D("2026-01-18"), "sem_arquivo"],
            [D("2026-01-25"), D("2026-02-01"), "defeito"],
            [D("2026-02-15"), D("2026-02-15"), "sem_arquivo"]])
        self.assertEqual(dataset_card.gaps([D("2026-01-04"), D("2026-01-11")]), [])
        self.assertEqual(dataset_card.gaps([]), [])

    def test_defective_weeks_from_exclusion_list(self):
        excluded = {"a" * 64: {"file": "revendas_lpc_2025-06-29_2025-07-05.xlsx"},
                    "b" * 64: {"file": "outro-arquivo.xlsx"}}
        self.assertEqual(dataset_card.defective_weeks(excluded), {D("2025-06-29")})

    def test_shipped_exclusion_list_covers_known_defects(self):
        excluded = load_excluded_sources(ROOT / "config" / "excluded_sources.json")
        weeks = dataset_card.defective_weeks(excluded)
        self.assertIn(D("2025-06-29"), weeks)  # resumos no lugar dos postos (ADR 0006)
        self.assertIn(D("2022-12-04"), weeks)  # planilha que o leitor não abre
        self.assertEqual(len(excluded), 14)


CARD = {
    "coverage": {"first_week": "2026-01-04", "last_week": "2026-02-22", "weeks_with_data": 5, "weeks_in_range": 8,
                 "gaps": [["2026-01-18", "2026-01-18", "sem_arquivo"], ["2026-01-25", "2026-02-01", "defeito"]],
                 "municipalities": 2, "stations": 30, "uf": "SP"},
    "observations": {"current": 12345, "with_warning": 12, "warning_share": 0.001, "flags": {"preco_extremo": 12},
                     "superseded_by_revision": 3, "quarantined": {"conflito_de_preco_mesma_chave": 1}},
    "by_product": [{"product": "GASOLINA_COMUM", "observations": 12345, "stations": 30, "municipalities": 2,
                    "weeks": 5}],
    "by_year": [{"year": 2026, "observations": 12345, "weeks": 5}],
    "regions": {"Capital": {"municipalities": 1, "weeks_median": 5}},
    "sample": {"municipality_weeks": 10, "stations_median": 8, "stations_p10": 3, "stations_p90": 15,
               "thin_cells_lt3": 1, "thin_share": 0.1},
    "brands": {"top": [{"brand": "BRANCA", "observations": 6000, "share": 0.486}], "other_share": 0.514},
    "source_files": [], "external": [{"source_id": "bcb_sgs_1", "publisher": "Banco Central do Brasil",
                                      "license": "ODbL", "rows": 9, "first_period": "2026-01-01",
                                      "last_period": "2026-01-09"}],
}


class MarkdownTests(unittest.TestCase):
    def test_portuguese(self):
        text = dataset_card.markdown(CARD, "pt")
        self.assertIn("de 04/01/2026 a 22/02/2026: 5 semanas com dado de 8", text)
        self.assertIn("1 semanas sem arquivo na página da ANP (18/01/2026)", text)
        self.assertIn("2 semanas com arquivo da ANP com defeito", text)
        self.assertIn("12.345 observações vigentes", text)
        self.assertIn("(10,0%)", text)
        self.assertIn("preço extremo para o combustível: 12", text)

    def test_english(self):
        text = dataset_card.markdown(CARD, "en")
        self.assertIn("from 2026-01-04 to 2026-02-22: 5 weeks with data out of 8", text)
        self.assertIn("12,345 current observations", text)
        self.assertIn("(10.0%)", text)
        self.assertIn("| Capital | 1 | 5 |", text)

    def test_committed_card_has_no_personal_data(self):
        card = (ROOT / "reports" / "dataset" / "ficha.json").read_text(encoding="utf-8")
        self.assertNotIn("cnpj", card.lower())
        self.assertNotIn("legal_name", card)
        self.assertNotRegex(card, r"\b\d{14}\b")
        data = json.loads(card)
        c = data["coverage"]
        gap_weeks = sum((D(b) - D(a)).days // 7 + 1 for a, b, _ in c["gaps"])
        self.assertEqual(c["weeks_with_data"] + gap_weeks, c["weeks_in_range"])  # cada semana tem dado ou causa


if __name__ == "__main__":
    unittest.main()
