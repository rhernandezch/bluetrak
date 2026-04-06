"""Tests for domain models."""

from datetime import datetime

from bluetrak.models import Rate, format_rate_change_message


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


def test_rate_default_values() -> None:
    rate = Rate(
        source="test",
        buy_rate=1400,
        sell_rate=1450,
        fetched_at=datetime.now(),
    )
    assert rate.source == "test"
    assert rate.buy_rate == 1400


def test_format_rate_change_message_with_previous() -> None:
    previous = Rate(source="wu", buy_rate=1460, sell_rate=1460, fetched_at=datetime(2026, 4, 1))
    current = Rate(source="wu", buy_rate=1470, sell_rate=1470, fetched_at=datetime(2026, 4, 2))
    msg = format_rate_change_message("wu", current, previous)
    assert "1470.00" in msg
    assert "+10.00" in msg
    assert "🟢 ▲" in msg


def test_format_rate_change_message_decrease() -> None:
    previous = Rate(source="wu", buy_rate=1470, sell_rate=1470, fetched_at=datetime(2026, 4, 1))
    current = Rate(source="wu", buy_rate=1460, sell_rate=1460, fetched_at=datetime(2026, 4, 2))
    msg = format_rate_change_message("wu", current, previous)
    assert "-10.00" in msg
    assert "🔴 ▼" in msg


def test_format_rate_change_message_first_rate() -> None:
    current = Rate(source="wu", buy_rate=1470, sell_rate=1470, fetched_at=datetime(2026, 4, 2))
    msg = format_rate_change_message("wu", current, None)
    assert "1470.00" in msg
    assert "First rate recorded" in msg
