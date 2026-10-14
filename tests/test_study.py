"""Estudo do Marco 8 (Q1 a Q3) com dados sintéticos de resposta conhecida, sem banco.

Cada análise precisa recuperar o efeito que foi plantado nos dados, não achar efeito onde não há,
e recusar semanas do teste final. Sobrevivência é conferida contra a implementação do scipy.
"""

from datetime import date, timedelta
import math
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from radar_combustiveis.forecasting import protocol  # noqa: E402
from radar_combustiveis.study import common, descriptive as ds, gate, q1, q2, q3  # noqa: E402

START = date(2023, 1, 1)  # domingo, dentro do subperíodo A
GC = "GASOLINA_COMUM"


def week(i):
    return START + timedelta(weeks=i)


class CommonTests(unittest.TestCase):
    def test_holm_matches_the_hand_computation_and_skips_nan(self):
        adjusted = common.holm([0.01, 0.04, 0.03, 0.005, math.nan])
        np.testing.assert_allclose(adjusted[:4], [0.03, 0.06, 0.06, 0.02])
        self.assertTrue(math.isnan(adjusted[4]))

    def test_brand_aliases_and_size_classes(self):
        self.assertEqual(common.normalize_brand(" vibra energia "), "VIBRA")
        self.assertEqual(common.normalize_brand("ALESAT"), "ALE")
        self.assertIsNone(common.normalize_brand(None))
        self.assertEqual([common.size_class(v) for v in (25, 20, 19, 8, 7, 3, 2)],
                         ["grande", "grande", "medio", "medio", "pequeno", "pequeno", None])

    def test_same_sign(self):
        self.assertTrue(common.same_sign(-1, -0.2, -3))
        self.assertFalse(common.same_sign(-1, 0.2))
        self.assertFalse(common.same_sign(-1, math.nan))
        self.assertFalse(common.same_sign(-1, 0))

    def test_block_bootstrap_draws_contiguous_blocks_and_is_reproducible(self):
        seen = []

        def stat(groups):
            seen.append(groups)
            return float(np.mean(groups))

        groups = list(range(10))
        a = common.block_bootstrap(groups, stat, reps=50, block=4, seed=7)
        b = common.block_bootstrap(groups, stat, reps=50, block=4, seed=7)
        np.testing.assert_array_equal(a, b)
        for draw in seen:
            self.assertEqual(len(draw), 10)
            for first in range(0, 8, 4):  # cada bloco completo é uma sequência de semanas seguidas
                block = draw[first:first + 4]
                self.assertEqual(block, list(range(block[0], block[0] + 4)))

    def test_kaplan_meier_by_hand_and_against_scipy(self):
        times, surv, median = common.kaplan_meier([1, 2, 2, 3, 4], [1, 1, 0, 1, 0])
        np.testing.assert_allclose(times, [1, 2, 3])
        np.testing.assert_allclose(surv, [0.8, 0.6, 0.3])
        self.assertEqual(median, 3)
        rng = np.random.default_rng(1)
        d, e = rng.integers(0, 12, 300), rng.random(300) < 0.7
        times, surv, _ = common.kaplan_meier(d, e)
        ref = stats.ecdf(stats.CensoredData(uncensored=d[e], right=d[~e])).sf
        np.testing.assert_allclose(surv, ref.evaluate(times), atol=1e-12)

    def test_logrank_against_scipy(self):
        rng = np.random.default_rng(2)
        da, ea = rng.integers(0, 10, 200), rng.random(200) < 0.8
        db, eb = rng.integers(1, 14, 150), rng.random(150) < 0.6
        ours = common.logrank(da, ea, db, eb)
        ref = stats.logrank(stats.CensoredData(uncensored=da[ea], right=da[~ea]),
                            stats.CensoredData(uncensored=db[eb], right=db[~eb])).pvalue
        self.assertAlmostEqual(ours, ref, places=10)
        self.assertAlmostEqual(common.logrank(da, ea, da, ea), 1.0)

    def test_holdout_and_early_weeks_are_refused(self):
        with self.assertRaises(protocol.HoldoutViolation):
            common.check_window([protocol.VALID_END, protocol.TEST_START])
        with self.assertRaises(ValueError):
            common.check_window([protocol.STUDY_START - timedelta(weeks=1)])


# -- Q1 -----------------------------------------------------------------------------------------


def q1_data(gap=math.log(0.97), cities=30, weeks=40, stations=10, seed=0, cluster_sd=0.01):
    """Bandeira branca concentrada nos municípios caros: a diferença bruta tem o sinal errado."""
    rng = np.random.default_rng(seed)
    rows, sid = [], 0
    for m in range(cities):
        level = math.log(5.5) + 0.01 * m
        whites = 1 + (m * 7) // cities  # de 1 a 7 brancas: mais nos municípios caros
        for s in range(stations):
            sid += 1
            white = s < whites
            brand = "BRANCA" if white else ("IPIRANGA", "RAIZEN", "VIBRA ENERGIA")[s % 3]
            station_effect = rng.normal(0, cluster_sd)
            for w in range(weeks):
                logp = level + 0.002 * w + gap * white + station_effect + rng.normal(0, 0.01)
                rows.append(dict(station_id=sid, municipality=f"M{m:02d}", product=GC, week_start=week(w),
                                 price=math.exp(logp), brand=brand, postal_code=f"1{m:02d}{s % 2}0-000",
                                 extreme=False))
    return pd.DataFrame(rows)


class Q1Tests(unittest.TestCase):
    def test_recovers_the_planted_gap_that_the_raw_mean_gets_wrong(self):
        obs = q1_data()
        white = obs["brand"] == "BRANCA"
        self.assertGreater(obs.loc[white, "price"].mean(), obs.loc[~white, "price"].mean())  # confundido
        r = q1.analyze(obs)
        p = r["primary"]
        self.assertAlmostEqual(p["pct"], -3.0, delta=0.3)
        self.assertLess(p["pct_ci"][0], -3.0)
        self.assertGreater(p["pct_ci"][1], -3.0)
        self.assertEqual(p["n_clusters"], 300)
        for name in ("vizinhanca_cep5", "sem_preco_extremo", "subperiodo_a"):
            self.assertLess(r["robustness"][name]["pct"], 0, name)
        # Subperíodo B não tem nenhuma semana destes dados: sem estimativa, não há "mesmo sinal".
        self.assertTrue(math.isnan(r["robustness"]["subperiodo_b"]["beta"]))
        self.assertFalse(r["stable"])

    def test_stable_when_both_subperiods_agree(self):
        early, late = q1_data(weeks=20), q1_data(weeks=20, seed=1)
        late["week_start"] = late["week_start"] + (protocol.SUBPERIODS[1][0] - START)
        self.assertTrue(q1.analyze(pd.concat([early, late]))["stable"])

    def test_big_brands_are_compared_against_white_and_aliases_are_merged(self):
        brands = q1.analyze(q1_data())["brands"]
        self.assertEqual(set(brands), {"IPIRANGA", "RAIZEN", "VIBRA"})
        for b in brands.values():
            self.assertAlmostEqual(b["pct"], 100 * (1 / 0.97 - 1), delta=0.4)
            self.assertLess(b["p_holm"], 0.05)

    def test_no_gap_gives_an_interval_with_zero(self):
        p = q1.analyze(q1_data(gap=0.0, seed=4))["primary"]
        self.assertLess(p["pct_ci"][0], 0)
        self.assertGreater(p["pct_ci"][1], 0)

    def test_clustered_interval_has_close_to_nominal_coverage(self):
        """Com efeito de posto persistente, o IC agrupado precisa cobrir o valor real ~95% das vezes."""
        hits = 0
        reps = 120
        for seed in range(reps):
            df = q1.prepare(q1_data(cities=8, weeks=10, stations=8, seed=100 + seed, cluster_sd=0.03))
            low, high = q1.white_gap(df)["pct_ci"]
            hits += low <= -3.0 <= high
        self.assertGreaterEqual(hits / reps, 0.88)

    def test_cells_without_both_kinds_of_station_do_not_count(self):
        obs = q1_data(cities=4, weeks=3)
        lonely = obs[obs["municipality"] == "M00"].copy()
        lonely["municipality"], lonely["brand"] = "SO_BANDEIRADOS", "IPIRANGA"
        before = q1.white_gap(q1.prepare(obs))
        after = q1.white_gap(q1.prepare(pd.concat([obs, lonely])))
        self.assertEqual(before["n_obs"], after["n_obs"])
        self.assertAlmostEqual(before["beta"], after["beta"])

    def test_refuses_the_final_test(self):
        obs = q1_data(cities=3, weeks=2)
        obs.loc[0, "week_start"] = protocol.TEST_START
        with self.assertRaises(protocol.HoldoutViolation):
            q1.analyze(obs)


# -- Q2 -----------------------------------------------------------------------------------------


def q2_data(up=0.12, down=0.06, p_up=0.2, p_down=0.15, stations=120, weeks=80, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(stations):
        price = 5.0
        for w in range(weeks):
            u = rng.random()
            if u < p_up:
                price += up
            elif u < p_up + p_down:
                price -= down
            rows.append(dict(station_id=s, product=GC, week_start=week(w), price=round(price, 3), extreme=False))
    return pd.DataFrame(rows)


def series(prices, weeks=None, station=1):
    weeks = weeks if weeks is not None else range(len(prices))
    return pd.DataFrame(dict(station_id=station, product=GC, week_start=[week(w) for w in weeks],
                             price=prices, extreme=False))


class Q2Tests(unittest.TestCase):
    def test_pairs_need_consecutive_weeks_and_cents_survive_floating_point(self):
        p = q2.pairs(series([5.99, 5.98, 6.10, 6.00], weeks=[0, 1, 3, 4]))
        self.assertEqual(list(p["delta"]), [-0.01, -0.10])  # o par 1 → 3 tem lacuna e sai
        stats_ = q2.change_stats(p)
        self.assertEqual((stats_["changes"], stats_["downs"]), (2, 2))

    def test_spells_events_and_censoring_by_hand(self):
        obs = pd.concat([series([5.00, 5.00, 5.10, 5.10, 5.10, 5.05, 5.05, 5.05], weeks=[0, 1, 2, 3, 4, 5, 6, 8]),
                         series([4.0, 4.2, 4.2], station=2)])
        sp = q2.spells(obs)
        rows = sorted(map(tuple, sp[["direction", "duration", "event"]].to_numpy().tolist()))
        # Posto 1: alta em 2, queda em 5 (3 semanas, evento); a queda é censurada antes da lacuna (6 → 8).
        # Posto 2: alta em 1, censurada no fim dos dados (1 semana).
        self.assertEqual(rows, [(-1, 1, False), (1, 1, False), (1, 3, True)])

    def test_recovers_a_planted_size_asymmetry(self):
        r = q2.analyze(q2_data(), reps=300)
        p = r["primary"]
        self.assertAlmostEqual(p["estimate"], 0.06, places=6)
        self.assertGreater(p["ci"][0], 0)
        d = r["descriptive"][GC]
        self.assertAlmostEqual(d["frac_up"], 0.2, delta=0.02)
        self.assertAlmostEqual(d["frac_down"], 0.15, delta=0.02)
        self.assertAlmostEqual(r["up_minus_down"]["estimate"], 0.05, delta=0.02)
        self.assertAlmostEqual(r["robustness"]["limiar_0_05"], 0.06, places=6)
        # Sem dados no subperíodo B, não há "mesmo sinal": o achado não pode ser declarado estável.
        self.assertTrue(math.isnan(r["robustness"]["subperiodo_b"]))
        self.assertFalse(r["stable"])

    def test_stable_when_every_check_agrees(self):
        a, b = protocol.SUBPERIODS
        obs = q2_data(weeks=40)
        late = q2_data(weeks=40, seed=1)
        late["week_start"] = late["week_start"] + (b[0] - START)
        r = q2.analyze(pd.concat([obs, late]), reps=200)
        self.assertTrue(r["stable"])

    def test_symmetric_changes_give_an_interval_with_zero(self):
        p = q2.analyze(q2_data(up=0.08, down=0.08, p_down=0.2, seed=3), reps=300)["primary"]
        self.assertEqual(p["estimate"], 0)
        self.assertLessEqual(p["ci"][0], 0)
        self.assertGreaterEqual(p["ci"][1], 0)

    def test_refuses_the_final_test(self):
        obs = q2_data(stations=2, weeks=3)
        obs.loc[0, "week_start"] = protocol.TEST_START
        with self.assertRaises(protocol.HoldoutViolation):
            q2.analyze(obs, reps=10)

    def test_duration_is_longer_when_changes_are_rare(self):
        r = q2.analyze(q2_data(p_up=0.05, p_down=0.05), reps=50)
        median = r["durations"][GC]["median_weeks"]
        self.assertGreaterEqual(median, 5)   # geométrica com p = 0,1 por semana: mediana ≈ 7
        self.assertLessEqual(median, 9)


# -- Q3 -----------------------------------------------------------------------------------------


def q3_data(follow=True, weeks=150, seed=0):
    """Quatro grandes, dez médios e dois pequenos; os médios copiam o choque dos grandes uma semana depois."""
    rng = np.random.default_rng(seed)
    shock = rng.normal(0, 0.05, weeks)
    rows = []
    groups = [(f"G{i}", 25) for i in range(4)] + [(f"M{i}", 10) for i in range(10)] + [(f"P{i}", 4) for i in range(2)]
    for name, stations in groups:
        level = 5.0
        for w in range(weeks):
            if name.startswith("G"):
                delta = shock[w] + rng.normal(0, 0.005)
            elif follow:
                delta = (shock[w - 1] if w else 0) + rng.normal(0, 0.01)
            else:
                delta = rng.normal(0, 0.05)
            level += delta
            rows.append(dict(municipality=name, product=GC, week_start=week(w), median=level,
                             stations=stations, low_coverage=False))
    city = pd.DataFrame(rows)
    state = city[city["municipality"].str.startswith("G")].groupby("week_start", as_index=False)["median"].mean()
    state["product"] = GC
    return city, state


class Q3Tests(unittest.TestCase):
    def test_sizes_pick_leaders_and_followers(self):
        city, state = q3_data(weeks=40)
        r = q3.analyze(city, state)
        self.assertEqual(r["leaders"], ["G0", "G1", "G2", "G3"])
        self.assertEqual(r["followers"], [f"M{i}" for i in range(10)])

    def test_detects_planted_precedence_and_not_the_reverse(self):
        r = q3.analyze(*q3_data())
        self.assertEqual(r["primary"]["testable"], 10)
        self.assertEqual(r["primary"]["share_forward"], 1.0)
        self.assertLessEqual(r["primary"]["share_reverse"], 0.2)
        best = [v["best_lag"] for v in r["cross_correlation"].values()]
        self.assertEqual(set(best), {1})

    def test_independent_followers_show_no_precedence(self):
        r = q3.analyze(*q3_data(follow=False, seed=5))
        self.assertLess(r["primary"]["share_forward"], q3.MIN_FOLLOWER_SHARE)
        self.assertFalse(r["stable"])

    def test_low_coverage_week_is_a_gap_not_a_value(self):
        city, _ = q3_data(weeks=10)
        city.loc[(city["municipality"] == "M0") & (city["week_start"] == week(5)), "low_coverage"] = True
        weeks = q3.calendar(city["week_start"])
        deltas = q3.wide_medians(city, GC, weeks).diff()
        self.assertTrue(np.isnan(deltas.loc[week(5), "M0"]))
        self.assertTrue(np.isnan(deltas.loc[week(6), "M0"]))
        self.assertTrue(np.isfinite(deltas.loc[week(7), "M0"]))

    def test_follow_times_by_hand(self):
        weeks = [week(i) for i in range(14)]
        base = {"A": [5.0] * 14, "B": [5.0] * 14, "C": [5.0] * 14, "D": [5.0] * 14}
        base["A"][4:] = [5.2] * 10            # acompanha na própria semana do evento (k = 0)
        base["B"][6:] = [5.06] * 8            # acompanha duas semanas depois
        base["D"][5] = math.nan               # lacuna em k = 1: censurado em 0
        medians = pd.DataFrame(base, index=weeks)
        out = q3.follow_times(medians, [(4, 1)], ["A", "B", "C", "D"]).set_index("municipality")
        self.assertEqual(tuple(out.loc["A"][["weeks", "followed"]]), (0, True))
        self.assertEqual(tuple(out.loc["B"][["weeks", "followed"]]), (2, True))
        self.assertEqual(tuple(out.loc["C"][["weeks", "followed"]]), (7, False))
        self.assertEqual(tuple(out.loc["D"][["weeks", "followed"]]), (0, False))
        # Um novo evento duas semanas depois encerra a janela do primeiro.
        out = q3.follow_times(medians, [(4, 1), (6, -1)], ["C"])
        self.assertEqual(out.iloc[0][["weeks", "followed"]].tolist(), [1, False])

    def test_too_few_events_in_one_direction_fall_back_to_the_lower_threshold(self):
        weeks = [week(i) for i in range(30)]
        steps = [0.0] * 30
        for i in (2, 6, 10, 14, 18):
            steps[i] = 0.12
        for i in (22, 26):
            steps[i] = -0.07
        state = pd.DataFrame(dict(product=GC, week_start=weeks, median=5 + np.cumsum(steps)))
        events, thresholds = q3.choose_events(state, GC, weeks)
        self.assertEqual(thresholds, {1: 0.10, -1: 0.05})
        self.assertEqual(len(events), 7)

    def test_precedence_needs_enough_weeks(self):
        y = pd.Series(np.random.default_rng(0).normal(size=20))
        p, n = q3.precedence(y, y.shift(1))
        self.assertTrue(math.isnan(p))
        self.assertLess(n, q3.MIN_OBS)

    def test_refuses_the_final_test(self):
        city, state = q3_data(weeks=5)
        state.loc[0, "week_start"] = protocol.TEST_START
        with self.assertRaises(protocol.HoldoutViolation):
            q3.analyze(city, state)


class ReportTests(unittest.TestCase):
    def test_reports_are_written_with_brazilian_numbers_and_the_gate(self):
        import json
        import tempfile
        from radar_combustiveis.study.report import write_reports
        city, state = q3_data(weeks=60)
        results = dict(q1=q1.analyze(q1_data(cities=10, weeks=12)), q2=q2.analyze(q2_data(stations=30), reps=30),
                       q3=q3.analyze(city, state))
        meta = dict(uf="SP", code_sha="abc", protocol_commit="def", seed=protocol.SEED, bootstrap_reps=30,
                    data_hashes=dict(combined="1" * 64, observations="2" * 64, city="3" * 64, state="4" * 64),
                    window=[protocol.STUDY_START, protocol.STUDY_END], observations=1234567, weeks_with_data=10)
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_reports(meta, results, gate.g1(results), Path(tmp))
            self.assertEqual(sorted(p.name for p in paths),
                             ["q1.html", "q1.md", "q2.html", "q2.md", "q3.html", "q3.md", "resultados.json", "resumo.md"])
            summary = (Path(tmp) / "resumo.md").read_text(encoding="utf-8")
            q1_text = (Path(tmp) / "q1.md").read_text(encoding="utf-8")
            data = json.loads((Path(tmp) / "resultados.json").read_text(encoding="utf-8"))
        self.assertIn("1.234.567 observações", summary)
        self.assertIn("Gate G1: não passou", summary)
        self.assertRegex(q1_text, r"\*\*-3,\d\d%\*\*")      # decimal com vírgula
        self.assertNotRegex(q1_text, r"-\d+\.\d\d%")       # nunca ponto decimal
        self.assertIsNone(data["q1"]["robustness"]["subperiodo_b"]["beta"])  # NaN vira null no JSON


class DescriptiveTests(unittest.TestCase):
    def test_ethanol_pays_at_70_percent_and_low_coverage_is_skipped(self):
        rows = []
        for w in range(30):
            for city, ratio in (("A", 0.65), ("B", 0.70), ("C", 0.75)):
                rows.append(dict(municipality=city, product=GC, week_start=week(w), median=6.0, stations=9,
                                 low_coverage=False))
                rows.append(dict(municipality=city, product=ds.ETHANOL, week_start=week(w), median=6.0 * ratio,
                                 stations=9, low_coverage=(city == "C" and w < 2)))
        city = pd.DataFrame(rows)
        state = pd.DataFrame([dict(product=p, week_start=week(w), median=m) for w in range(30)
                              for p, m in ((GC, 6.0), (ds.ETHANOL, 4.0 if w < 10 else 4.5))])
        r = ds.ethanol_vs_gasoline(city, state)
        self.assertEqual(r["city_weeks"], 88)                      # C perde 2 semanas de cobertura baixa
        self.assertAlmostEqual(r["share_city_weeks"], 60 / 88)    # A e B compensam (70% exato conta)
        self.assertAlmostEqual(r["state"]["share"], 10 / 30)
        self.assertEqual([c["municipality"] for c in r["most"]][:2], ["A", "B"])
        self.assertEqual(r["least"][0]["municipality"], "C")
        self.assertEqual((r["latest"]["cities"], r["latest"]["paying"]), (3, 2))
        self.assertEqual(r["state"]["min"]["week"], week(0))

    def test_station_choice_saving_ignores_small_weeks_and_extremes(self):
        rows = []
        for w in range(30):
            for s, price in enumerate([5.80, 6.00, 6.10, 6.20, 6.30]):
                rows.append(dict(station_id=s, municipality="A", product=GC, week_start=week(w), price=price,
                                 extreme=False))
            rows.append(dict(station_id=9, municipality="A", product=GC, week_start=week(w), price=4.0, extreme=True))
            for s, price in enumerate([5.0, 5.5]):  # só 2 postos: não entra
                rows.append(dict(station_id=20 + s, municipality="B", product=GC, week_start=week(w), price=price,
                                 extreme=False))
        r = ds.station_choice(pd.DataFrame(rows), sizes={"A": "medio"})
        self.assertEqual(r["city_weeks"], 30)
        self.assertAlmostEqual(r["saving"]["median"], 0.30)          # 6,10 − 5,80
        self.assertAlmostEqual(r["saving_tank"], 15.0)
        self.assertAlmostEqual(r["spread"]["median"], 0.20)          # 6,20 − 6,00
        self.assertEqual(r["by_size"]["medio"]["city_weeks"], 30)
        with_extreme = ds.station_choice(pd.DataFrame(rows), exclude_extreme=False)
        self.assertGreater(with_extreme["saving"]["median"], 0.30)  # o 4,00 vira o mínimo
        self.assertTrue(math.isnan(r["typical_change"]))            # preços constantes: nenhuma mudança

    def test_regions_and_difference_to_the_capital(self):
        rows = []
        for w in range(10):
            for city, price in (("SAO PAULO", 6.0), ("SANTOS", 6.2), ("CAMPINAS", 5.9), ("OSASCO", 6.1)):
                rows.append(dict(station_id=city, municipality=city, product=GC, week_start=week(w),
                                 price=price + (0.2 if city == "CAMPINAS" and w >= 8 else 0), extreme=False))
        r = ds.regions(pd.DataFrame(rows))
        self.assertEqual(r["municipalities"]["litoral"], ["SANTOS"])
        self.assertEqual(r["municipalities"]["metropolitana"], ["OSASCO"])
        gc = r["products"][GC]
        self.assertAlmostEqual(gc["litoral"]["median_diff"], 0.2)
        self.assertAlmostEqual(gc["interior"]["median_diff"], -0.1)
        self.assertAlmostEqual(gc["interior"]["share_cheaper"], 0.8)
        self.assertEqual(ds.region_of("SAO PAULO"), "capital")
        self.assertEqual(ds.region_of("RIBEIRAO PRETO"), "interior")

    def test_descriptive_report_is_written(self):
        import tempfile
        from radar_combustiveis.study.report import write_descriptive
        city, state = q3_data(weeks=40)
        ethanol = city.assign(product=ds.ETHANOL, median=city["median"] * 0.68)
        city = pd.concat([city, ethanol])
        state = pd.concat([state, state.assign(product=ds.ETHANOL, median=state["median"] * 0.72)])
        obs = q2_data(stations=6, weeks=40).assign(municipality="SAO PAULO")
        obs = pd.concat([obs, q2_data(stations=6, weeks=40, seed=2).assign(municipality="SANTOS", station_id=lambda d: d["station_id"] + 100)])
        meta = dict(uf="SP", code_sha="abc", protocol_commit="def", seed=protocol.SEED, bootstrap_reps=0,
                    data_hashes=dict(combined="1" * 64, observations="2" * 64, city="3" * 64, state="4" * 64),
                    window=[protocol.STUDY_START, protocol.STUDY_END], observations=len(obs), weeks_with_data=40)
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptive(meta, ds.analyze(obs, city, state, q3.sizes(city)), Path(tmp))
            text = (Path(tmp) / "descritivo.md").read_text(encoding="utf-8")
        self.assertIn("Etanol compensa (até 70% do preço da gasolina) em **100,0%**", text)
        self.assertIn("| Litoral |", text)
        self.assertIn("num tanque de 50 L", text)

    def test_refuses_the_final_test(self):
        obs = q2_data(stations=2, weeks=2).assign(municipality="A")
        obs.loc[0, "week_start"] = protocol.TEST_START
        with self.assertRaises(protocol.HoldoutViolation):
            ds.station_choice(obs)


class GateTests(unittest.TestCase):
    def test_two_of_three(self):
        self.assertTrue(gate.g1({"q1": {"stable": True}, "q2": {"stable": False}, "q3": {"stable": True}})["passed"])
        result = gate.g1({"q1": {"stable": True}, "q2": {"stable": False}, "q3": {"stable": False}})
        self.assertEqual((result["passed"], result["stable"]), (False, ["q1"]))


if __name__ == "__main__":
    unittest.main()
