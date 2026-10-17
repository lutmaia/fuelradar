# Model card — weekly median price forecast

A short, honest account of what the forecast does and does not do. The product shows two things: the **value forecast** (published model: last value) and, labelled **experimental**, the **probabilities of a fall, no change or a rise**, which are under live evaluation. Decisions in ADR 0007 (in Portuguese); reproducible numeric report in [reports/forecasting/backtest.md](../../reports/forecasting/backtest.md); overview in the [technical report](technical-report.md). Versão em português: [model-card.md](../model-card.md).

## What is forecast

The **weekly median** retail price of a product, in a São Paulo municipality or statewide, 1 to 4 weeks ahead, with an 80% interval. It is not the price at one station, nor on one day.

## Model in use

**Last observed value** (baseline): the forecast median for the coming weeks is the median of the most recent week. The interval comes from this method's errors in a test on past data.

A machine learning model (**global LightGBM**) was trained and evaluated in a rolling-origin backtest. **It was not approved**: it was 7.9% worse in weighted error and more than 5% worse in several groups. So the baseline remains published.

## How it was evaluated

- 24,481 forecasts evaluated, at 22 cut-off dates 4 weeks apart, using only data before each cut-off.
- The four models (three baselines and the candidate) are compared on the same points.
- Mean error of the published model: R$ 0.106 per litre (R$ 0.043 at 1 week; R$ 0.115 at 4 weeks, weighted by stations).
- The 80% interval contains the actual value in 75% of cases.

## When there is no forecast

Series with fewer than 52 weeks of history, data in fewer than 80% of recent weeks, fewer than 3 stations per week (municipalities), recent low coverage or no data in the latest week. In those cases the dashboard shows the reason, never a number. Today 279 of 600 series have a forecast.

## Limitations

- It does not consider oil, exchange rate, taxes or pricing policy; sudden changes are not forecast.
- Actual price changes tend to come in R$ 0.10 steps, which limits precision.
- The backtest covers Nov/2022 to Oct/2026, and weeks missing at the source appear as gaps.
- Result of one fixed configuration; there was no hyperparameter search.

## Modelling v2 (Milestone 10): class of change, not approved

Pre-registration in [protocolo-modelagem.md](../estudo/protocolo-modelagem.md); numbers in [reports/modelv2/final.md](../../reports/modelv2/final.md).

- **Question:** will the median **fall, stay or rise** (R$ 0.05 threshold) in 1, 2 and 4 weeks? Primary outcome: Brier skill at 2 weeks against the base rate by product and month.
- **Layers:** L1 (the series itself), L2 (+ statewide signals: statewide change and share of municipalities that rose or fell), L3 (+ dollar and producer prices, only what had been published by then). Multinomial logistic and LightGBM in each layer, fixed parameters.
- **Candidate chosen on validation** (Jul/2025 to Mar/2026): **L2 with LightGBM**, BSS +0.145 (95% CI +0.081 to +0.195).
- **Final test** (Apr to Oct/2026, 25 origins, read once): BSS **+0.164** (CI +0.104 to +0.208), no regression in any product, size or horizon, reproducible. **Calibration error 0.0504**, above the pre-registered limit of 0.05: **not approved**. The product did not change and the published value forecast is still "last value".
- **What each layer added** (test, Holm): the series itself, nothing significant (+0.031); statewide signals, **+0.133** (p < 0.001); dollar and producers, nothing (−0.012).
- **Value (secondary):** the L2 LightGBM had 6.3% lower MAE than "last value", but not significant after correction (Holm p 1.0).
- **Limitations:** probabilities slightly miscalibrated (addressed in the live evaluation below, under a new protocol); the test period had more falls (39%) than validation (16%); producer prices are for the Southeast region and have no ethanol.

## Live probabilities (experimental, under evaluation)

Pre-registration in [protocolo-ao-vivo.md](../estudo/protocolo-ao-vivo.md), committed before any forecast; operations and dates in [operations.md](operations.md).

- **Model:** Milestone 10's candidate (L2 with LightGBM), with no change other than calibration. Retrained every week on all pairs whose target is already known.
- **Calibration:** temperature scaling, one parameter per horizon, fitted once on Milestone 10's validation: T = 1.32 (1 week), 1.39 (2 weeks) and 2.33 (4 weeks). T > 1 makes the model less confident, and the most likely class never changes. On that same validation, the calibration error at 2 weeks went from 0.050 to 0.036; the number is optimistic because it is the fitting sample ([calibracao.json](../../reports/modelv2/calibracao.json)). Milestone 10's final test was not used.
- **Output:** for each eligible series, the probability that the median falls, stays or rises by at least R$ 0.05 in 1, 2 and 4 weeks, next to the reference base rate. First origin: 2026-10-04, 837 forecasts (279 series × 3 horizons).
- **Immutable ledger:** forecasts go to `reports/ledger/` before ANP publishes prices, with each file's SHA-256 in the manifest; the routine stops if any file changes.
- **Scoreboard:** when the target week is published, each forecast is scored; the dashboard (*Desempenho ao vivo*) and the API (`/models/scoreboard`) show Brier skill against the base rate with a 95% CI, calibration error and scored weeks.
- **Decision, once:** with 26 origins scored at 2 weeks (around April 2027), the probabilities become official if the gain has a CI lower bound above zero, calibration error is at most 0.05 and no product, size or horizon is below −0.05. Otherwise they leave the product, and the result is published either way.
- **Degradation alert:** from 13 scored origins (around January 2027), if the 2-week gain over the 13 most recent falls below zero, the dashboard warns.
- **Status on 2026-10-16:** no forecast scored yet.
- **Limitations:** the temperature was fitted on a validation period with 16% falls, while Milestone 10's test had 39%; calibration may not hold. ANP publication gaps delay scoring. The published **value** forecast is still "last value"; these probabilities do not replace it.

## Unusual changes

Weeks in which the median fell outside the expected 99% range of weekly change, by at least R$ 0.15 and with at least 3 stations. It is a **statistical signal**, not evidence of wrongdoing by stations or of irregular prices.
