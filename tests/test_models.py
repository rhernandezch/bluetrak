"""Tests for domain models."""

from datetime import datetime

from bluetrak.models import Rate


def test_rate_str() -> None:
    rate = Rate(
        source="test_source",
        buy_rate=1400.50,
        sell_rate=1450.75,
        fetched_at=datetime(2026, 3, 19, 12, 0, 0),
    )
    assert "test_source" in str(rate)
    assert "1400.50" in str(rate)
    assert "1450.75" in str(rate)


def test_rate_with_raw_response() -> None:
    rate = Rate(
        source="test",
        buy_rate=1400,
        sell_rate=1450,
        fetched_at=datetime.now(),
        raw_response='{"key": "value"}',
    )
    assert rate.raw_response == '{"key": "value"}'
