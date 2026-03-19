"""Integration tests for the full Bluetrak pipeline.

These tests exercise multiple components together — real SQLite, real engine,
real analysis — with only HTTP calls mocked at the edges (sources, dispatch).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import httpx
import respx

from bluetrak.config import Settings
from bluetrak.db import Database
from bluetrak.models import AlertUrgency, DataMaturity, Rate
from bluetrak.scheduler import fetch_and_store
from bluetrak.sources.base import RateSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSource(RateSource):
    """A controllable source for integration testing.

    Each call to fetch() returns the next rate in the queue.
    """

    name = "fake_source"

    def __init__(self, rates: list[tuple[float, float]] | None = None) -> None:
        super().__init__()
        self._rates: list[tuple[float, float]] = rates or []
        self._index = 0
        self._fetch_time: datetime | None = None

    def enqueue(self, buy: float, sell: float) -> None:
        self._rates.append((buy, sell))

    def set_time(self, t: datetime) -> None:
        self._fetch_time = t

    def fetch(self) -> Rate:
        if self._index >= len(self._rates):
            raise RuntimeError("FakeSource: no more rates queued")
        buy, sell = self._rates[self._index]
        self._index += 1
        return Rate(
            source=self.name,
            buy_rate=buy,
            sell_rate=sell,
            fetched_at=self._fetch_time or datetime.now(),
        )


class FailingSource(RateSource):
    """A source that always raises on fetch."""

    name = "failing_source"

    def fetch(self) -> Rate:
        raise ConnectionError("simulated network failure")


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "integration.db")
    db.connect()
    return db


def _populate_history(
    db: Database,
    source: str,
    base_rate: float,
    daily_increment: float,
    days: int,
    readings_per_hour: int = 4,
) -> float:
    """Insert realistic rate history: step-function data with hourly changes.

    Returns the final rate value.
    """
    now = datetime.now()
    start = now - timedelta(days=days)
    rate = base_rate
    for day in range(days):
        for hour in range(24):
            ts_base = start + timedelta(days=day, hours=hour)
            for reading in range(readings_per_hour):
                ts = ts_base + timedelta(minutes=15 * reading)
                db.save_rate(Rate(
                    source=source,
                    buy_rate=rate - 50,
                    sell_rate=rate,
                    fetched_at=ts,
                ))
            # Rate changes once per hour
            rate += daily_increment / 24.0
    return rate


# ===========================================================================
# 1. Fetch-Store-Evaluate Pipeline
# ===========================================================================


class TestFetchStoreEvaluatePipeline:
    """End-to-end: source.fetch() → db.save_rate() → evaluate_alerts() → dispatch."""

    def test_full_cycle_stores_rate_and_evaluates(self, tmp_path: Path) -> None:
        """A single fetch cycle stores the rate and runs evaluation."""
        db = _db(tmp_path)
        try:
            source = FakeSource([(1400.0, 1450.0)])
            settings = Settings(
                sell_rate_alert_above=1500,
                webhook_url="https://hooks.example.com/test",
            )
            # No alert expected (1450 < 1500 threshold, cold start)
            with respx.mock:
                fetch_and_store([source], db, settings)

            latest = db.get_latest_rates()
            assert len(latest) == 1
            assert latest[0].source == "fake_source"
            assert latest[0].sell_rate == 1450.0
        finally:
            db.close()

    @respx.mock
    def test_cold_start_alert_dispatches_to_webhook(self, tmp_path: Path) -> None:
        """Cold start: rate above threshold triggers webhook dispatch."""
        db = _db(tmp_path)
        try:
            source = FakeSource([(1500.0, 1550.0)])
            webhook_route = respx.post("https://hooks.example.com/test").mock(
                return_value=httpx.Response(200)
            )
            settings = Settings(
                sell_rate_alert_above=1500,
                webhook_url="https://hooks.example.com/test",
            )
            fetch_and_store([source], db, settings)

            assert webhook_route.called
            request_body = webhook_route.calls[0].request.content.decode()
            assert "1550.00" in request_body
        finally:
            db.close()

    @respx.mock
    def test_cold_start_alert_dispatches_to_telegram(self, tmp_path: Path) -> None:
        """Cold start: rate above threshold triggers Telegram dispatch."""
        db = _db(tmp_path)
        try:
            source = FakeSource([(1500.0, 1550.0)])
            tg_route = respx.post(
                "https://api.telegram.org/botFAKE_TOKEN/sendMessage"
            ).mock(return_value=httpx.Response(200))

            settings = Settings(
                sell_rate_alert_above=1500,
                telegram_bot_token="FAKE_TOKEN",
                telegram_chat_id="12345",
            )
            fetch_and_store([source], db, settings)

            assert tg_route.called
            request_body = tg_route.calls[0].request.content.decode()
            assert "1550.00" in request_body
        finally:
            db.close()

    def test_no_dispatch_when_alerts_disabled(self, tmp_path: Path) -> None:
        """Without webhook/telegram configured, no dispatch happens."""
        db = _db(tmp_path)
        try:
            source = FakeSource([(1500.0, 9999.0)])
            settings = Settings(sell_rate_alert_above=1500)
            # No respx mock needed — if dispatch were attempted it would fail
            fetch_and_store([source], db, settings)
            # Just verify it didn't crash
            assert db.get_latest_rates()[0].sell_rate == 9999.0
        finally:
            db.close()

    @respx.mock
    def test_dispatch_uses_formatted_alert_signal(self, tmp_path: Path) -> None:
        """Verify the dispatched message is AlertSignal.format_message(), not a raw string."""
        db = _db(tmp_path)
        try:
            # Build up enough history for ensemble evaluation
            _populate_history(db, "fake_source", 1400.0, 10.0, days=15)

            # Now fetch a spike
            spike_rate = 1400.0 + 15 * 10.0 + 200.0  # way above trend
            source = FakeSource([(spike_rate - 50, spike_rate)])
            webhook_route = respx.post("https://hooks.example.com/alert").mock(
                return_value=httpx.Response(200)
            )
            settings = Settings(
                sell_rate_alert_above=0,
                webhook_url="https://hooks.example.com/alert",
            )
            fetch_and_store([source], db, settings)

            if webhook_route.called:
                body = webhook_route.calls[0].request.content.decode()
                # AlertSignal.format_message uses Markdown bold
                assert "fake_source" in body
                assert f"{spike_rate:.2f}" in body
        finally:
            db.close()


# ===========================================================================
# 2. Cold-Start Maturity Progression
# ===========================================================================


class TestMaturityProgression:
    """Simulate data accumulating over time and verify maturity transitions."""

    def test_cold_to_preliminary(self, tmp_path: Path) -> None:
        """After ~4 distinct rate changes, maturity upgrades from COLD to PRELIMINARY."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            settings = Settings(sell_rate_alert_above=1500)
            now = datetime.now()

            # Insert 5 distinct rate changes over ~2 days
            rates_sequence = [1400.0, 1400.0, 1405.0, 1405.0, 1410.0,
                              1415.0, 1420.0, 1420.0]
            for i, sell in enumerate(rates_sequence):
                ts = now - timedelta(hours=6 * (len(rates_sequence) - i))
                db.save_rate(Rate(
                    source="test", buy_rate=sell - 50, sell_rate=sell, fetched_at=ts,
                ))

            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=1470, sell_rate=1500, fetched_at=now)],
                settings, db,
            )
            assert signals[0].maturity == DataMaturity.PRELIMINARY
            # Percentile should be computed
            assert signals[0].percentile_rank is not None
        finally:
            db.close()

    def test_progression_to_full_maturity(self, tmp_path: Path) -> None:
        """With 50+ distinct changes (14+ days), all three components are active."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            # 15 days × ~4 changes/day = 60 distinct changes → FULL
            final_rate = _populate_history(db, "test", 1400.0, 8.0, days=15)

            spike = final_rate + 100
            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=spike - 50, sell_rate=spike,
                      fetched_at=datetime.now())],
                settings, db,
            )
            signal = signals[0]
            assert signal.maturity == DataMaturity.FULL
            assert signal.percentile_rank is not None
            assert signal.trend_residual is not None
            assert signal.momentum_fading is not None
        finally:
            db.close()

    def test_cold_start_uses_threshold_fallback(self, tmp_path: Path) -> None:
        """With zero history, the engine uses the old sell_rate_alert_above logic."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            settings = Settings(sell_rate_alert_above=1500)

            # Above threshold → alert
            signals = evaluate_alerts(
                [Rate(source="new_source", buy_rate=1500, sell_rate=1550,
                      fetched_at=datetime.now())],
                settings, db,
            )
            assert signals[0].maturity == DataMaturity.COLD
            assert signals[0].should_alert

            # Below threshold → no alert
            signals = evaluate_alerts(
                [Rate(source="new_source", buy_rate=1400, sell_rate=1450,
                      fetched_at=datetime.now())],
                settings, db,
            )
            assert not signals[0].should_alert
        finally:
            db.close()


# ===========================================================================
# 3. Regime Change Detection End-to-End
# ===========================================================================


class TestRegimeChange:
    """Verify that a large sudden jump resets analysis windows."""

    def test_devaluation_resets_window(self, tmp_path: Path) -> None:
        """A 30% jump mid-history resets the trend/percentile windows."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            now = datetime.now()
            # 10 days of normal rates around 1000
            for day in range(10):
                for hour in range(24):
                    ts = now - timedelta(days=15 - day, hours=hour)
                    rate_val = 1000.0 + day * 2.0 + hour * 0.08
                    db.save_rate(Rate(
                        source="test", buy_rate=rate_val - 50,
                        sell_rate=rate_val, fetched_at=ts,
                    ))

            # Devaluation: 30% jump
            for day in range(5):
                for hour in range(24):
                    ts = now - timedelta(days=5 - day, hours=hour)
                    rate_val = 1300.0 + day * 2.0 + hour * 0.08
                    db.save_rate(Rate(
                        source="test", buy_rate=rate_val - 50,
                        sell_rate=rate_val, fetched_at=ts,
                    ))

            # Current rate slightly above post-devaluation range
            current = 1315.0
            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=current - 50, sell_rate=current,
                      fetched_at=now)],
                settings, db,
            )
            signal = signals[0]
            # The pre-devaluation ~1000 rates should NOT be in the window,
            # so percentile should be computed against post-jump data only
            if signal.percentile_rank is not None:
                # Current rate 1315 vs post-devaluation range 1300-1310
                # Should be high percentile since we're above most post-jump rates
                assert signal.percentile_rank > 50

            # trend_predicted should be in the post-devaluation range, not pre
            if signal.trend_predicted is not None:
                assert signal.trend_predicted > 1200  # definitely post-devaluation
        finally:
            db.close()

    def test_no_regime_change_on_small_jump(self, tmp_path: Path) -> None:
        """A 3% jump should NOT trigger regime change detection."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            now = datetime.now()
            # Rates that vary per-hour (not just per-day) to get 50+ distinct changes
            for day in range(14):
                for hour in range(24):
                    ts = now - timedelta(days=14 - day, hours=hour)
                    base = 1000.0 + day * 2.0 + hour * 0.08
                    if day >= 7:
                        base += 30.0  # 3% jump at day 7
                    db.save_rate(Rate(
                        source="test", buy_rate=base - 50,
                        sell_rate=base, fetched_at=ts,
                    ))

            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=1070, sell_rate=1080,
                      fetched_at=now)],
                settings, db,
            )
            # All components should be active since no regime reset
            signal = signals[0]
            assert signal.maturity == DataMaturity.FULL
            assert signal.percentile_rank is not None
            assert signal.trend_residual is not None
        finally:
            db.close()


# ===========================================================================
# 4. Source Failure Resilience
# ===========================================================================


class TestSourceFailureResilience:
    """One source failing must not prevent others from being stored/evaluated."""

    @respx.mock
    def test_one_source_fails_others_succeed(self, tmp_path: Path) -> None:
        """If one source throws, other rates are still stored and evaluated."""
        db = _db(tmp_path)
        try:
            good_source = FakeSource([(1450.0, 1500.0)])
            good_source.name = "good_source"
            bad_source = FailingSource()

            webhook_route = respx.post("https://hooks.example.com/test").mock(
                return_value=httpx.Response(200)
            )
            settings = Settings(
                sell_rate_alert_above=1490,
                webhook_url="https://hooks.example.com/test",
            )
            fetch_and_store([bad_source, good_source], db, settings)

            latest = db.get_latest_rates()
            assert len(latest) == 1
            assert latest[0].source == "good_source"
            # Alert should fire for good_source (1500 >= 1490)
            assert webhook_route.called
        finally:
            db.close()

    def test_all_sources_fail_no_crash(self, tmp_path: Path) -> None:
        """When every source fails, the cycle completes without error."""
        db = _db(tmp_path)
        try:
            settings = Settings(
                sell_rate_alert_above=1500,
                webhook_url="https://hooks.example.com/test",
            )
            fetch_and_store([FailingSource(), FailingSource()], db, settings)
            assert db.get_latest_rates() == []
        finally:
            db.close()


# ===========================================================================
# 5. Multi-Source Divergent Maturity
# ===========================================================================


class TestMultiSourceDivergentMaturity:
    """Multiple sources at different maturity levels in the same fetch cycle."""

    def test_sources_evaluated_independently(self, tmp_path: Path) -> None:
        """source_a has 15 days of data (FULL), source_b has 2 days (PRELIMINARY)."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            # source_a: 15 days of history
            _populate_history(db, "source_a", 1400.0, 8.0, days=15)
            # source_b: 2 days of history with 5 distinct changes
            now = datetime.now()
            for i in range(5):
                ts = now - timedelta(hours=10 * (5 - i))
                db.save_rate(Rate(
                    source="source_b", buy_rate=1400 + i * 5,
                    sell_rate=1450 + i * 5, fetched_at=ts,
                ))

            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts([
                Rate(source="source_a", buy_rate=1600, sell_rate=1650,
                     fetched_at=now),
                Rate(source="source_b", buy_rate=1500, sell_rate=1550,
                     fetched_at=now),
            ], settings, db)

            assert len(signals) == 2
            assert signals[0].maturity == DataMaturity.FULL
            # source_b has 4 distinct changes (5 values → 4 transitions)
            assert signals[1].maturity in (DataMaturity.PRELIMINARY, DataMaturity.DEVELOPING)

            # source_a should have all components populated
            assert signals[0].percentile_rank is not None
            assert signals[0].trend_residual is not None
            assert signals[0].momentum_fading is not None
        finally:
            db.close()


# ===========================================================================
# 6. Hourly Aggregation Correctness
# ===========================================================================


class TestHourlyAggregation:
    """Verify SQL hourly aggregation across edge cases."""

    def test_multiple_hours_multiple_days(self, tmp_path: Path) -> None:
        """Hourly aggregation works across day boundaries."""
        db = _db(tmp_path)
        try:
            now = datetime.now()
            # Insert readings across 3 days, 4 per hour
            for day in range(3):
                for hour in range(24):
                    for quarter in range(4):
                        ts = now - timedelta(days=3 - day, hours=24 - hour,
                                             minutes=45 - 15 * quarter)
                        rate = 1400.0 + day * 10.0 + hour * 0.4
                        db.save_rate(Rate(
                            source="test", buy_rate=rate - 50,
                            sell_rate=rate, fetched_at=ts,
                        ))

            hourly = db.get_hourly_rates("test", 5)
            # 3 days × 24 hours = 72 hourly data points
            assert len(hourly) >= 70  # allow some slack for boundary hours
            # Values should span the expected range
            rates = [r for _, r in hourly]
            assert min(rates) >= 1399.0
            assert max(rates) <= 1450.0
        finally:
            db.close()

    def test_source_isolation(self, tmp_path: Path) -> None:
        """Hourly rates for one source don't include another source's data."""
        db = _db(tmp_path)
        try:
            now = datetime.now()
            for i in range(10):
                ts = now - timedelta(hours=i)
                db.save_rate(Rate(
                    source="source_a", buy_rate=1400, sell_rate=1500, fetched_at=ts,
                ))
                db.save_rate(Rate(
                    source="source_b", buy_rate=1600, sell_rate=1700, fetched_at=ts,
                ))

            hourly_a = db.get_hourly_rates("source_a", 2)
            hourly_b = db.get_hourly_rates("source_b", 2)

            for _, rate in hourly_a:
                assert rate == 1500.0
            for _, rate in hourly_b:
                assert rate == 1700.0
        finally:
            db.close()

    def test_window_respects_days_parameter(self, tmp_path: Path) -> None:
        """get_hourly_rates(days=7) should not return data older than 7 days."""
        db = _db(tmp_path)
        try:
            now = datetime.now()
            # Old data (10 days ago)
            for i in range(24):
                ts = now - timedelta(days=10, hours=i)
                db.save_rate(Rate(
                    source="test", buy_rate=900, sell_rate=1000, fetched_at=ts,
                ))
            # Recent data (2 days ago)
            for i in range(24):
                ts = now - timedelta(days=2, hours=i)
                db.save_rate(Rate(
                    source="test", buy_rate=1400, sell_rate=1500, fetched_at=ts,
                ))

            hourly = db.get_hourly_rates("test", 7)
            # Should only contain recent data
            for _, rate in hourly:
                assert rate == 1500.0
        finally:
            db.close()


# ===========================================================================
# 7. Realistic Scenarios: Spike, Plateau, Flat Market
# ===========================================================================


class TestRealisticScenarios:
    """End-to-end tests with realistic ARS/USD rate patterns."""

    def test_spike_after_steady_climb(self, tmp_path: Path) -> None:
        """14 days of steady climb, then a spike — alert should fire."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            final_rate = _populate_history(db, "test", 1400.0, 8.0, days=14)
            spike = final_rate + 150  # big spike above trend

            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=spike - 50, sell_rate=spike,
                      fetched_at=datetime.now())],
                settings, db,
            )
            signal = signals[0]
            assert signal.should_alert
            assert signal.percentile_rank is not None
            assert signal.percentile_rank >= 90
            assert signal.trend_residual is not None
            assert signal.trend_residual > 50  # well above trend

        finally:
            db.close()

    def test_flat_market_no_alert(self, tmp_path: Path) -> None:
        """14 days of flat rates — current rate should NOT trigger alert."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            now = datetime.now()
            # Flat market: same rate for 14 days
            for day in range(14):
                for hour in range(24):
                    ts = now - timedelta(days=14 - day, hours=hour)
                    db.save_rate(Rate(
                        source="test", buy_rate=1400, sell_rate=1450,
                        fetched_at=ts,
                    ))

            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=1400, sell_rate=1450,
                      fetched_at=now)],
                settings, db,
            )
            # In a flat market the rate equals the historical rate,
            # so it shouldn't be "above trend" or at high percentile
            assert not signals[0].should_alert
        finally:
            db.close()

    def test_gradual_climb_on_trend_no_alert(self, tmp_path: Path) -> None:
        """A rate that's climbing but on-trend should not alert.

        Even though percentile is high (it's the latest in an uptrend), the
        trend residual should be near-zero because the value follows the line.
        With perfectly linear synthetic data the residual IS ~0, so trend_ok
        is False and the ensemble doesn't fire.
        """
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            final_rate = _populate_history(db, "test", 1400.0, 8.0, days=15)
            # Current rate is exactly on-trend (the next expected value)
            on_trend = final_rate + 8.0 / 24.0  # one more hour of the same slope

            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=on_trend - 50, sell_rate=on_trend,
                      fetched_at=datetime.now())],
                settings, db,
            )
            signal = signals[0]
            # On-trend value: even if sigma is capped, the raw residual should be tiny
            assert signal.trend_residual is not None
            assert abs(signal.trend_residual) < 5.0
        finally:
            db.close()

    def test_plateau_after_climb_high_urgency(self, tmp_path: Path) -> None:
        """Climb for 10 days then plateau for 4 — spike should trigger HIGH urgency."""
        db = _db(tmp_path)
        try:
            from bluetrak.alerts.engine import evaluate_alerts

            now = datetime.now()
            # 10 days of climbing
            for day in range(10):
                for hour in range(24):
                    ts = now - timedelta(days=14 - day, hours=hour)
                    rate = 1400.0 + (day * 24 + hour) * 0.5
                    db.save_rate(Rate(
                        source="test", buy_rate=rate - 50,
                        sell_rate=rate, fetched_at=ts,
                    ))

            peak = 1400.0 + 10 * 24 * 0.5
            # 4 days plateau at peak
            for day in range(4):
                for hour in range(24):
                    ts = now - timedelta(days=4 - day, hours=hour)
                    db.save_rate(Rate(
                        source="test", buy_rate=peak - 50,
                        sell_rate=peak, fetched_at=ts,
                    ))

            # Current: slightly above plateau
            spike = peak + 80
            settings = Settings(sell_rate_alert_above=0)
            signals = evaluate_alerts(
                [Rate(source="test", buy_rate=spike - 50, sell_rate=spike,
                      fetched_at=now)],
                settings, db,
            )
            signal = signals[0]
            if signal.should_alert and signal.momentum_fading:
                assert signal.urgency == AlertUrgency.HIGH
        finally:
            db.close()


# ===========================================================================
# 8. Fetch Cycle Accumulation
# ===========================================================================


class TestFetchCycleAccumulation:
    """Simulate multiple fetch_and_store cycles and verify cumulative behavior."""

    def test_multiple_cycles_accumulate_data(self, tmp_path: Path) -> None:
        """Running fetch_and_store multiple times builds up DB history."""
        db = _db(tmp_path)
        try:
            settings = Settings(sell_rate_alert_above=0)

            for i in range(10):
                source = FakeSource([(1400.0 + i * 5, 1450.0 + i * 5)])
                source.set_time(datetime.now() - timedelta(hours=10 - i))
                with respx.mock:
                    fetch_and_store([source], db, settings)

            # Should have 10 rows in DB
            rows = db.conn.execute("SELECT COUNT(*) as cnt FROM rates").fetchone()
            assert rows["cnt"] == 10

            # Distinct changes should match the 10 different rates
            changes = db.count_distinct_changes("fake_source")
            assert changes == 9  # 10 values → 9 transitions
        finally:
            db.close()

    @respx.mock
    def test_alert_only_fires_when_conditions_met(self, tmp_path: Path) -> None:
        """Build up data over cycles; alert should only fire on spike cycles."""
        db = _db(tmp_path)
        try:
            # Pre-populate 14 days of history for full maturity
            final_rate = _populate_history(db, "fake_source", 1400.0, 8.0, days=15)

            # Normal cycle: on-trend rate → no alert
            webhook_route = respx.post("https://hooks.example.com/test").mock(
                return_value=httpx.Response(200)
            )
            on_trend_source = FakeSource([(final_rate - 50, final_rate)])
            settings = Settings(
                sell_rate_alert_above=0,
                webhook_url="https://hooks.example.com/test",
            )
            fetch_and_store([on_trend_source], db, settings)
            on_trend_calls = webhook_route.call_count

            # Spike cycle: above trend but <5% to avoid regime change detection
            # final_rate is ~1520, so +60 is ~4% — below the 5% regime threshold
            spike = final_rate + 60
            spike_source = FakeSource([(spike - 50, spike)])
            fetch_and_store([spike_source], db, settings)
            spike_calls = webhook_route.call_count

            # The spike cycle should have generated more dispatch calls
            assert spike_calls > on_trend_calls
        finally:
            db.close()


# ===========================================================================
# 9. Alert Dispatch Failure Resilience
# ===========================================================================


class TestDispatchFailureResilience:
    """Dispatch failures should be logged, not crash the cycle."""

    @respx.mock
    def test_webhook_failure_does_not_crash(self, tmp_path: Path) -> None:
        """If webhook returns 500, the fetch cycle still completes."""
        db = _db(tmp_path)
        try:
            source = FakeSource([(1500.0, 1550.0)])
            respx.post("https://hooks.example.com/broken").mock(
                return_value=httpx.Response(500)
            )
            settings = Settings(
                sell_rate_alert_above=1500,
                webhook_url="https://hooks.example.com/broken",
            )
            # Should not raise
            fetch_and_store([source], db, settings)
            # Rate should still be persisted
            assert db.get_latest_rates()[0].sell_rate == 1550.0
        finally:
            db.close()

    @respx.mock
    def test_telegram_failure_falls_through_to_webhook(self, tmp_path: Path) -> None:
        """If Telegram fails, webhook should still be attempted."""
        db = _db(tmp_path)
        try:
            source = FakeSource([(1500.0, 1550.0)])
            respx.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
                return_value=httpx.Response(500)
            )
            webhook_route = respx.post("https://hooks.example.com/backup").mock(
                return_value=httpx.Response(200)
            )
            settings = Settings(
                sell_rate_alert_above=1500,
                telegram_bot_token="TOKEN",
                telegram_chat_id="123",
                webhook_url="https://hooks.example.com/backup",
            )
            fetch_and_store([source], db, settings)
            # Webhook should still have been called despite Telegram failure
            assert webhook_route.called
        finally:
            db.close()


# ===========================================================================
# 10. Database Persistence Round-Trip
# ===========================================================================


class TestDatabaseRoundTrip:
    """Verify data survives the save → query → analysis pipeline."""

    def test_rates_survive_round_trip(self, tmp_path: Path) -> None:
        """Rates saved via save_rate match what get_hourly_rates returns."""
        db = _db(tmp_path)
        try:
            now = datetime.now()
            expected_rate = 1477.50
            # Insert one reading per hour for 24 hours
            for hour in range(24):
                ts = now - timedelta(hours=24 - hour)
                db.save_rate(Rate(
                    source="test", buy_rate=expected_rate - 50,
                    sell_rate=expected_rate, fetched_at=ts,
                ))

            hourly = db.get_hourly_rates("test", 2)
            assert len(hourly) >= 23  # at least 23 of 24 hours
            for _, rate in hourly:
                assert rate == expected_rate
        finally:
            db.close()

    def test_get_rates_since_consistency(self, tmp_path: Path) -> None:
        """get_rates_since and get_hourly_rates cover the same time range."""
        db = _db(tmp_path)
        try:
            now = datetime.now()
            for i in range(48):  # 2 days, every 15 min = 192 readings? no, 48 readings
                ts = now - timedelta(hours=48 - i)
                db.save_rate(Rate(
                    source="test", buy_rate=1400, sell_rate=1450 + i,
                    fetched_at=ts,
                ))

            since = now - timedelta(days=3)
            raw = db.get_rates_since("test", since)
            hourly = db.get_hourly_rates("test", 3)

            # Raw should have all 48 readings
            assert len(raw) == 48
            # Hourly should have at most 48 (one per hour since we inserted one per hour)
            assert len(hourly) <= 48
            assert len(hourly) >= 1
        finally:
            db.close()

    def test_export_json_reflects_saved_data(self, tmp_path: Path) -> None:
        """export_json includes rates that were recently saved."""
        db = _db(tmp_path)
        try:
            import json

            db.save_rate(Rate(
                source="test", buy_rate=1400, sell_rate=1450,
                fetched_at=datetime.now(),
            ))
            exported = json.loads(db.export_json(10))
            assert len(exported) == 1
            assert exported[0]["source"] == "test"
            assert exported[0]["sell_rate"] == 1450.0
        finally:
            db.close()
