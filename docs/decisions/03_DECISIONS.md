# Decisions 03 — Intelligent Alert System Implementation

## Date: 2026-03-19

### D1: Ensemble over single method
**Decision**: Use a 3-component ensemble (percentile rank + linear trend residual + momentum plateau) instead of a single statistical method.
**Rationale**: No single method handles all characteristics of ARS/USD data (step-function, trending, regime changes). The ensemble provides false-positive suppression through AND logic while each component covers a different aspect of "is this a good time to sell?"

### D2: Cold-start with progressive enablement
**Decision**: Progressively enable analysis components as data accumulates, falling back to legacy threshold with <1 day of data.
**Rationale**: Zero-disruption deployment. Existing users with `sell_rate_alert_above` configured see no behavior change on day 1. The system self-upgrades as data matures.

### D3: Regime change detection resets windows
**Decision**: A >5% single-tick jump resets all rolling windows, keeping only post-jump data.
**Rationale**: Pre-devaluation rates would make every post-devaluation rate look "normal" in percentile terms, suppressing valid alerts. Quick adaptation to the new regime is more valuable than maintaining a long history.

### D4: numpy as sole dependency
**Decision**: Only add numpy, no statsmodels/scipy/prophet.
**Rationale**: All three components use basic numpy operations (percentile, polyfit, diff). The Oracle Cloud ARM deployment benefits from minimal dependencies. numpy has excellent ARM64 support.

### D5: AlertSignal as structured model
**Decision**: Replace `list[str]` return type with `list[AlertSignal]` Pydantic models.
**Rationale**: Structured data enables per-channel formatting (Markdown for Telegram, plain text for webhook), makes tests assertable on component values, and carries maturity/urgency metadata for future UI use.

### D6: Hourly aggregation in SQL
**Decision**: Use SQL window functions (`ROW_NUMBER() OVER PARTITION BY hour`) to aggregate to hourly before sending to Python.
**Rationale**: Reduces data transfer from ~4,000 rows (14 days × 96/day) to ~336 rows. Keeps numpy operations fast and memory-light.

### D7: evaluate_alerts backward-compatible signature
**Decision**: Add `db: Database | None = None` parameter, keeping the function callable without DB access.
**Rationale**: Legacy code paths and tests that don't need ensemble evaluation can still call the function. The scheduler was the only caller and now passes `db`.
