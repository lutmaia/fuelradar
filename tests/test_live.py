"""Calibração e avaliação ao vivo, com dados sintéticos de resposta conhecida."""

from datetime import date, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.forecasting.panel import build_panel  # noqa: E402
from radar_combustiveis.modelv2 import calibration, live, metrics  # noqa: E402
from radar_combustiveis.modelv2.features import Features  # noqa: E402
from tests.test_modelv2 import planted_rows  # noqa: E402

PROTOCOL = ROOT / "docs" / "estudo" / "protocolo-ao-vivo.md"


class ProtocolTests(unittest.TestCase):
    def test_protocol_numbers_are_the_code_constants(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for snippet in ("**um parâmetro T por horizonte**", "T entre 0,25 e 4", "**26 origens vencidas em h = 2**",
                        "**13 origens vencidas mais recentes**", "**até 0,05**", "abaixo de **−0,05**",
                        "pelo menos 200 pontos", "B = 2000, semente 20261013"):
            self.assertIn(snippet, text, snippet)
        self.assertEqual((live.DECISION_ORIGINS, live.ALERT_ORIGINS, live.MAX_ECE, calibration.T_BOUNDS),
                         (26, 13, 0.05, (0.25, 4.0)))
        self.assertEqual((live.LAYER, live.MODEL), ("L2", "lightgbm"))


class CalibrationTests(unittest.TestCase):
    def test_temperature_one_is_identity_and_the_top_class_never_changes(self):
        rng = np.random.default_rng(0)
        p = rng.dirichlet([1, 1, 1], size=500)
        np.testing.assert_allclose(calibration.apply(p, 1.0), p, atol=1e-12)
        for t in (0.3, 2.5):
            q = calibration.apply(p, t)
            np.testing.assert_allclose(q.sum(axis=1), 1.0)
            self.assertTrue((q.argmax(axis=1) == p.argmax(axis=1)).all())
        self.assertLess(calibration.apply(p, 2.5).max(), p.max())  # T > 1: menos confiante

    def test_fit_recovers_the_temperature_of_an_overconfident_model(self):
        rng = np.random.default_rng(1)
        true = rng.dirichlet([2, 2, 2], size=20000)
        labels = np.array([rng.choice(3, p=row) for row in true])
        overconfident = calibration.apply(true, 0.5)  # quadrado das probabilidades, renormalizado
        t = calibration.fit(overconfident, labels)
        self.assertAlmostEqual(t, 2.0, delta=0.1)
        self.assertLess(metrics.ece(calibration.apply(overconfident, t), labels), metrics.ece(overconfident, labels))


def ledger_rows(origins, horizon=2, per=30, good=True, seed=3, start=date(2026, 1, 4)):
    """Registro sintético já pontuado: o modelo 'bom' acerta a classe com 70%; a referência é uniforme."""
    rng = np.random.default_rng(seed)
    rows = []
    for o in range(origins):
        for k in range(per):
            label = int(rng.choice(3))
            p = np.full(3, 0.15)
            p[label if good else (label + 1) % 3] = 0.7
            rows.append({"origin_week": start + timedelta(weeks=o), "location": f"C{k}", "product": "GASOLINA_COMUM",
                         "horizon": horizon, "target_week": start + timedelta(weeks=o + horizon), "size": "medio",
                         "last": 6.0, "p0": p[0], "p1": p[1], "p2": p[2], "base_p0": 1 / 3, "base_p1": 1 / 3,
                         "base_p2": 1 / 3, "temperature": 1.0, "model": live.MODEL_NAME, "label": label, "origin": o})
    return pd.DataFrame(rows)


class LedgerAndScoreboardTests(unittest.TestCase):
    def test_ledger_is_written_once_and_tampering_is_detected(self):
        frame = ledger_rows(1).drop(columns=["label", "origin"])
        with tempfile.TemporaryDirectory() as folder:
            first = live.write_ledger(frame, folder)
            path = first["path"]
            content = path.read_bytes()
            changed = frame.assign(p0=0.9)
            self.assertEqual(live.write_ledger(changed, folder)["status"], "existente")
            self.assertEqual(path.read_bytes(), content)  # não foi reescrito
            self.assertEqual(live.check_manifest(folder), [])
            back = live.read_ledgers(folder)
            self.assertEqual(len(back), len(frame))
            self.assertEqual(back["origin_week"].iloc[0], date(2026, 1, 4))
            path.write_bytes(content.replace(b"0.700000", b"0.800000", 1))
            self.assertEqual(live.check_manifest(folder), [path.name])

    def test_decision_waits_for_26_origins_and_then_applies_the_rule(self):
        early = live.scoreboard(ledger_rows(20), reps=200)
        self.assertEqual(early["decision"]["status"], "pendente")
        self.assertEqual(early["decision"]["origins_matured"], 20)
        self.assertGreater(early["horizons"][2]["estimate"], 0)
        good = live.scoreboard(ledger_rows(30), reps=200)
        self.assertEqual(good["decision"]["origins_used"], 26)  # só as 26 primeiras decidem
        self.assertTrue(good["decision"]["checks"]["ganho_com_ic_acima_de_zero"])
        self.assertIn(good["decision"]["status"], ("oficial", "reprovado"))
        bad = live.scoreboard(ledger_rows(30, good=False), reps=200)
        self.assertEqual(bad["decision"]["status"], "reprovado")
        self.assertTrue(bad["alert"]["degraded"])

    def test_decision_does_not_change_after_the_26th_origin(self):
        h2 = ledger_rows(26)
        h4 = ledger_rows(26, horizon=4, seed=5)
        cutoff = h2["target_week"].max()
        decided = live.scoreboard(pd.concat([h2, h4[h4["target_week"] <= cutoff]]), reps=200)
        # Duas semanas depois: as previsões de 4 semanas das últimas origens vencem, e são ruins.
        bad = ledger_rows(26, horizon=4, seed=5, good=False)
        h4_later = pd.concat([h4[h4["target_week"] <= cutoff], bad[bad["target_week"] > cutoff]])
        later = live.scoreboard(pd.concat([ledger_rows(28), h4_later]), reps=200)
        self.assertEqual(later["decision"], decided["decision"])  # o que vence depois não entra
        self.assertNotEqual(live.decide(pd.concat([h2, h4_later]), reps=200)["groups"],
                            decided["decision"]["groups"])  # se entrasse, a decisão mudaria
        self.assertEqual(len(live.decision_points(h4, [0, 25])), 0)  # sem h = 2 conferido, nada decide

    def test_calibrated_and_correct_model_becomes_official(self):
        rows = ledger_rows(30)
        rng = np.random.default_rng(4)  # probabilidades calibradas: a classe sai sorteada delas
        p = rng.dirichlet([0.6, 0.6, 0.6], size=len(rows))
        rows[["p0", "p1", "p2"]] = p
        rows["label"] = [rng.choice(3, p=row) for row in p]
        board = live.scoreboard(rows, reps=200)
        self.assertEqual(board["decision"]["status"], "oficial", board["decision"])


class EndToEndLiveTests(unittest.TestCase):
    def test_predict_register_then_score_when_the_target_week_arrives(self):
        rows = planted_rows(weeks=150)
        later = [r for r in rows if r[0] <= date(2022, 11, 13) + timedelta(weeks=145)]
        panel = build_panel(later)
        features = Features(panel)
        models = live.train(panel, features)
        forecasts = live.predict(panel, features, models, {1: 1.0, 2: 1.2, 4: 1.0})
        self.assertEqual(set(forecasts["horizon"]), {1, 2, 4})
        self.assertTrue(np.allclose(forecasts[["p0", "p1", "p2"]].sum(axis=1), 1.0))
        self.assertEqual(forecasts["origin_week"].iloc[0], panel.weeks[-1])
        self.assertEqual(live.score(forecasts, panel).shape[0], 0)  # nada venceu ainda
        full = build_panel(rows)
        scored = live.score(forecasts, full)
        self.assertEqual(set(scored["horizon"]), {1, 2, 4})
        series = scored.iloc[0]
        s = full.keys.index((series["location"], series["product"]))
        t = full.index_of(series["target_week"])
        self.assertAlmostEqual(series["actual"], full.y[s, t])


# -- API e painel -------------------------------------------------------------------------------

from tests.test_api import ApiCase, LAST, insert_published_model  # noqa: E402


class LiveApiTests(ApiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        insert_published_model(cls.admin_url)
        import psycopg
        with psycopg.connect(cls.admin_url) as conn:
            gasoline = conn.execute("SELECT product_id FROM radar.dim_product WHERE canonical_name = 'GASOLINA_COMUM'"
                                    ).fetchone()[0]
            for h, p in ((1, (0.2, 0.6, 0.2)), (2, (0.3, 0.4, 0.3)), (4, (0.4, 0.3, 0.3))):
                conn.execute("""INSERT INTO radar.forecast_class (origin_week, uf, location_id, product_id, horizon,
                                    target_week, p_down, p_flat, p_up, model, temperature)
                                VALUES (%s, 'SP', NULL, %s, %s, %s, %s, %s, %s, 'classe_l2_lightgbm_calibrado', 1.1)""",
                             (LAST, gasoline, h, LAST + timedelta(weeks=h), *p))
            conn.commit()

    def set_scoreboard(self, status):
        import psycopg
        body = {"horizons": {"2": {"origins": 3, "points": 90, "estimate": 0.1, "ci": [-0.2, 0.3], "p": 0.4,
                                   "ece": 0.08}},
                "alert": None, "decision": {"status": status, "origins_matured": 3, "origins_needed": 26},
                "ledger_origins": [LAST.isoformat()]}
        with psycopg.connect(self.admin_url) as conn:
            conn.execute("DELETE FROM radar.live_scoreboard")
            conn.execute("INSERT INTO radar.live_scoreboard (body) VALUES (%s::jsonb)", (json.dumps(body),))
            conn.commit()

    def test_forecast_carries_experimental_probabilities_and_the_scoreboard(self):
        self.set_scoreboard("pendente")
        body = self.ok("/api/v1/forecasts", product="GASOLINA_COMUM")
        classes = body["classes"]
        self.assertEqual((classes["status"], classes["origin_week_start"]), ("experimental", LAST.isoformat()))
        self.assertEqual([(i["horizon"], i["p_flat"]) for i in classes["items"]], [(1, 0.6), (2, 0.4), (4, 0.3)])
        board = self.ok("/api/v1/models/scoreboard")
        self.assertEqual((board["status"], board["origins_matured"], board["origins_needed"]), ("experimental", 3, 26))
        city = self.ok("/api/v1/forecasts", product="GASOLINA_COMUM", municipality="Campinas")
        self.assertIsNone(city["classes"])  # sem previsão de classe registrada para a série

    def test_rejected_model_disappears_from_forecasts(self):
        self.set_scoreboard("reprovado")
        self.assertIsNone(self.ok("/api/v1/forecasts", product="GASOLINA_COMUM")["classes"])
        self.assertEqual(self.ok("/api/v1/models/scoreboard")["status"], "reprovado")

    def test_no_scoreboard_yet_is_a_readable_404(self):
        import psycopg
        with psycopg.connect(self.admin_url) as conn:
            conn.execute("DELETE FROM radar.live_scoreboard")
            conn.commit()
        self.assertError(self.get("/api/v1/models/scoreboard"), 404, "NO_SCOREBOARD")
        self.assertEqual(self.ok("/api/v1/forecasts", product="GASOLINA_COMUM")["classes"]["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
