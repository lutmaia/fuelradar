# Technical report — Radar de Combustíveis SP

**Version of 2026-10-16.** What the project measured, how, and what it could not show. Every number comes from a code-generated report committed under `reports/`; section 9 says where each one lives. Protocols, ADRs and generated reports are in Portuguese. Versão em português: [relatorio-tecnico.md](../relatorio-tecnico.md).

## 1. Summary

The project organizes the fuel prices surveyed by ANP (Brazil's National Petroleum Agency) in the state of São Paulo (about 800 thousand prices, 174 weeks, Nov/2022 to Oct/2026) and asks: **what do these prices make predictable, and what not?** Methods and criteria were written and committed before each result.

- **Unbranded stations:** in the same municipality and week, regular gasoline at unbranded ("bandeira branca") stations costs **5.59% less** than at branded ones (95% CI −5.96% to −5.21%), stable under every check. It is a price association, not an effect of the brand.
- **Dynamics and diffusion:** "prices rise more than they fall" and "price moves start in the big cities" **did not hold** across subperiods. Per the protocol, gate G1 (2 of 3 stable findings) **did not pass**.
- **Forecasting the value:** a LightGBM was **7.9% worse** than repeating the last value. The published forecast is the simple method.
- **Forecasting the direction** (down, flat, up in 2 weeks): the best model beat the base rate by **16.4%** (Brier skill) on the final test, read once, but had a calibration error of **0.0504**, above the 0.05 limit, and **was not approved**. The gain came from statewide signals; the dollar and producer prices added nothing.
- **Live evaluation:** the same model, recalibrated, records forecasts every week before prices come out. The decision comes with 26 scored weeks, around April 2027. **In progress.**

## 2. Questions

| Id | Question | Type | Status |
|---|---|---|---|
| Q1 | How much less do unbranded stations charge, same municipality, product and week? | association | answered, stable |
| Q2 | How does a station's price change, and do rises differ from falls? | descriptive | answered, not stable |
| Q3 | Do price moves spread across municipalities, and who moves first? | temporal association | answered, not stable |
| Q4 | How much of the change over the next 1 to 4 weeks is predictable, and from what information? | predictive | answered, candidate not approved |
| Q5 | Do forecasts hold up once the actual value arrives? | prospective | in progress |

Out of scope by decision: any inference about fuel quality or adulteration, and any accusation against stations. The full design is in [estudo-de-caso.md](../estudo-de-caso.md).

## 3. Data

- **Source:** ANP's fuel price survey (LPC), weekly files by station, plus a semiannual history received at the start. Full card in [dataset-card.md](dataset-card.md).
- **Coverage:** state of São Paulo, 2022-11-13 to 2026-10-04; **174 weeks with data** out of 204 in the range, 108 municipalities, 4,009 stations and **801,810 current observations**, across six road fuels (LPG out of scope).
- **Gaps:** 19 weeks have no file on ANP's page (the longest, 2025-10-19 to 2025-11-30) and 11 have a defective file, excluded with a recorded reason in `config/excluded_sources.json` (ADR 0006). Nothing is interpolated.
- **Sample:** ANP surveys a sample that changes every week. The median is 8 stations per municipality and week, and 9.7% of combinations have fewer than 3 stations and are treated as weak series.
- **Pipeline:** ingestion with a SHA-256 manifest and untouched raw files (ADR 0001); quality rules, quarantine and source precedence (ADR 0002); PostgreSQL with SQL migrations (ADR 0003); read-only API and dashboard. 8,653 observations (1.1%) carry an extreme-price warning and stay in the medians; 8 are quarantined.
- **External sources** (ADR 0010): US dollar from the Central Bank and ANP producer and distributor prices, each value with the date it became available (`available_at`), so no feature uses future data. Ethanol at the mill and import parity were dropped over licensing.
- **Privacy:** the database keeps CNPJ (company tax ID) and company name; the public package, the reports and the forecast ledger do not.

## 4. Protocol and safeguards

- **Windows fixed in code** (`forecasting/protocol.py`): development up to 2025-06-29; validation 2025-07-06 to 2026-03-29; **final test from 2026-04-05, sealed**. The study (Q1 to Q3) uses only development and validation.
- **Seal:** the test loader requires an explicit parameter and writes a row to `holdout_access` (time, commit, purpose, data hash) before returning data. There is exactly one row, from 2026-10-15 at 12:29 Brasília time.
- **Pre-registration checkable in Git:**

| Stage | Protocol committed | First result committed |
|---|---|---|
| Study Q1 to Q3 | `efeded4`, Oct 13 19:58 ([protocol](../estudo/protocolo.md)) | `4ff5292`, Oct 13 22:43 |
| Consumer descriptives | `06d1051`, Oct 13 23:04 ([definitions](../estudo/descritivo.md)) | `c285350`, Oct 13 23:05 |
| Modelling v2 (Q4) | `b79188e`, Oct 15 12:25 ([protocol](../estudo/protocolo-modelagem.md)) | test read at 12:29; `1d2112d`, 15:28 |
| Calibration and live evaluation (Q5) | `3614baf`, Oct 15 15:29 ([protocol](../estudo/protocolo-ao-vivo.md)) | `65fe8c3`, 15:41 |

  For the descriptives, the one-minute gap shows the commit order but does not prove the run happened after the definitions were committed.
- **Deviations** are logged in each protocol, with the date and whether they came before or after results. The two later ones (row ordering in the study, effect only at the 16th digit; a wording inconsistency in the modelling protocol, no effect on the decision) are declared as such.
- **Uncertainty:** moving-block bootstrap over 4-week blocks, B = 2000, seed 20261013; standard errors clustered by station in Q1; Holm correction on secondary outcomes.
- **Independent checks:** the main results were recomputed in SQL without the project's code and matched (Q1 coefficient, Q2 pairs and medians, the three descriptive measures, margins and dashboard numbers).

## 5. Exploratory study (Q1 to Q3)

Window 2022-11-13 to 2026-03-29: 147 weeks with data and 675,834 observations. Primary outcome always on regular gasoline. Details in the [summary](../../reports/study/resumo.md).

**Q1, unbranded stations.** Regression of log price with municipality × week fixed effects and station-clustered errors: **−5.59%** (CI −5.96% to −5.21%), with 173,992 observations in 13,407 cells. Stable under every check: neighbourhood by postcode prefix (−5.55%), without extreme prices (−5.23%), subperiod A (−5.95%) and B (−5.28%). Other products range from −2.17% (CNG, not significant) to −6.39% (premium gasoline). Limitation: the brand is today's registration, and being unbranded is not random. [Report](../../reports/study/q1.md)

**Q2, dynamics.** Of 130,079 same-station pairs in consecutive weeks, 22.2% change; the median rise is R$ 0.12 and the median fall R$ 0.10. Asymmetry: **R$ 0.020** (CI 0.000 to 0.100), with 0.100 in subperiod A and 0.000 in B: **not stable**. The likely cause is the measure: prices move in R$ 0.10 steps, and the median jumps between them. Changing the measure now would mean choosing after seeing the data. [Report](../../reports/study/q2.md)

**Q3, diffusion.** Moves in the four leaders (São Paulo, Campinas, Guarulhos, Ribeirão Preto) improve the forecast of **38.6%** of 83 followers, against 4.8% in reverse, but **0.0%** in subperiod A: **not stable**. Most municipalities correlate most strongly in the same week as the leaders, which weekly resolution cannot separate. [Report](../../reports/study/q3.md)

**Gate G1:** 1 of 3 stable findings; the protocol required 2. The result was published as is and the modelling scope was reassessed (layer L2 without the Q3 leaders).

**Consumer descriptives** ([report](../../reports/study/descritivo.md)): ethanol paid off (at most 70% of the gasoline price) in **82.6%** of 13,593 municipality-weeks, from 99.4% in 2024 to 32.8% in 2026; the cheapest station is typically **R$ 0.40/L** below the municipal median, about 4 times a typical weekly price change (R$ 0.10); the capital was the cheapest region for regular gasoline (interior and metropolitan area +R$ 0.10, coast +R$ 0.30, in median).

## 6. Forecasting (Q4)

**Weekly median value** ([report](../../reports/forecasting/backtest.md), ADR 0007). Rolling-origin backtest every 4 weeks, 22 evaluated origins and 24,481 forecasts common to all four models, 1 to 4 weeks ahead:

| Model | MAE (R$/L) | Station-weighted MAE | 80% interval coverage |
|---|---|---|---|
| Last value | 0.1064 | **0.0812** | 75.3% |
| 4-week moving average | 0.1316 | 0.1098 | 70.6% |
| Same week last year | 0.4051 | 0.3800 | 73.8% |
| Global LightGBM (candidate) | 0.1120 | 0.0876 | 76.6% |

The rule required a 5% improvement in weighted MAE; the candidate was **7.9% worse** and worse in several groups. **Published: last value.** This stage had no formal pre-registration: the 5% minimum gain and no-regression-by-group rule come from the specification written at the start of the project ([architecture.md](../architecture.md), section 14.8), but the bias and coverage limits were chosen during that stage, and Git does not show whether before or after the backtest. Neither of those two limits decided the outcome: the candidate failed the specification's criteria.

**Direction of change (modelling v2)** ([protocol](../estudo/protocolo-modelagem.md), [validation](../../reports/modelv2/validacao.md), [final](../../reports/modelv2/final.md)). Target: whether the median h weeks ahead falls, stays or rises, with a R$ 0.05 threshold. Primary outcome: Brier skill score (BSS) at h = 2 against the base rate by product and month. Three information layers, each with a multinomial logistic model and a LightGBM with fixed parameters:

| Layer | Information | Validation BSS (best model) | Test BSS (best model) |
|---|---|---|---|
| L1 | the series itself | +0.080 (logistic) | +0.062 (LightGBM) |
| L2 | + statewide signals | **+0.145 (LightGBM, candidate)** | **+0.164** (CI +0.104 to +0.208) |
| L3 | + dollar and producer prices | +0.143 (LightGBM) | +0.152 (LightGBM) |

- **Test decision** (26 origins, 21,387 points; 25 origins at h = 2): (b) gain confirmed ✅, (c) no product, size or horizon below −0.05 ✅ (worst group: h = 1, +0.105), (e) reproducible ✅, **(d) calibration error 0.0504 > 0.05 ❌. Not approved.**
- **Ablation (Holm):** own series +0.031 (p 1.0); **statewide signals +0.133 (p < 0.001)**; dollar and producers −0.012 (p 1.0).
- **Reference check:** against a product-only base rate, BSS was +0.172, so the gain does not come from a noisy monthly reference.
- **Value (secondary):** the L2 LightGBM had MAE 0.1019 against 0.1088 for last value (+6.3%), not significant (Diebold–Mariano, Holm p 1.0).
- **Distribution shift:** the test had 39% falls against 16% in validation.

## 7. Live evaluation (Q5), in progress

Pre-registered in [protocolo-ao-vivo.md](../estudo/protocolo-ao-vivo.md), committed before any forecast.

- **What changes:** calibration only. One temperature parameter per horizon, fitted once on the modelling v2 validation: T = 1.32 (h = 1), 1.39 (h = 2) and 2.33 (h = 4). On that same validation, the calibration error at h = 2 went from 0.050 to 0.036; the number is optimistic because it is the fitting sample. The modelling v2 final test is not used.
- **Immutable ledger:** every week, before ANP publishes prices, the probabilities for each eligible series go to `reports/ledger/<origin>.csv`, with its SHA-256 in the manifest, and the GitHub commit serves as the timestamp. First origin: 2026-10-04, 837 forecasts (279 series × 3 horizons).
- **One-time decision** at 26 matured origins at h = 2: the probabilities become official if BSS at h = 2 has a CI lower bound above zero, calibration error is at most 0.05 and no group is below −0.05. Otherwise they leave the product and the result is published. Until then they are labelled experimental.
- **Dates:** degradation alert from 13 matured origins (around Jan/2027); decision around Apr/2027.
- **Status on 2026-10-16:** 0 matured origins.

## 8. Engineering and operations

- **API:** read-only FastAPI, with data date, sample and coverage in every response ([guide](../api.md), in Portuguese); **dashboard:** Streamlit, 12 pages, reading only from the API ([guide](../dashboard.md)).
- **Gross retail margin:** station price minus the average distributor price, by state, municipality and station, in neutral wording; it is not profit, and a station's real cost is not public.
- **Tests:** 378, with synthetic data of known answer and, for database, API and integration, against a real PostgreSQL in Docker. Screens were checked in a browser.
- **Zero-cost operations** (ADR 0011, [manual](operations.md)): tests on every push; a daily GitHub Actions routine that, when there is a new week, restores an encrypted state into a temporary PostgreSQL, refreshes everything and commits the ledger and package. Injected failure and recovery were demonstrated on GitHub. The public demo reads a package with no CNPJ or company name (ADR 0009).
- **Reproduction:** `scripts/reproduce.py` regenerates every report in a temporary folder and compares: 14 of 16 checks identical and 2 warnings (same numbers, different observation hash, probably because the study ran on a database with different internal station ids). The final test is checked from the points of the single read, with no new access. **From scratch on another machine** (macOS arm64, clean clone, everything downloaded from ANP, without the project's state): the same 801,810 observations, the Q1 to Q3 study identical including the data hash, and the dataset card equal in all counts (it differs only by files received by hand at the start, which are not on ANP's page). LightGBM numbers change slightly between Windows x86-64 and Mac arm64 with the same data and version (validation L2 +0.140 vs +0.145; backtest +11.0% worse vs +7.9%), without changing any decision: they only reproduce exactly on the same architecture.

## 9. Where each number lives

| Topic | Generated report | Numbers in JSON |
|---|---|---|
| Data coverage and quality | [dataset-card.md](dataset-card.md) | `reports/dataset/ficha.json` |
| Q1 to Q3 and gate G1 | [summary](../../reports/study/resumo.md) | `reports/study/resultados.json` |
| Consumer descriptives | [descriptives](../../reports/study/descritivo.md) | `reports/study/descritivo.json` |
| Value forecast | [backtest](../../reports/forecasting/backtest.md) | `reports/forecasting/backtest.json` |
| Modelling v2: validation and test | [validation](../../reports/modelv2/validacao.md), [final](../../reports/modelv2/final.md) | `reports/modelv2/validacao.json`, `final.json` |
| Calibration | — | `reports/modelv2/calibracao.json` |
| Live evaluation | *Desempenho ao vivo* page | `reports/ledger/placar.json` |

Each report records the data hash, the code commit and, where there is one, the protocol commit.

## 10. Limitations

- **ANP's sample:** it does not cover every station, changes every week and has publication gaps; a small municipality's median moves with the sample.
- **Association, not causation:** no analysis identifies a causal effect; brand, region and price reflect location, size, freight, taxes and competition, which the project does not separate.
- **Current brand:** no history of brand changes.
- **A small final test:** 25 origins at h = 2, with a class mix different from validation; the live result is the missing proof.
- **Fixed parameters:** no hyperparameter search, on purpose; other settings might do better.
- **Approximate external sources:** `available_at` follows each source's published rule; producer prices are regional (Southeast) and have no ethanol; distributor prices arrive 5 to 9 weeks late.
- **The final test has been seen:** any new modelling that uses it needs a new protocol and must say so.
