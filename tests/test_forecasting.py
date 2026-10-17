"""Testes da previsão de valor com séries sintéticas (sem banco): painel, elegibilidade, baselines, vazamento,
intervalos, métricas, regra de aprovação e o ciclo completo."""

from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from radar_combustiveis.forecasting import evaluate as ev  # noqa: E402
from radar_combustiveis.forecasting import models as md  # noqa: E402
from radar_combustiveis.forecasting import panel as pn  # noqa: E402
from radar_combustiveis.forecasting.report import markdown  # noqa: E402
from radar_combustiveis.forecasting.run import MIN_ANOMALY_ABS, compute  # noqa: E402

START = date(2024, 1, 7)  # domingo


CITIES = tuple(f"CIDADE{n:02d}" for n in range(12)) + ("ALFA",)


def make_rows(weeks=90, cities=CITIES, products=("GASOLINA_COMUM", "ETANOL_HIDRATADO"), seed=3,
              missing=(), stations=9, jump=None):
    """Passeio aleatório com degraus de R$ 0,05 por série, mais o agregado estadual."""
    rng = np.random.default_rng(seed)
    rows = []
    for product in products:
        for place in (*cities, pn.STATE):
            level = 5.5 + rng.random()
            for w in range(weeks):
                level += rng.choice([-0.05, 0.0, 0.0, 0.05])
                if (place, product, w) in missing:
                    continue
                value = level + (jump[3] if jump and (place, product, w) == jump[:3] else 0)
                rows.append((START + timedelta(weeks=w), place, product, round(value, 2),
                             200 if place == pn.STATE else stations, False))
    return rows


class PanelTests(unittest.TestCase):
    def test_calendar_is_continuous_and_gaps_stay_nan(self):
        rows = make_rows(weeks=10, missing={("ALFA", "GASOLINA_COMUM", 4)})
        panel = pn.build_panel(rows)
        s = panel.keys.index(("ALFA", "GASOLINA_COMUM"))
        self.assertEqual(len(panel.weeks), 10)
        self.assertTrue(np.isnan(panel.y[s, 4]))
        self.assertEqual(panel.weeks[1] - panel.weeks[0], timedelta(weeks=1))
        self.assertEqual(panel.weeks[0].weekday(), 6)

    def test_data_hash_depends_on_content_not_on_order(self):
        rows = make_rows(weeks=8)
        self.assertEqual(pn.data_hash(rows), pn.data_hash(list(reversed(rows))))
        changed = list(rows)
        changed[0] = (*changed[0][:3], changed[0][3] + 0.01, *changed[0][4:])
        self.assertNotEqual(pn.data_hash(rows), pn.data_hash(changed))


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.rows = make_rows(weeks=80)

    def check(self, rows, place="ALFA", product="GASOLINA_COMUM"):
        panel = pn.build_panel(rows)
        return pn.eligibility(panel, panel.keys.index((place, product)), panel.last)

    def test_complete_series_is_eligible(self):
        self.assertEqual(self.check(self.rows), (True, []))

    def test_short_history(self):
        ok, reasons = self.check(make_rows(weeks=40))
        self.assertFalse(ok)
        self.assertIn("menos_de_52_semanas_de_historico", reasons)

    def test_too_many_gaps_in_recent_window(self):
        missing = {("ALFA", "GASOLINA_COMUM", w) for w in range(40, 80, 2)}  # metade das semanas recentes
        ok, reasons = self.check(make_rows(weeks=80, missing=missing))
        self.assertFalse(ok)
        self.assertIn("dados_em_menos_de_80pct_das_semanas", reasons)

    def test_missing_origin_week_blocks(self):
        ok, reasons = self.check(make_rows(weeks=80, missing={("ALFA", "GASOLINA_COMUM", 79)}))
        self.assertFalse(ok)
        self.assertIn("sem_dado_na_semana_de_origem", reasons)

    def test_small_sample_blocks_cities_but_not_the_state(self):
        ok, reasons = self.check(make_rows(weeks=80, stations=2))
        self.assertFalse(ok)
        self.assertIn("mediana_de_postos_abaixo_de_3", reasons)
        self.assertTrue(self.check(make_rows(weeks=80, stations=2), place=pn.STATE)[0])

    def test_recent_low_coverage_blocks(self):
        rows = [(*r[:5], True) if (r[1], r[2]) == ("ALFA", "GASOLINA_COMUM") and r[0] == START + timedelta(weeks=78)
                else r for r in self.rows]
        ok, reasons = self.check(rows)
        self.assertFalse(ok)
        self.assertIn("cobertura_baixa_recente", reasons)

    def test_eligibility_at_an_origin_ignores_the_future(self):
        panel = pn.build_panel(self.rows)
        s = panel.keys.index(("ALFA", "GASOLINA_COMUM"))
        before = pn.eligibility(panel, s, 60)
        panel.y[s, 61:] = np.nan  # apagar o futuro não muda a elegibilidade na origem 60
        self.assertEqual(pn.eligibility(panel, s, 60), before)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.panel = pn.build_panel(make_rows(weeks=70, missing={("ALFA", "GASOLINA_COMUM", 30)}))
        self.s = self.panel.keys.index(("ALFA", "GASOLINA_COMUM"))

    def test_last_value(self):
        forecast = md.baseline_forecast(self.panel, "ultimo_valor", 2)
        self.assertEqual(forecast[self.s, 40], self.panel.y[self.s, 40])

    def test_moving_average_needs_three_of_four_weeks(self):
        forecast = md.baseline_forecast(self.panel, "media_movel_4", 1)
        window = self.panel.y[self.s, 37:41]
        self.assertAlmostEqual(forecast[self.s, 40], window.mean())
        # A janela 28..31 tem uma semana faltando (30): três de quatro ainda servem.
        self.assertAlmostEqual(forecast[self.s, 31], np.nanmean(self.panel.y[self.s, 28:32]))

    def test_seasonal_uses_the_same_week_of_the_previous_year(self):
        forecast = md.baseline_forecast(self.panel, "mesma_semana_ano_anterior", 3)
        self.assertEqual(forecast[self.s, 60], self.panel.y[self.s, 60 + 3 - 52])
        self.assertTrue(np.isnan(forecast[self.s, 20]))  # sem um ano de histórico


class NoLeakageTests(unittest.TestCase):
    def setUp(self):
        self.rows = make_rows(weeks=90)
        self.cut = 70

    def altered_future(self):
        panel = pn.build_panel(self.rows)
        panel.y[:, self.cut + 1:] += 5.0  # qualquer mudança depois do corte
        panel.stations[:, self.cut + 1:] = 1
        return panel

    def test_features_at_an_origin_do_not_depend_on_later_weeks(self):
        base = md.FeatureStore(pn.build_panel(self.rows))
        other = md.FeatureStore(self.altered_future())
        np.testing.assert_array_equal(base.matrix[:, : self.cut + 1], other.matrix[:, : self.cut + 1])

    def test_training_set_only_uses_targets_known_at_the_cutoff(self):
        base = md.FeatureStore(pn.build_panel(self.rows))
        other = md.FeatureStore(self.altered_future())
        x1, y1 = base.training_set(self.cut)
        x2, y2 = other.training_set(self.cut)
        pd.testing.assert_frame_equal(x1, x2)
        np.testing.assert_array_equal(y1, y2)

    def test_training_set_grows_with_the_cutoff(self):
        store = md.FeatureStore(pn.build_panel(self.rows))
        self.assertLess(len(store.training_set(60)[0]), len(store.training_set(80)[0]))


class MetricsTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({
            "actual": [6.0, 6.2, 6.5], "m": [6.1, 6.2, 6.3], "weight": [1.0, 1.0, 2.0], "scale": [0.1, 0.1, 0.1],
            "m_lo": [5.9, 6.0, 6.0], "m_hi": [6.3, 6.4, 6.4]})

    def test_score_values(self):
        s = ev.score(self.frame(), "m")
        self.assertAlmostEqual(s["mae"], (0.1 + 0.0 + 0.2) / 3)
        self.assertAlmostEqual(s["wmae"], (0.1 + 0.0 + 0.4) / 4)
        self.assertAlmostEqual(s["bias"], (0.1 + 0.0 - 0.2) / 3)  # previsão − observado
        self.assertAlmostEqual(s["coverage"], 2 / 3)  # 6.5 fica fora de [6.0, 6.4]
        self.assertAlmostEqual(s["interval_width"], 0.4)
        self.assertAlmostEqual(s["mase"], (1.0 + 0.0 + 2.0) / 3)

    def test_empty_frame(self):
        self.assertEqual(ev.score(self.frame().iloc[0:0], "m"), {"n": 0})


class IntervalTests(unittest.TestCase):
    def test_intervals_use_only_residuals_known_at_the_origin(self):
        rng = np.random.default_rng(0)
        records = []
        for origin in range(10, 40, 4):
            for h in (1, 2):
                for k in range(60):
                    actual = 6.0 + rng.normal(0, 0.1)
                    records.append({"origin": origin, "target": origin + h, "horizon": h, "series": k,
                                    "level": "municipio", "product": "GASOLINA_COMUM", "group": "x", "scale": 0.1,
                                    "weight": 1.0, "actual": actual, "m": 6.0})
        points = pd.DataFrame(records)
        base = ev.add_intervals(points, models=("m",))
        future = points.copy()
        future.loc[future["origin"] >= 30, "actual"] += 10  # muda só o que acontece depois da origem 26
        altered = ev.add_intervals(future, models=("m",))
        early = base["origin"] <= 26
        pd.testing.assert_frame_equal(base[early].reset_index(drop=True), altered[early].reset_index(drop=True))
        self.assertTrue(base.loc[base["origin"] == 10, "m_lo"].isna().all())  # nada para calibrar ainda
        done = base[base["origin"] == 38]
        self.assertTrue((done["m_lo"] < done["m"]).all() and (done["m_hi"] > done["m"]).all())


class DecisionTests(unittest.TestCase):
    def summary(self, cand_wmae, bias=0.0, coverage=0.8, group_wmae=None):
        def scores(wmae, cov=0.8, b=0.0):
            return {"n": 100, "mae": wmae, "wmae": wmae, "bias": b, "coverage": cov}
        base = {"ultimo_valor": scores(0.10), "media_movel_4": scores(0.12), "mesma_semana_ano_anterior": scores(0.4),
                md.CANDIDATE: scores(cand_wmae, coverage, bias)}
        groups = {"estado": {**base, md.CANDIDATE: scores(group_wmae if group_wmae else cand_wmae)}}
        return {"overall": base, "by_product": groups, "by_level": {}, "by_horizon": {}, "by_group": {}}

    def test_candidate_must_beat_the_best_baseline_by_five_percent(self):
        self.assertFalse(ev.decide(self.summary(0.098), True)["approved"])
        result = ev.decide(self.summary(0.094), True)
        self.assertTrue(result["approved"])
        self.assertEqual(result["best_baseline"], "ultimo_valor")

    def test_worse_candidate_keeps_the_baseline(self):
        result = ev.decide(self.summary(0.11), True)
        self.assertFalse(result["approved"])
        self.assertLess(result["improvement"], 0)

    def test_other_checks_each_block_approval(self):
        self.assertFalse(ev.decide(self.summary(0.09, coverage=0.5), True)["approved"])   # intervalo ruim
        self.assertFalse(ev.decide(self.summary(0.09, bias=0.05), True)["approved"])      # viés alto
        self.assertFalse(ev.decide(self.summary(0.09), False)["approved"])                # não reprodutível
        regression = ev.decide(self.summary(0.09, group_wmae=0.12), True)                 # piora em um grupo
        self.assertFalse(regression["approved"])
        self.assertTrue(regression["regressions"])


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        jump = ("ALFA", "GASOLINA_COMUM", 89, 0.60)  # salto grande na última semana
        cls.rows = make_rows(weeks=90, jump=jump)
        cls.result = compute(cls.rows, code_sha="teste", step=3, burn_in=2, min_origin=55)

    def test_publishes_only_a_model_with_intervals_for_eligible_series(self):
        result = self.result
        self.assertIn(result["published_model"], (*md.BASELINES, md.CANDIDATE))
        self.assertEqual(result["origin_week"], START + timedelta(weeks=89))
        self.assertEqual(len(result["forecasts"]) % 4, 0)
        self.assertTrue(result["forecasts"])
        for f in result["forecasts"]:
            self.assertLessEqual(f["lower"], f["point"])
            self.assertLessEqual(f["point"], f["upper"])
            self.assertEqual(f["target_week"], result["origin_week"] + timedelta(weeks=f["horizon"]))
        eligible = {(e["location"], e["product"]) for e in result["eligibility"] if e["eligible"]}
        self.assertEqual({(f["location"], f["product"]) for f in result["forecasts"]}, eligible)

    def test_reproducibility_check_tolerates_series_without_data_at_the_origin(self):
        # Série sem dado na última semana: a previsão do candidato é NaN nas duas execuções.
        rows = make_rows(weeks=90, missing={("CIDADE03", "GASOLINA_COMUM", 89)})
        again = compute(rows, code_sha="teste", step=3, burn_in=2, min_origin=55)
        self.assertTrue(again["reproducible"])

    def test_reproducible_same_data_same_outcome(self):
        again = compute(self.rows, code_sha="teste", step=3, burn_in=2, min_origin=55)
        self.assertTrue(self.result["reproducible"])
        self.assertEqual(again["data_hash"], self.result["data_hash"])
        self.assertEqual(again["forecasts"], self.result["forecasts"])
        self.assertEqual(again["summary"]["overall"], self.result["summary"]["overall"])
        self.assertEqual(again["decision"], self.result["decision"])

    def test_big_jump_is_an_unusual_variation_and_small_moves_are_not(self):
        flagged = {(a["location"], a["product"], a["week_start"]) for a in self.result["anomalies"]}
        last = START + timedelta(weeks=89)
        self.assertIn(("ALFA", "GASOLINA_COMUM", last), flagged)
        jump = next(a for a in self.result["anomalies"] if (a["location"], a["product"]) == ("ALFA", "GASOLINA_COMUM")
                    and a["week_start"] == last)
        self.assertEqual(jump["direction"], "acima")
        self.assertGreaterEqual(jump["residual"], MIN_ANOMALY_ABS)
        self.assertTrue(jump["observed"] > jump["upper"])
        self.assertTrue(all(abs(a["residual"]) >= MIN_ANOMALY_ABS for a in self.result["anomalies"]))

    def test_report_states_the_decision_without_claiming_a_gain(self):
        text = markdown(self.result)
        self.assertIn("Relatório do backtest", text)
        if self.result["decision"]["approved"]:
            self.assertIn("Candidato aprovado", text)
        else:
            self.assertIn("permanece publicado", text)


if __name__ == "__main__":
    unittest.main()
