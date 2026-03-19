# Decisions 02: Intelligent Alert System

**Date:** 2026-03-19

## Decision: Ensemble of 3 lightweight statistical methods

**Context:** Replace the static threshold alert with a system that detects local peaks — "this rate is historically high and momentum is fading, likely a good time to sell."

**Decision:** Combine percentile rank (7-day window) + linear trend residual (14-day window) + momentum plateau detection. Alert when percentile AND trend agree; momentum modulates urgency.

**Rationale:**
- ARS/USD rates are step-functions with structural depreciation and regime changes — this rules out smooth-curve methods (ARIMA, Holt-Winters) and data-hungry ML approaches (Prophet, XGBoost)
- Percentile rank directly answers "is this rate unusually high?" without distributional assumptions
- Linear trend captures the depreciation slope, so the residual isolates the "above-trend" signal
- Momentum plateau prevents alerting mid-rally
- Only dependency: numpy. No heavy ML stack.
- Graceful cold-start: percentile works from day 3, full ensemble from day 14

**Rejected alternatives:**
- **ARIMA/SARIMA**: stationarity assumption violated by devaluations; overkill
- **Prophet**: heavy deps (cmdstanpy), needs months of data, poor ARM support
- **XGBoost/LightGBM**: overfits with limited data, black box, needs months of training
- **Simple threshold**: no awareness of trend or history
- **Moving average crossover**: lags behind peaks too much

## Decision: Per-source analysis

**Rationale:** Each source has different update frequencies and spreads. A composite rate would not correspond to any real transaction the user could execute.

## Decision: Automatic cold-start upgrade

**Rationale:** System starts with threshold fallback (day 0), adds percentile (day 1-3), adds trend (day 7+), reaches full ensemble at day 14+. No manual intervention needed.
