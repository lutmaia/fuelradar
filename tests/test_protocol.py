"""Protocolo do estudo (Marco 8): as janelas em código são as do pré-registro e o lacre funciona."""

from datetime import date, timedelta
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.forecasting import protocol as pr  # noqa: E402

WEEK = timedelta(days=7)


class WindowTests(unittest.TestCase):
    def test_every_boundary_is_a_sunday(self):
        dates = [pr.DEV_START, pr.DEV_END, pr.VALID_START, pr.VALID_END, pr.TEST_START,
                 *(d for period in pr.SUBPERIODS for d in period)]
        for d in dates:
            self.assertEqual(d.weekday(), 6, d)

    def test_windows_are_contiguous_and_ordered(self):
        self.assertEqual(pr.VALID_START, pr.DEV_END + WEEK)
        self.assertEqual(pr.TEST_START, pr.VALID_END + WEEK)
        self.assertLess(pr.DEV_START, pr.DEV_END)
        self.assertLess(pr.VALID_START, pr.VALID_END)

    def test_study_stops_before_the_final_test(self):
        self.assertEqual((pr.STUDY_START, pr.STUDY_END), (pr.DEV_START, pr.VALID_END))
        (a_start, a_end), (b_start, b_end) = pr.SUBPERIODS
        self.assertEqual((a_start, b_end), (pr.STUDY_START, pr.STUDY_END))
        self.assertEqual(b_start, a_end + WEEK)

    def test_window_of(self):
        self.assertEqual(pr.window_of(pr.DEV_START), "dev")
        self.assertEqual(pr.window_of(pr.DEV_END), "dev")
        self.assertEqual(pr.window_of(pr.VALID_START), "valid")
        self.assertEqual(pr.window_of(pr.VALID_END), "valid")
        self.assertEqual(pr.window_of(pr.TEST_START), "test")
        self.assertEqual(pr.window_of(date(2030, 1, 6)), "test")
        with self.assertRaises(ValueError):
            pr.window_of(pr.DEV_START - WEEK)

    def test_study_weeks_drop_the_holdout_and_keep_order(self):
        weeks = [pr.TEST_START, pr.VALID_END, pr.DEV_START, pr.DEV_START - WEEK, pr.TEST_START + WEEK]
        self.assertEqual(pr.study_weeks(weeks), [pr.VALID_END, pr.DEV_START])
        pr.assert_no_holdout(pr.study_weeks(weeks))

    def test_holdout_week_is_refused(self):
        pr.assert_no_holdout([pr.DEV_START, pr.VALID_END])
        with self.assertRaises(pr.HoldoutViolation) as ctx:
            pr.assert_no_holdout([pr.VALID_END, pr.TEST_START + WEEK, pr.TEST_START])
        self.assertIn(str(pr.TEST_START), str(ctx.exception))


class PreRegistrationTests(unittest.TestCase):
    """O código e o protocolo escrito não podem divergir em silêncio."""

    def test_protocol_document_states_the_same_dates_and_seed(self):
        text = (ROOT / "docs" / "estudo" / "protocolo.md").read_text(encoding="utf-8")
        for d in (pr.DEV_START, pr.DEV_END, pr.VALID_START, pr.VALID_END, pr.TEST_START,
                  *(x for period in pr.SUBPERIODS for x in period)):
            self.assertIn(d.isoformat(), text)
        self.assertIn(str(pr.SEED), text)
        self.assertRegex(text, rf"B\s*=\s*{pr.BOOTSTRAP_REPS}")
        self.assertIsNotNone(re.search(rf"{pr.BOOTSTRAP_BLOCK_WEEKS} semanas", text))


if __name__ == "__main__":
    unittest.main()
