"""Alert evaluation engine.

Evaluates rates using an ensemble of percentile rank, linear trend residual,
and momentum plateau detection. Falls back to simple threshold for cold-start.
"""

import logging
from datetime import datetime

import numpy as np

from bluetrak.alerts.analysis import (
    momentum_plateau,
    percentile_rank,
    preprocess_rates,
    trend_residual,
)
from bluetrak.config import Settings
from bluetrak.db import Database
from bluetrak.models import AlertSignal, AlertUrgency, DataMaturity, Rate

logger = logging.getLogger(__name__)

# Maturity thresholds based on distinct rate changes
_MATURITY_THRESHOLDS = [
    (50, DataMaturity.FULL),  # ~14+ days of real changes
    (20, DataMaturity.STABLE),  # ~7-14 days
    (10, DataMaturity.DEVELOPING),  # ~3-7 days
    (4, DataMaturity.PRELIMINARY),  # ~1-3 days
]


def _determine_maturity(distinct_changes: int) -> DataMaturity:
    """Map count of distinct rate changes to a data maturity level."""
    for threshold, maturity in _MATURITY_THRESHOLDS:
        if distinct_changes >= threshold:
            return maturity
    return DataMaturity.COLD


def _to_arrays(
    hourly_rates: list[tuple[str, float]],
) -> tuple[np.ndarray, np.ndarray]:
    """Convert DB results to numpy arrays of (timestamps_as_epoch, rates)."""
    if not hourly_rates:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    timestamps = np.array(
        [datetime.fromisoformat(ts).timestamp() for ts, _ in hourly_rates],
        dtype=np.float64,
    )
    rates = np.array([r for _, r in hourly_rates], dtype=np.float64)
    return timestamps, rates


def _evaluate_source(
    rate: Rate,
    db: Database,
    settings: Settings,
) -> AlertSignal:
    """Run the ensemble analysis for a single source."""
    distinct_changes = db.count_distinct_changes(rate.source)
    maturity = _determine_maturity(distinct_changes)

    signal = AlertSignal(
        source=rate.source,
        sell_rate=rate.sell_rate,
        maturity=maturity,
    )

    # Cold start: fall back to simple threshold
    if maturity == DataMaturity.COLD:
        if settings.sell_rate_alert_above > 0 and rate.sell_rate >= settings.sell_rate_alert_above:
            signal.should_alert = True
        return signal

    # --- Component A: Percentile Rank ---
    percentile_data = db.get_hourly_rates(rate.source, settings.alert_percentile_window_days)
    p_timestamps, p_rates = _to_arrays(percentile_data)
    p_timestamps, p_rates, _ = preprocess_rates(p_timestamps, p_rates)

    if len(p_rates) > 0:
        signal.percentile_rank = percentile_rank(rate.sell_rate, p_rates)
        signal.window_high = float(np.max(p_rates))

    percentile_ok = (
        signal.percentile_rank is not None
        and signal.percentile_rank >= settings.alert_percentile_threshold
    )

    # Preliminary maturity: percentile alone can trigger
    if maturity == DataMaturity.PRELIMINARY:
        signal.should_alert = percentile_ok
        return signal

    # --- Component B: Trend Residual ---
    trend_data = db.get_hourly_rates(rate.source, settings.alert_trend_window_days)
    t_timestamps, t_rates = _to_arrays(trend_data)
    t_timestamps, t_rates, regime_changed = preprocess_rates(t_timestamps, t_rates)

    if regime_changed:
        logger.warning("Regime change detected for %s — windows reset", rate.source)

    if len(t_timestamps) >= 3:
        current_ts = rate.fetched_at.timestamp()
        residual, sigma = trend_residual(t_timestamps, t_rates, current_ts, rate.sell_rate)
        signal.trend_residual = residual
        signal.trend_residual_sigma = sigma
        signal.trend_predicted = rate.sell_rate - residual

    trend_ok = signal.trend_residual_sigma is not None and signal.trend_residual_sigma > 1.0

    # Developing maturity: percentile + trend
    if maturity == DataMaturity.DEVELOPING:
        signal.should_alert = percentile_ok and trend_ok
        return signal

    # --- Component C: Momentum Plateau (stable/full maturity) ---
    if len(p_rates) >= 3:
        signal.momentum_fading = momentum_plateau(p_rates)

    # Full ensemble: A AND B required, C modulates urgency
    signal.should_alert = percentile_ok and trend_ok

    if signal.should_alert and signal.momentum_fading:
        signal.urgency = AlertUrgency.HIGH

    return signal


def evaluate_alerts(
    rates: list[Rate],
    settings: Settings,
    db: Database | None = None,
) -> list[AlertSignal]:
    """Evaluate rates using ensemble analysis. Returns list of AlertSignal results.

    If db is None, falls back to legacy threshold-only behavior.
    """
    signals: list[AlertSignal] = []

    for rate in rates:
        if db is not None:
            signal = _evaluate_source(rate, db, settings)
        else:
            # Legacy fallback when no DB access (shouldn't happen in practice)
            signal = AlertSignal(source=rate.source, sell_rate=rate.sell_rate)
            if settings.sell_rate_alert_above > 0 and rate.sell_rate >= settings.sell_rate_alert_above:
                signal.should_alert = True

        if signal.should_alert:
            logger.info("Alert triggered for %s: %s", rate.source, signal.format_message())

        signals.append(signal)

    return signals
