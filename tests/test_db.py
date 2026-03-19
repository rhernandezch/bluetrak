"""Tests for the database layer."""

from datetime import datetime
from pathlib import Path

from bluetrak.db import Database
from bluetrak.models import Rate


def make_rate(source: str = "test", buy: float = 1400.0, sell: float = 1450.0) -> Rate:
    return Rate(
        source=source,
        buy_rate=buy,
        sell_rate=sell,
        fetched_at=datetime.now(),
    )


def test_save_and_retrieve(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.connect()
    try:
        rate = make_rate()
        db.save_rate(rate)

        latest = db.get_latest_rates()
        assert len(latest) == 1
        assert latest[0].source == "test"
        assert latest[0].buy_rate == 1400.0
        assert latest[0].sell_rate == 1450.0
    finally:
        db.close()


def test_latest_returns_one_per_source(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.connect()
    try:
        db.save_rate(make_rate("source_a", buy=1000, sell=1100))
        db.save_rate(make_rate("source_a", buy=1010, sell=1110))
        db.save_rate(make_rate("source_b", buy=1200, sell=1300))

        latest = db.get_latest_rates()
        assert len(latest) == 2
        sources = {r.source for r in latest}
        assert sources == {"source_a", "source_b"}
    finally:
        db.close()


def test_save_rates_batch(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.connect()
    try:
        rates = [make_rate("a"), make_rate("b"), make_rate("c")]
        db.save_rates(rates)

        latest = db.get_latest_rates()
        assert len(latest) == 3
    finally:
        db.close()
