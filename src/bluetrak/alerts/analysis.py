"""Pure analysis functions for intelligent alert detection.

All functions operate on numpy arrays — no database or model dependencies.
This makes them trivially testable with synthetic data.
"""

import numpy as np
from numpy.typing import NDArray


def preprocess_rates(
    timestamps: NDArray[np.float64],
    rates: NDArray[np.float64],
    regime_change_pct: float = 5.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], bool]:
    """Deduplicate consecutive identical readings and detect regime changes.

    Returns:
        (clean_timestamps, clean_rates, regime_changed)
        If a regime change is detected, only post-change data is returned.
    """
    if len(rates) < 2:
        return timestamps, rates, False

    # Deduplicate: keep only readings where the rate actually changed,
    # plus the very first reading
    mask = np.ones(len(rates), dtype=bool)
    mask[1:] = rates[1:] != rates[:-1]
    clean_ts = timestamps[mask]
    clean_rates = rates[mask]

    # Regime change: check if any single change exceeds threshold
    regime_changed = False
    if len(clean_rates) >= 2:
        pct_changes = np.abs(np.diff(clean_rates) / clean_rates[:-1]) * 100
        regime_indices = np.where(pct_changes > regime_change_pct)[0]

        if len(regime_indices) > 0:
            # Keep only data after the most recent regime change
            last_regime = regime_indices[-1] + 1  # +1 because diff shifts index
            clean_ts = clean_ts[last_regime:]
            clean_rates = clean_rates[last_regime:]
            regime_changed = True

    return clean_ts, clean_rates, regime_changed


def percentile_rank(current_rate: float, historical_rates: NDArray[np.float64]) -> float:
    """Compute the percentile rank of the current rate within historical data.

    Returns a value 0-100 indicating what percentage of historical rates
    are below the current rate.
    """
    if len(historical_rates) == 0:
        return 0.0

    below = np.sum(historical_rates < current_rate)
    return float(below / len(historical_rates) * 100)


def trend_residual(
    timestamps: NDArray[np.float64],
    rates: NDArray[np.float64],
    current_ts: float,
    current_rate: float,
) -> tuple[float, float]:
    """Fit a linear trend and compute the residual of the current rate.

    Returns:
        (residual, residual_sigma) where:
        - residual = current_rate - predicted_rate (positive = above trend)
        - residual_sigma = residual expressed in standard deviations of the fit residuals
    """
    if len(timestamps) < 3:
        return 0.0, 0.0

    # Normalize timestamps to days for numerical stability
    t_min = timestamps[0]
    t_norm = (timestamps - t_min) / 86400.0  # seconds to days
    current_t_norm = (current_ts - t_min) / 86400.0

    coeffs = np.polyfit(t_norm, rates, 1)
    predicted = np.polyval(coeffs, t_norm)
    residuals = rates - predicted

    std = float(np.std(residuals))
    if std == 0:
        return 0.0, 0.0

    # Cap sigma to avoid nonsensical values when std is near-zero
    # (e.g., from nearly-perfect linear fits with floating-point noise)
    max_sigma = 100.0

    current_predicted = float(np.polyval(coeffs, current_t_norm))
    residual = current_rate - current_predicted
    sigma = min(residual / std, max_sigma) if residual > 0 else max(residual / std, -max_sigma)

    return residual, sigma


def momentum_plateau(
    rates: NDArray[np.float64],
    lookback: int = 6,
) -> bool:
    """Detect if upward momentum is fading.

    Looks at the last `lookback` rate changes (on deduplicated data).
    Returns True if the most recent change(s) are zero or negative
    while earlier changes were positive — indicating a plateau or reversal.
    """
    if len(rates) < 3:
        return False

    changes = np.diff(rates)
    recent = changes[-lookback:] if len(changes) > lookback else changes

    if len(recent) < 2:
        return False

    # Split into earlier and latest portions
    split = max(1, len(recent) // 2)
    earlier = recent[:split]
    latest = recent[split:]

    # Momentum is fading if earlier changes were mostly positive
    # but latest changes are flat or negative
    earlier_positive = float(np.mean(earlier)) > 0
    latest_flat_or_down = float(np.mean(latest)) <= 0

    return earlier_positive and latest_flat_or_down


def short_window_move(
    rates: NDArray[np.float64],
    lookback: int = 4,
) -> tuple[float, float]:
    """Return absolute and percent change over the latest short window."""
    if len(rates) < 2:
        return 0.0, 0.0

    start_idx = max(0, len(rates) - lookback - 1)
    start = float(rates[start_idx])
    end = float(rates[-1])
    change = end - start
    pct = change / start * 100 if start != 0 else 0.0

    return change, pct


def crossed_recent_drop_threshold(
    rates: NDArray[np.float64],
    lookback: int = 8,
    min_drop_abs: float = 3.0,
    min_drop_pct: float = 0.2,
) -> tuple[bool, float, float, float]:
    """Detect the first meaningful drop from a recent high.

    Returns:
        (crossed, drop_abs, drop_pct, recent_high)
        drop_abs is positive when the current rate is below the recent high.
    """
    if len(rates) < 3:
        return False, 0.0, 0.0, 0.0

    window_start = max(0, len(rates) - lookback - 1)
    window = rates[window_start:]
    current = float(window[-1])
    previous = float(window[-2])
    latest_change = current - previous

    high_before_current = float(np.max(window[:-1]))
    current_drop = high_before_current - current
    current_drop_pct = current_drop / high_before_current * 100 if high_before_current else 0.0

    high_before_previous = float(np.max(window[:-2])) if len(window) > 2 else previous
    previous_drop = high_before_previous - previous
    previous_drop_pct = previous_drop / high_before_previous * 100 if high_before_previous else 0.0

    current_meets = current_drop >= min_drop_abs and current_drop_pct >= min_drop_pct
    previous_met = previous_drop >= min_drop_abs and previous_drop_pct >= min_drop_pct
    crossed = latest_change < 0 and current_meets and not previous_met

    return crossed, current_drop, current_drop_pct, high_before_current
