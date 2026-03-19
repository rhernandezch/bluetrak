"""Tests for the alert evaluation engine."""

from datetime import datetime

from bluetrak.alerts.engine import evaluate_alerts
from bluetrak.config import Settings
from bluetrak.models import Rate


def _rate(source: str, sell: float) -> Rate:
    return Rate(source=source, buy_rate=sell - 50, sell_rate=sell, fetched_at=datetime.now())


def test_no_alerts_when_threshold_zero() -> None:
    settings = Settings(sell_rate_alert_above=0)
    alerts = evaluate_alerts([_rate("test", 9999)], settings)
    assert alerts == []


def test_alert_when_above_threshold() -> None:
    settings = Settings(sell_rate_alert_above=1500)
    alerts = evaluate_alerts([_rate("test", 1510)], settings)
    assert len(alerts) == 1
    assert "1510" in alerts[0]


def test_no_alert_when_below_threshold() -> None:
    settings = Settings(sell_rate_alert_above=1500)
    alerts = evaluate_alerts([_rate("test", 1490)], settings)
    assert alerts == []


def test_multiple_sources_some_alert() -> None:
    settings = Settings(sell_rate_alert_above=1500)
    rates = [_rate("a", 1510), _rate("b", 1490), _rate("c", 1520)]
    alerts = evaluate_alerts(rates, settings)
    assert len(alerts) == 2
