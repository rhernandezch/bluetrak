# Plan 02 — Intelligent Alert System

## Context

The current alert system fires when `sell_rate >= threshold` — a static number the user sets manually. The user wants something smarter: an alert that says *"The rate has not gone above X over the last Y days, current value is Y, and it's likely near a local peak — good time to sell."*

This is fundamentally a **local peak detection** problem on a time series with specific characteristics:
- Step-function behavior (rates hold flat for hours, then jump)
- Structural depreciation trend (ARS loses value over time → the number trends upward)
- Regime changes (government devaluations cause sudden 30-50% jumps)
- Low effective data density (many consecutive identical readings)
- 3 independent sources, tracked per-source

## Recommendation: Ensemble of 3 Simple Methods

Combine three lightweight signals. Alert when the first two agree; the third modulates urgency.

### Component A — Percentile Rank (primary signal)
- Rank the current sell_rate against a 7-day rolling window of hourly-aggregated rates
- Alert when ≥ 90th percentile
- Implementation: `numpy.percentile`

### Component B — Linear Trend Residual (trend filter)
- Fit `rate = a·time + b` over the last 14 days, compute `residual = current - predicted`
- Alert when residual > 1.0 × residual_std_dev
- Implementation: `numpy.polyfit`

### Component C — Momentum Plateau (timing filter)
- Look at last 4-6 actual rate changes (after deduplicating flat readings)
- If most recent change was zero or negative while prior changes were positive → momentum fading
- Modulates alert urgency, does not gate alerts

### How they combine
```
Alert fires when: A (percentile ≥ 90th) AND B (residual > 1σ)
Urgency = high when: A AND B AND C (momentum fading)
```

## Cold-Start Strategy

| Period | Strategy |
|---|---|
| Day 0–1 | Existing threshold fallback (`sell_rate_alert_above`) |
| Day 1–3 | Percentile rank only (preliminary) |
| Day 3–7 | Percentile + detrended z-score |
| Day 7–14 | Percentile + linear trend residual |
| Day 14+ | Full ensemble (all 3 components) |

## Data Preprocessing

1. Deduplicate consecutive identical readings
2. Hourly aggregation (last reading per hour)
3. Regime change detection (>5% jump resets windows)

## Dependencies

Only `numpy` is needed beyond what's already installed.

## Files to Modify

| File | Change |
|---|---|
| `src/bluetrak/alerts/analysis.py` | New — pure analysis functions |
| `src/bluetrak/alerts/engine.py` | Replace threshold logic with ensemble |
| `src/bluetrak/db.py` | Add historical query methods |
| `src/bluetrak/config.py` | Add ensemble settings |
| `src/bluetrak/models.py` | Add `AlertSignal` model |
| `src/bluetrak/scheduler.py` | Pass `db` to `evaluate_alerts()` |
| `tests/test_alerts.py` | Comprehensive tests with synthetic data |
