"""Modelagem v2 (Marco 10) com dados sintéticos de resposta conhecida, antes de qualquer execução real.

Cobre: protocolo × código, alvos, métricas, logística, *as-of* das variáveis externas, ausência de
vazamento no treino, efeito plantado recuperado pela camada certa, ruído sem candidato, regra de
decisão e o lacre do teste no banco.
"""

from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.forecasting.panel import STATE, build_panel  # noqa: E402
from radar_combustiveis.modelv2 import decision, experiment, metrics, spec  # noqa: E402
from radar_combustiveis.modelv2.features import Features, labels, _producer_features, _usd_levels  # noqa: E402
from radar_combustiveis.modelv2.models import BaseRate, Logistic  # noqa: E402

PROTOCOL = ROOT / "docs" / "estudo" / "protocolo-modelagem.md"
START = date(2022, 11, 13)


class ProtocolMatchesCodeTests(unittest.TestCase):
    def test_numbers_in_the_protocol_are_the_code_constants(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for snippet in ("τ = R$ 0,05", "τ = 0,03 e 0,10", "a cada **13 semanas**", "λ = 1,0", "300 rodadas",
                        "variação absoluta ≥ 2%", "limitado a 52", "10 faixas", "**B = 2000**", "**20261013**",
                        "**4 semanas de origem**", "de até 0,05", "pelo menos −0,05", "pelo menos 200 pontos",
                        "h = 1, 2 e 4", "**h = 2**", "grande ≥ 20, médio 8 a 19, pequeno 3 a 7",
                        "60ª semana", "4 defasagens", "quantis 10% e 90%"):
            self.assertIn(snippet, text, snippet)
        self.assertEqual((spec.TAU, spec.TAU_SENSITIVITY, spec.RETRAIN_EVERY, spec.LOGIT_LAMBDA, spec.LGB_ROUNDS),
                         (0.05, (0.03, 0.10), 13, 1.0, 300))
        self.assertEqual((spec.EVENT_THRESHOLD, spec.WEEKS_SINCE_CAP, spec.CALIBRATION_BINS, spec.MAX_ECE),
                         (0.02, 52, 10, 0.05))
        self.assertEqual((spec.MIN_GROUP_POINTS, spec.MIN_GROUP_BSS, spec.HORIZONS, spec.PRIMARY_HORIZON),
                         (200, -0.05, (1, 2, 4), 2))
        self.assertEqual((spec.SIZE_LARGE, spec.SIZE_MEDIUM, spec.SIZE_SMALL, spec.MIN_ORIGIN, spec.DM_LAGS),
                         (20, 8, 3, 60, 4))
        self.assertEqual((spec.BOOTSTRAP_REPS, spec.SEED, spec.BOOTSTRAP_BLOCK_WEEKS), (2000, 20261013, 4))
        self.assertEqual(spec.LGB_CLASS_PARAMS["learning_rate"], 0.05)
        self.assertEqual(spec.LGB_CLASS_PARAMS["num_leaves"], 31)
        self.assertEqual(spec.INTERVAL_QUANTILES, (0.10, 0.90))


# -- Painéis sintéticos ------------------------------------------------------------------------


def make_rows(weeks, cities, state_fn, city_fn, product="GASOLINA_COMUM", stations=12):
    rows = []
    for t in range(weeks):
        w = START + timedelta(weeks=t)
        rows.append((w, STATE, product, round(state_fn(t), 4), stations * cities, False))
        for c in range(cities):
            rows.append((w, f"CIDADE {c:02d}", product, round(city_fn(c, t), 4), stations, False))
    return rows


def planted_rows(weeks=170, cities=24, seed=1):
    """O estado dá degraus de ±R$ 0,10 em torno de R$ 6,00; cada município repete o estado 2 semanas depois."""
    rng = np.random.default_rng(seed)
    state = np.empty(weeks)
    state[0] = 6.0
    for t in range(1, weeks):  # degraus ao acaso, puxados de volta a 6,00 (os níveis não saem da faixa)
        up = 0.2 - 0.6 * (state[t - 1] - 6.0)
        state[t] = state[t - 1] + rng.choice([-0.10, 0.0, 0.10], p=_probs(up))
    noise = rng.normal(0, 0.015, size=(cities, weeks))
    lagged = lambda c, t: state[max(t - 2, 0)] + 0.02 * c / cities + noise[c, t]  # noqa: E731
    return make_rows(weeks, cities, lambda t: state[t], lagged)


def _probs(up):
    up = min(max(up, 0.0), 0.4)
    return [0.4 - up, 0.6, up]


def noise_rows(weeks=170, cities=24, seed=2):
    """Sem nenhum sinal: cada município é um passeio aleatório (a variação futura não depende do passado)."""
    rng = np.random.default_rng(seed)
    values = 6.0 + np.cumsum(rng.choice([-0.06, 0.0, 0.06], size=(cities + 1, weeks)), axis=1)
    state = values[-1]  # o estado também é um passeio independente (a média dos municípios variaria menos)
    return make_rows(weeks, cities, lambda t: state[t], lambda c, t: values[c, t])


# -- Alvos, métricas, modelos ------------------------------------------------------------------


class TargetAndMetricTests(unittest.TestCase):
    def test_labels_use_tau_with_float_tolerance(self):
        rows = make_rows(6, 1, lambda t: 6.0, lambda c, t: [6.39, 6.44, 6.39, 6.43, 6.48, 6.48][t])
        panel = build_panel(rows)
        s = panel.keys.index(("CIDADE 00", "GASOLINA_COMUM"))
        self.assertEqual(list(labels(panel, 1)[s]), [2, 0, 1, 2, 1, -1])  # 6,44 − 6,39 = 0,05 conta como alta
        self.assertEqual(list(labels(panel, 2)[s][:4]), [1, 1, 2, 2])

    def test_brier_skill_logloss_balanced_accuracy_and_ece(self):
        y = np.array([0, 1, 2, 1])
        perfect = metrics.one_hot(y)
        uniform = np.full((4, 3), 1 / 3)
        self.assertEqual(metrics.brier_points(perfect, y).sum(), 0)
        self.assertAlmostEqual(metrics.brier_points(uniform, y)[0], 2 / 3)
        self.assertAlmostEqual(metrics.skill(metrics.brier_points(perfect, y), metrics.brier_points(uniform, y)), 1.0)
        self.assertEqual(metrics.balanced_accuracy(perfect, y), 1.0)
        self.assertAlmostEqual(metrics.log_loss(uniform, y), np.log(3))
        rng = np.random.default_rng(0)
        p = rng.dirichlet([1, 1, 1], size=20000)
        drawn = np.array([rng.choice(3, p=row) for row in p])
        self.assertLess(metrics.ece(p, drawn), 0.02)                       # calibrado por construção
        self.assertGreater(metrics.ece(np.roll(p, 1, axis=1), drawn), 0.1)  # trocado: descalibrado

    def test_holm_and_bootstrap(self):
        self.assertEqual(metrics.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
        origins = np.repeat(np.arange(40), 10)
        rng = np.random.default_rng(3)
        reference = rng.uniform(0.5, 0.7, size=400)
        better = reference * 0.8
        result = metrics.bootstrap_skill(origins, better, reference, reps=500)
        self.assertAlmostEqual(result["estimate"], 0.2, places=6)
        self.assertLess(result["ci"][0], 0.2 + 1e-9)
        self.assertGreater(result["ci"][0], 0.15)
        same = metrics.bootstrap_skill(origins, better, reference, reps=500)
        self.assertEqual(result, same)  # semente fixa
        idx = metrics.block_resamples(10, block=4, reps=3)
        self.assertEqual(idx.shape, (3, 10))
        self.assertTrue(((idx >= 0) & (idx < 10)).all())

    def test_diebold_mariano_detects_a_systematically_better_forecast(self):
        origins = np.repeat(np.arange(60), 5)
        rng = np.random.default_rng(4)
        worse = rng.uniform(0.1, 0.2, size=300) + 0.05
        better = worse - 0.05 + rng.normal(0, 0.005, size=300)
        result = metrics.diebold_mariano(origins, worse, better)
        self.assertGreater(result["statistic"], 0)
        self.assertLess(result["p"], 0.001)

    def test_logistic_recovers_known_probabilities(self):
        rng = np.random.default_rng(5)
        x = rng.normal(size=(6000, 2))
        logits = np.stack([-1.5 * x[:, 0], np.zeros(len(x)), 1.5 * x[:, 0] + 0.5 * x[:, 1]], axis=1)
        p = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
        y = np.array([rng.choice(3, p=row) for row in p])
        frame = pd.DataFrame({"a": x[:, 0], "b": x[:, 1], "product": 0})
        model = Logistic(lam=1e-3)
        model.products = 1
        fitted = model.fit(frame, y).predict(frame)
        self.assertTrue(model.converged)
        self.assertLess(np.abs(fitted - p).mean(), 0.03)

    def test_logistic_handles_missing_values_with_an_indicator(self):
        frame = pd.DataFrame({"a": [1.0, np.nan, 2.0, np.nan] * 50, "product": [0, 1] * 100})
        y = np.array([2, 0, 2, 0] * 50)  # a ausência é o sinal
        model = Logistic()
        model.products = 2
        p = model.fit(frame, y).predict(frame)
        self.assertGreater(p[1, 0], 0.8)
        self.assertGreater(p[0, 2], 0.8)

    def test_base_rate_by_product_and_month_with_laplace(self):
        base = BaseRate().fit([0, 0, 0, 1], [1, 1, 1, 1], [2, 2, 1, 0])
        np.testing.assert_allclose(base.predict([0], [1])[0], [1 / 6, 2 / 6, 3 / 6])
        np.testing.assert_allclose(base.predict([0], [7])[0], [1 / 6, 2 / 6, 3 / 6])  # mês sem dado: o produto
        self.assertAlmostEqual(base.predict([9], [1])[0].sum(), 1.0)                  # produto novo: geral


# -- Variáveis externas e vazamento ------------------------------------------------------------


class AsOfFeatureTests(unittest.TestCase):
    def test_producer_values_are_used_only_after_they_are_available(self):
        weekly = [{"period_end": date(2026, 1, 4) + timedelta(weeks=k), "value": 3.0 + (0.1 if k == 5 else 0.0),
                   "available_at": date(2026, 1, 4) + timedelta(weeks=k, days=12)} for k in range(6)]
        jump_seen = date(2026, 1, 4) + timedelta(weeks=5, days=12)
        before, after = _producer_features(weekly, [jump_seen - timedelta(days=1), jump_seen])
        self.assertAlmostEqual(before[0], 0.0)              # o reajuste ainda não tinha sido publicado
        self.assertAlmostEqual(after[0], 0.1 / 3.0, places=6)
        self.assertEqual((before[2], after[2]), (0.0, 1.0))  # evento de reajuste (≥ 2%)
        self.assertAlmostEqual(after[3], 12 / 7)  # a semana do evento terminou 12 dias antes do corte

    def test_usd_level_uses_the_seven_days_up_to_the_cutoff(self):
        daily = [{"period_end": date(2026, 1, 1) + timedelta(days=d), "value": 5.0 + d / 100,
                  "available_at": date(2026, 1, 2) + timedelta(days=d)} for d in range(20)]
        level = _usd_levels(daily, [date(2026, 1, 10)])[0]
        # disponíveis até 10/01: cotações até 09/01; janela de 7 dias: 04/01 a 09/01 (d = 3..8)
        self.assertAlmostEqual(level, np.mean([5.0 + d / 100 for d in range(3, 9)]))

    def test_training_pairs_never_see_a_target_after_the_cutoff(self):
        panel = build_panel(planted_rows())
        for h in spec.HORIZONS:
            lab = labels(panel, h)
            s, i = experiment.training_pairs(lab, h, cutoff=120)
            self.assertTrue(len(s) > 0)
            self.assertLessEqual(int((i + h).max()), 120)
            self.assertGreaterEqual(int(i.min()), spec.MIN_ORIGIN)


# -- Ponta a ponta com resposta conhecida ------------------------------------------------------


class EndToEndTests(unittest.TestCase):
    def run_layers(self, rows):
        panel = build_panel(rows)
        features = Features(panel)
        origins = list(range(130, 160))
        points = experiment.run_window(panel, features, origins, target_limit=165, first_cutoff=129,
                                       layers=("L1", "L2"), horizons=(2,), value=False)
        return points, decision.select_candidate(points, keys=decision.model_keys(layers=("L1", "L2")), reps=300)

    def test_planted_state_lead_is_found_by_the_state_layer(self):
        points, selection = self.run_layers(planted_rows())
        table = selection["validation"]
        self.assertGreater(len(points), 400)
        self.assertGreater(table["L2_logistica"]["estimate"], table["L1_logistica"]["estimate"] + 0.1)
        self.assertGreater(table["L2_logistica"]["ci"][0], 0)
        self.assertIn(selection["candidate"], ("L2_logistica", "L2_lightgbm"))

    def test_pure_noise_has_no_candidate(self):
        _, selection = self.run_layers(noise_rows())
        self.assertIsNone(selection["candidate"], selection["validation"])


class ReportPathTests(unittest.TestCase):
    """O caminho inteiro do relatório roda antes da leitura real do teste (que só pode acontecer uma vez)."""

    def test_validation_and_final_reports_from_a_synthetic_run(self):
        from radar_combustiveis.modelv2 import report
        panel = build_panel(planted_rows(cities=10))
        features = Features(panel)
        valid = experiment.run_window(panel, features, list(range(125, 145)), 146, 124)
        test = experiment.run_window(panel, features, list(range(147, 165)), panel.last, 146)
        selection = decision.select_candidate(valid, reps=200)
        meta = {"data_hash": "x" * 64, "series": len(panel.keys), "first_week": panel.weeks[0],
                "last_week": panel.weeks[-1], "code_sha": "abc", "protocol_commit": "def", "seed": spec.SEED,
                "bootstrap_reps": 200}
        summary = report.validation_summary(valid, selection, meta)
        self.assertIn("Candidato:", report.validation_markdown(summary))
        verdict = decision.decide(test, selection["candidate"], reproducible=True, reps=200)
        final = report.final_summary(test, summary, verdict, {}, valid, [{"access_id": 1}], meta)
        text = report.final_markdown(final)
        self.assertIn("## Decisão", text)
        self.assertIn("lido 1 vez(es)", text)
        self.assertEqual(set(final["values"]), {"L1", "L2", "L3"})
        self.assertTrue(all(0 <= v["interval_coverage"] <= 1 for v in final["values"].values()))
        self.assertIn("L2_vs_L1", final["secondary"])
        json_text = report.dumps(final)
        self.assertIn('"candidate"', json_text)


class DecisionRuleTests(unittest.TestCase):
    def points(self, model_probs, n_origins=30, per=40, products=("A",)):
        rng = np.random.default_rng(6)
        rows = []
        for o in range(n_origins):
            for k in range(per):
                label = int(rng.choice(3, p=[0.2, 0.6, 0.2]))
                good = metrics.one_hot([label])[0]  # acerta sempre, com certeza: calibrado
                p = good if model_probs == "good" else np.full(3, 1 / 3)
                rows.append({"origin": o, "horizon": 2, "label": label, "product": products[k % len(products)],
                             "size": "medio", "base_p0": 0.2, "base_p1": 0.6, "base_p2": 0.2,
                             "L1_logistica_p0": p[0], "L1_logistica_p1": p[1], "L1_logistica_p2": p[2]})
        return pd.DataFrame(rows)

    def test_good_candidate_is_approved_and_each_failure_is_named(self):
        good = self.points("good")
        verdict = decision.decide(good, "L1_logistica", reproducible=True, reps=300)
        self.assertTrue(verdict["checks"]["b_ganho_confirmado_no_teste"])
        self.assertTrue(verdict["checks"]["c_sem_piora_em_grupo"])
        self.assertTrue(verdict["approved"], verdict)
        self.assertFalse(decision.decide(good, "L1_logistica", reproducible=False, reps=300)["approved"])
        bad = decision.decide(self.points("uniform"), "L1_logistica", reproducible=True, reps=300)
        self.assertFalse(bad["checks"]["b_ganho_confirmado_no_teste"])
        self.assertFalse(bad["approved"])
        none = decision.decide(good, None, reproducible=True)
        self.assertEqual((none["approved"], none["candidate"]), (False, None))


# -- Lacre do teste no banco -------------------------------------------------------------------

from tests.test_api import ApiCase  # noqa: E402


class HoldoutSealTests(ApiCase):
    """Os dados sintéticos da API são de jul a set/2026: todos no teste final."""

    def test_development_loader_cannot_return_test_weeks_and_test_reads_are_logged(self):
        import psycopg
        from radar_combustiveis.db.connection import connect
        from radar_combustiveis.modelv2 import data
        with connect(self.admin_url) as conn:
            self.assertEqual(data.load_panel_rows(conn), [])  # nada até 2026-03-29
            with self.assertRaises(ValueError):
                data.load_panel_rows(conn, read_test=True)    # sem finalidade
            self.assertEqual(data.holdout_reads(conn), [])
            rows = data.load_panel_rows(conn, read_test=True, purpose="teste automatizado", code_sha="abc")
            self.assertGreater(len(rows), 0)
            reads = data.holdout_reads(conn)
        self.assertEqual(len(reads), 1)
        self.assertEqual((reads[0][3], reads[0][5]), ("teste automatizado", len(rows)))
        with psycopg.connect(self.api_url) as conn:  # a API não lê o registro do lacre
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT * FROM radar.holdout_access")


if __name__ == "__main__":
    unittest.main()
