"""Tests for the alert evaluation engine and analysis functions."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from bluetrak.alerts.analysis import (
    momentum_plateau,
    percentile_rank,
    preprocess_rates,
    trend_residual,
)
from bluetrak.alerts.engine import _determine_maturity, evaluate_alerts
from bluetrak.config import Settings
from bluetrak.db import Database
from bluetrak.models import AlertLevel, AlertSignal, AlertUrgency, DataMaturity, Rate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rate(source: str, sell: float, fetched_at: datetime | None = None) -> Rate:
    return Rate(
        source=source,
        buy_rate=sell - 50,
        sell_rate=sell,
        fetched_at=fetched_at or datetime.now(),
    )


def _populate_db(
    db: Database,
    source: str,
    rates: list[float],
    start: datetime | None = None,
    interval_minutes: int = 15,
) -> None:
    """Insert synthetic rate history into the database."""
    start = start or (datetime.now() - timedelta(minutes=interval_minutes * len(rates)))
    for i, sell in enumerate(rates):
        ts = start + timedelta(minutes=interval_minutes * i)
        db.save_rate(
            Rate(source=source, buy_rate=sell - 50, sell_rate=sell, fetched_at=ts)
        )


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.connect()
    return db


# ===========================================================================
# Analysis function tests
# ===========================================================================


class TestPreprocessRates:
    def test_deduplicates_consecutive_identical(self) -> None:
        ts = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        rates = np.array([100.0, 100.0, 101.0, 101.0, 102.0])
        clean_ts, clean_rates, regime = preprocess_rates(ts, rates)
        assert list(clean_rates) == [100.0, 101.0, 102.0]
        assert not regime

    def test_detects_regime_change(self) -> None:
        ts = np.array([1.0, 2.0, 3.0, 4.0])
        rates = np.array([100.0, 101.0, 140.0, 141.0])  # 38% jump
        clean_ts, clean_rates, regime = preprocess_rates(ts, rates)
        assert regime
        # Should only contain post-regime data
        assert list(clean_rates) == [140.0, 141.0]

    def test_empty_input(self) -> None:
        ts = np.array([], dtype=np.float64)
        rates = np.array([], dtype=np.float64)
        clean_ts, clean_rates, regime = preprocess_rates(ts, rates)
        assert len(clean_rates) == 0
        assert not regime

    def test_single_reading(self) -> None:
        ts = np.array([1.0])
        rates = np.array([100.0])
        clean_ts, clean_rates, regime = preprocess_rates(ts, rates)
        assert list(clean_rates) == [100.0]
        assert not regime


class TestPercentileRank:
    def test_highest_value(self) -> None:
        history = np.array([100.0, 110.0, 120.0, 130.0, 140.0])
        assert percentile_rank(150.0, history) == 100.0

    def test_lowest_value(self) -> None:
        history = np.array([100.0, 110.0, 120.0, 130.0, 140.0])
        assert percentile_rank(90.0, history) == 0.0

    def test_median_value(self) -> None:
        history = np.array([100.0, 110.0, 120.0, 130.0, 140.0])
        rank = percentile_rank(120.0, history)
        assert rank == 40.0  # 2 out of 5 are below

    def test_empty_history(self) -> None:
        assert percentile_rank(100.0, np.array([])) == 0.0


class TestTrendResidual:
    def test_on_trend_value(self) -> None:
        """A value exactly on the linear trend should have ~0 residual."""
        ts = np.array([0.0, 86400.0, 172800.0])  # 0, 1, 2 days in seconds
        rates = np.array([100.0, 110.0, 120.0])
        residual, sigma = trend_residual(ts, rates, 259200.0, 130.0)
        assert abs(residual) < 0.01

    def test_above_trend_value(self) -> None:
        """A value above the linear trend should have positive residual."""
        ts = np.array([0.0, 86400.0, 172800.0, 259200.0])
        rates = np.array([100.0, 110.0, 120.0, 130.0])
        residual, sigma = trend_residual(ts, rates, 345600.0, 160.0)  # +20 above trend
        assert residual > 10.0
        assert sigma > 0

    def test_insufficient_data(self) -> None:
        ts = np.array([0.0, 1.0])
        rates = np.array([100.0, 101.0])
        residual, sigma = trend_residual(ts, rates, 2.0, 102.0)
        assert residual == 0.0
        assert sigma == 0.0


class TestMomentumPlateau:
    def test_fading_momentum(self) -> None:
        """Rates climbed then flattened — using deduplicated data."""
        # After dedup, this represents: 3 upward moves then 2 flat/down moves
        rates = np.array([100.0, 105.0, 110.0, 115.0, 115.5, 115.0, 114.5])
        assert momentum_plateau(rates) is True

    def test_still_climbing(self) -> None:
        """Rates still going up — no plateau."""
        rates = np.array([100.0, 105.0, 110.0, 115.0, 120.0, 125.0])
        assert momentum_plateau(rates) is False

    def test_declining(self) -> None:
        """Rates going down — technically fading from prior up."""
        rates = np.array([100.0, 110.0, 120.0, 118.0, 115.0, 113.0])
        assert momentum_plateau(rates) is True

    def test_too_few_points(self) -> None:
        rates = np.array([100.0, 105.0])
        assert momentum_plateau(rates) is False


# ===========================================================================
# Data maturity tests
# ===========================================================================


class TestDataMaturity:
    def test_cold(self) -> None:
        assert _determine_maturity(0) == DataMaturity.COLD
        assert _determine_maturity(3) == DataMaturity.COLD

    def test_preliminary(self) -> None:
        assert _determine_maturity(4) == DataMaturity.PRELIMINARY
        assert _determine_maturity(9) == DataMaturity.PRELIMINARY

    def test_developing(self) -> None:
        assert _determine_maturity(10) == DataMaturity.DEVELOPING
        assert _determine_maturity(19) == DataMaturity.DEVELOPING

    def test_stable(self) -> None:
        assert _determine_maturity(20) == DataMaturity.STABLE
        assert _determine_maturity(49) == DataMaturity.STABLE

    def test_full(self) -> None:
        assert _determine_maturity(50) == DataMaturity.FULL
        assert _determine_maturity(200) == DataMaturity.FULL


# ===========================================================================
# Engine integration tests (with real SQLite)
# ===========================================================================


class TestEvaluateAlertsColdStart:
    """Tests for threshold-based fallback when data is insufficient."""

    def test_no_alerts_when_threshold_zero(self, tmp_path: Path) -> None:
        settings = Settings(sell_rate_alert_above=0)
        db = _db(tmp_path)
        try:
            signals = evaluate_alerts([_rate("test", 9999)], settings, db)
            assert len(signals) == 1
            assert not signals[0].should_alert
        finally:
            db.close()

    def test_cold_alert_above_threshold(self, tmp_path: Path) -> None:
        settings = Settings(sell_rate_alert_above=1500)
        db = _db(tmp_path)
        try:
            signals = evaluate_alerts([_rate("test", 1510)], settings, db)
            assert len(signals) == 1
            assert signals[0].should_alert
            assert signals[0].maturity == DataMaturity.COLD
        finally:
            db.close()

    def test_cold_no_alert_below_threshold(self, tmp_path: Path) -> None:
        settings = Settings(sell_rate_alert_above=1500)
        db = _db(tmp_path)
        try:
            signals = evaluate_alerts([_rate("test", 1490)], settings, db)
            assert not signals[0].should_alert
        finally:
            db.close()


class TestEvaluateAlertsLegacy:
    """Tests for legacy mode (no db parameter)."""

    def test_legacy_threshold_alert(self) -> None:
        settings = Settings(sell_rate_alert_above=1500)
        signals = evaluate_alerts([_rate("test", 1510)], settings)
        assert len(signals) == 1
        assert signals[0].should_alert

    def test_legacy_no_alert(self) -> None:
        settings = Settings(sell_rate_alert_above=1500)
        signals = evaluate_alerts([_rate("test", 1490)], settings)
        assert not signals[0].should_alert


class TestEvaluateAlertsEnsemble:
    """Tests with sufficient data for ensemble evaluation."""

    def _setup_steady_climb(self, db: Database, source: str = "test") -> None:
        """Populate DB with 14 days of steady climbing rates (~4 per day change)."""
        now = datetime.now()
        start = now - timedelta(days=14)
        rates: list[float] = []
        # Base rate 1400, climbing ~2 ARS per hour
        for hour in range(14 * 24):
            rate = 1400.0 + hour * 2.0
            # Each rate repeated 4 times (15-min intervals)
            rates.extend([rate] * 4)
        _populate_db(db, source, rates, start=start)

    def _setup_spike_at_peak(self, db: Database, source: str = "test") -> None:
        """Populate with climb then plateau — current rate at historical peak."""
        now = datetime.now()
        start = now - timedelta(days=14)
        rates: list[float] = []
        # Climb for 10 days
        for hour in range(10 * 24):
            rate = 1400.0 + hour * 2.0
            rates.extend([rate] * 4)
        # Plateau for 4 days at the peak
        peak = 1400.0 + 10 * 24 * 2.0
        for _hour in range(4 * 24):
            rates.extend([peak] * 4)
        _populate_db(db, source, rates, start=start)

    def test_steady_climb_current_on_trend(self, tmp_path: Path) -> None:
        """During a steady climb, the current (on-trend) rate should not alert."""
        db = _db(tmp_path)
        try:
            self._setup_steady_climb(db)
            # Current rate is right on the trend
            current = 1400.0 + 14 * 24 * 2.0
            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [_rate("test", current)], settings, db
            )
            # On-trend value should have low residual sigma, so no alert
            assert len(signals) == 1
            signal = signals[0]
            assert signal.maturity == DataMaturity.FULL
            assert signal.percentile_rank is not None
        finally:
            db.close()

    def test_spike_above_trend_triggers(self, tmp_path: Path) -> None:
        """A rate significantly above trend AND high percentile should alert."""
        db = _db(tmp_path)
        try:
            self._setup_steady_climb(db)
            # Current rate is way above the trend line
            trend_expected = 1400.0 + 14 * 24 * 2.0
            spike = trend_expected + 200  # +200 ARS above trend
            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [_rate("test", spike)], settings, db
            )
            signal = signals[0]
            assert signal.percentile_rank is not None
            assert signal.percentile_rank >= 90
            assert signal.trend_residual is not None
            assert signal.trend_residual > 0
            assert signal.should_alert
        finally:
            db.close()

    def test_plateau_has_high_urgency(self, tmp_path: Path) -> None:
        """Rate at peak with fading momentum should have HIGH urgency."""
        db = _db(tmp_path)
        try:
            self._setup_spike_at_peak(db)
            peak = 1400.0 + 10 * 24 * 2.0
            spike = peak + 100  # Slightly above the plateau
            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [_rate("test", spike)], settings, db
            )
            signal = signals[0]
            if signal.should_alert and signal.momentum_fading:
                assert signal.urgency == AlertUrgency.HIGH
        finally:
            db.close()

    def test_multiple_sources_independent(self, tmp_path: Path) -> None:
        """Each source is evaluated independently."""
        db = _db(tmp_path)
        try:
            self._setup_steady_climb(db, source="source_a")
            # source_b has no data (cold start)
            settings = Settings(sell_rate_alert_above=1500)
            trend_expected = 1400.0 + 14 * 24 * 2.0
            rates = [
                _rate("source_a", trend_expected + 200),  # Should trigger (above trend)
                _rate("source_b", 1510),  # Should trigger (cold, above threshold)
            ]
            signals = evaluate_alerts(rates, settings, db)
            assert len(signals) == 2
            assert signals[0].maturity == DataMaturity.FULL
            assert signals[1].maturity == DataMaturity.COLD
            assert signals[1].should_alert  # cold threshold
        finally:
            db.close()


# ===========================================================================
# AlertSignal model tests
# ===========================================================================


class TestAlertSignal:
    def test_format_message_basic(self) -> None:
        signal = AlertSignal(
            source="dolarapp",
            sell_rate=1485.20,
            should_alert=True,
            percentile_rank=94.0,
            window_high=1491.00,
            trend_residual=22.0,
            trend_predicted=1463.20,
            momentum_fading=True,
            urgency=AlertUrgency.HIGH,
        )
        msg = signal.format_message()
        assert "dolarapp" in msg
        assert "1485.20" in msg
        assert "94th percentile" in msg
        assert "+22.00" in msg
        assert "ARS above" in msg
        assert "Momentum" in msg
        assert "sell" in msg.lower()

    def test_format_message_no_components(self) -> None:
        signal = AlertSignal(
            source="test",
            sell_rate=1500.0,
            should_alert=True,
        )
        msg = signal.format_message()
        assert "test" in msg
        assert "1500.00" in msg


# ===========================================================================
# DB method tests
# ===========================================================================


class TestDatabaseAnalysisMethods:
    def test_get_hourly_rates(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        try:
            now = datetime.now()
            # Insert 4 readings in the same hour
            for i in range(4):
                ts = now - timedelta(minutes=15 * (3 - i))
                db.save_rate(Rate(
                    source="test", buy_rate=100.0, sell_rate=150.0 + i,
                    fetched_at=ts,
                ))
            hourly = db.get_hourly_rates("test", 1)
            # Should get at least 1 reading (the last per hour)
            assert len(hourly) >= 1
            # The rate should be the latest in that hour
            assert hourly[-1][1] == 153.0
        finally:
            db.close()

    def test_count_distinct_changes(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        try:
            now = datetime.now()
            rates = [100.0, 100.0, 101.0, 101.0, 102.0, 102.0, 103.0]
            for i, sell in enumerate(rates):
                ts = now + timedelta(minutes=i)
                db.save_rate(Rate(
                    source="test", buy_rate=50.0, sell_rate=sell, fetched_at=ts,
                ))
            changes = db.count_distinct_changes("test")
            assert changes == 3  # 100→101, 101→102, 102→103
        finally:
            db.close()

    def test_count_distinct_changes_no_data(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        try:
            assert db.count_distinct_changes("nonexistent") == 0
        finally:
            db.close()


# ===========================================================================
# Per-source alert level tests
# ===========================================================================


class TestAlertLevelFor:
    def test_default_is_normal(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.alert_level_for("dolarapp") == AlertLevel.NORMAL
        assert settings.alert_level_for("western_union") == AlertLevel.NORMAL
        assert settings.alert_level_for("infodolar_ccl") == AlertLevel.NORMAL

    def test_configured_levels(self) -> None:
        settings = Settings(
            _env_file=None,
            alert_level_dolarapp=AlertLevel.OFF,
            alert_level_western_union=AlertLevel.HIGH,
        )
        assert settings.alert_level_for("dolarapp") == AlertLevel.OFF
        assert settings.alert_level_for("western_union") == AlertLevel.HIGH
        assert settings.alert_level_for("infodolar_ccl") == AlertLevel.NORMAL

    def test_unknown_source_defaults_to_normal(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.alert_level_for("unknown_source") == AlertLevel.NORMAL
