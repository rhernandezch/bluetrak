"""Alert evaluation engine.

Evaluates rates using an ensemble of percentile rank, linear trend residual,
and momentum plateau detection. Falls back to simple threshold for cold-start.
"""

import logging
from datetime import datetime, timedelta

import numpy as np

from bluetrak.alerts.analysis import (
    crossed_recent_drop_threshold,
    momentum_plateau,
    percentile_rank,
    preprocess_rates,
    short_window_move,
    trend_residual,
)
from bluetrak.config import Settings
from bluetrak.db import Database
from bluetrak.models import AlertKind, AlertSignal, AlertUrgency, DataMaturity, Rate

logger = logging.getLogger(__name__)

# Maturity thresholds based on distinct rate changes
_MATURITY_THRESHOLDS = [
    (50, DataMaturity.FULL),  # ~14+ days of real changes
    (20, DataMaturity.STABLE),  # ~7-14 days
    (10, DataMaturity.DEVELOPING),  # ~3-7 days
    (4, DataMaturity.PRELIMINARY),  # ~1-3 days
]
_ARQ_SOURCE = "arq"
_ARQ_FAST_PERCENTILE_THRESHOLD = 80.0


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


def _append_current_rate(
    timestamps: np.ndarray,
    rates: np.ndarray,
    rate: Rate,
) -> tuple[np.ndarray, np.ndarray]:
    """Ensure the current fetch is represented in a raw recent-rate window."""
    current_ts = rate.fetched_at.timestamp()
    if len(timestamps) > 0 and timestamps[-1] == current_ts:
        return timestamps, rates

    return (
        np.append(timestamps, current_ts),
        np.append(rates, rate.sell_rate),
    )


def _significant_move(change: float, pct: float, settings: Settings) -> bool:
    """Return True when both absolute and percentage thresholds are met."""
    return (
        change >= settings.alert_arq_reactive_min_move_ars
        and pct >= settings.alert_arq_reactive_min_move_pct
    )


def _apply_arq_reactive_signals(
    signal: AlertSignal,
    rate: Rate,
    db: Database,
    settings: Settings,
) -> None:
    """Add faster ARQ-specific spike and drop alerts using raw recent samples."""
    if rate.source != _ARQ_SOURCE or not settings.alert_arq_reactive_enabled:
        return

    since = rate.fetched_at - timedelta(hours=settings.alert_arq_reactive_window_hours)
    recent_data = db.get_sell_rates_since(rate.source, since)
    r_timestamps, r_rates = _to_arrays(recent_data)
    r_timestamps, r_rates = _append_current_rate(r_timestamps, r_rates, rate)
    r_timestamps, r_rates, _ = preprocess_rates(r_timestamps, r_rates)

    if len(r_rates) < 2:
        return

    signal.recent_window_high = float(np.max(r_rates))
    signal.recent_window_low = float(np.min(r_rates))

    change, pct = short_window_move(r_rates, settings.alert_arq_reactive_lookback)
    signal.recent_change = change
    signal.recent_change_pct = pct

    drop_crossed, drop_abs, drop_pct, recent_high = crossed_recent_drop_threshold(
        r_rates,
        lookback=max(settings.alert_arq_reactive_lookback * 2, 3),
        min_drop_abs=settings.alert_arq_reactive_min_move_ars,
        min_drop_pct=settings.alert_arq_reactive_min_move_pct,
    )
    if drop_crossed:
        signal.kind = AlertKind.DROP_WARNING
        signal.should_alert = True
        signal.urgency = AlertUrgency.HIGH
        signal.reactive_move = True
        signal.price_dropping = True
        signal.recent_change = -drop_abs
        signal.recent_change_pct = -drop_pct
        signal.recent_window_high = recent_high
        return

    recent_percentile = percentile_rank(rate.sell_rate, r_rates)
    if (
        _significant_move(change, pct, settings)
        and recent_percentile >= _ARQ_FAST_PERCENTILE_THRESHOLD
    ):
        signal.should_alert = True
        signal.urgency = AlertUrgency.HIGH
        signal.reactive_move = True


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
        _apply_arq_reactive_signals(signal, rate, db, settings)
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
        _apply_arq_reactive_signals(signal, rate, db, settings)
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
        _apply_arq_reactive_signals(signal, rate, db, settings)
        return signal

    # --- Component C: Momentum Plateau (stable/full maturity) ---
    if len(p_rates) >= 3:
        signal.momentum_fading = momentum_plateau(p_rates)

    # Full ensemble: A AND B required, C modulates urgency
    signal.should_alert = percentile_ok and trend_ok

    if signal.should_alert and signal.momentum_fading:
        signal.urgency = AlertUrgency.HIGH

    _apply_arq_reactive_signals(signal, rate, db, settings)

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
            threshold = settings.sell_rate_alert_above
            if threshold > 0 and rate.sell_rate >= threshold:
                signal.should_alert = True

        if signal.should_alert:
            logger.info("Alert triggered for %s: %s", rate.source, signal.format_message())

        signals.append(signal)

    return signals
