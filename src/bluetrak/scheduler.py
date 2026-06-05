"""APScheduler setup for periodic rate fetching and summaries."""

import logging
import threading
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from bluetrak.alerts.engine import evaluate_alerts
from bluetrak.alerts.summary import format_summary
from bluetrak.alerts.telegram import send_telegram
from bluetrak.alerts.webhook import send_webhook
from bluetrak.config import Settings
from bluetrak.db import Database
from bluetrak.models import AlertLevel, AlertSignal, AlertUrgency, Rate, format_rate_change_message
from bluetrak.sources.base import RateSource

logger = logging.getLogger(__name__)


class _SummaryState:
    """Accumulates fired alert signals between summary sends. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alerts: list[AlertSignal] = []

    def add(self, signals: list[AlertSignal]) -> None:
        with self._lock:
            self._alerts.extend(s for s in signals if s.should_alert)

    def pop(self) -> list[AlertSignal]:
        """Return accumulated alerts and reset the list."""
        with self._lock:
            alerts = self._alerts[:]
            self._alerts.clear()
        return alerts


def fetch_and_store(
    sources: list[RateSource],
    db: Database,
    settings: Settings,
    state: _SummaryState,
) -> None:
    """Fetch rates from all sources and store them. Runs as a scheduled job."""
    logger.info("Starting fetch cycle for %d sources", len(sources))
    fetched_rates = []

    for source in sources:
        try:
            rate = source.fetch()
            db.save_rate(rate)
            fetched_rates.append(rate)
            logger.info("Fetched %s", rate)
        except Exception:
            logger.exception("Failed to fetch from %s", source.name)

    if not fetched_rates:
        logger.warning("No rates fetched in this cycle")
        return

    if not settings.alerts_enabled:
        return

    # Partition rates by alert mode
    ensemble_rates = []
    for rate in fetched_rates:
        level = settings.alert_level_for(rate.source)
        if level == AlertLevel.OFF:
            continue
        if level == AlertLevel.EVERY_CHANGE:
            _handle_rate_change(rate, db, settings)
            continue
        ensemble_rates.append(rate)

    # Ensemble evaluation for NORMAL/HIGH sources
    if ensemble_rates:
        signals = evaluate_alerts(ensemble_rates, settings, db)
        state.add(signals)
        for signal in signals:
            if signal.should_alert:
                level = settings.alert_level_for(signal.source)
                if level == AlertLevel.HIGH and signal.urgency != AlertUrgency.HIGH:
                    continue
                _dispatch(signal.format_message(), settings)


def send_summary(
    sources: list[RateSource],
    db: Database,
    settings: Settings,
    state: _SummaryState,
) -> None:
    """Build and dispatch the 12h rate summary. Runs as a scheduled job."""
    if not settings.telegram_enabled:
        logger.debug("Summary skipped — Telegram not configured")
        return

    logger.info("Building 12h summary")
    now = datetime.now(tz=UTC)
    since = now - timedelta(hours=12)

    source_names = [s.name for s in sources]
    current_rates = {r.source: r for r in db.get_latest_rates()}
    prev_rates = {name: db.get_rate_before(name, since) for name in source_names}
    rates_12h = {name: db.get_rates_since(name, since) for name in source_names}
    alerts = state.pop()

    message = format_summary(now, source_names, current_rates, prev_rates, rates_12h, alerts)

    try:
        send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, message)
        logger.info("12h summary sent")
    except Exception:
        logger.exception("Failed to send summary via Telegram")


def _handle_rate_change(rate: Rate, db: Database, settings: Settings) -> None:
    """Dispatch a notification if the sell rate changed from the previous reading."""
    previous = db.get_rate_before(rate.source, rate.fetched_at)

    if previous is not None and previous.sell_rate == rate.sell_rate:
        logger.debug("No sell_rate change for %s (still %.2f)", rate.source, rate.sell_rate)
        return

    message = format_rate_change_message(rate.source, rate, previous)
    _dispatch(message, settings)
    logger.info(
        "Rate change alert for %s: %.2f → %.2f",
        rate.source,
        previous.sell_rate if previous else 0,
        rate.sell_rate,
    )


def _dispatch(message: str, settings: Settings) -> None:
    """Send an alert message via configured channels."""
    if settings.telegram_enabled:
        try:
            send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, message)
        except Exception:
            logger.exception("Failed to send Telegram alert")

    if settings.webhook_url:
        try:
            send_webhook(settings.webhook_url, message)
        except Exception:
            logger.exception("Failed to send webhook alert")


def create_scheduler(
    sources: list[RateSource], db: Database, settings: Settings
) -> BlockingScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = BlockingScheduler()
    state = _SummaryState()

    # Fetch rates every N minutes
    scheduler.add_job(
        fetch_and_store,
        trigger=IntervalTrigger(minutes=settings.fetch_interval_minutes),
        args=[sources, db, settings, state],
        id="fetch_rates",
        name="Fetch exchange rates",
        misfire_grace_time=60,
    )

    # Send summary at 8 AM and 8 PM UTC-3 (= 11:00 and 23:00 UTC)
    scheduler.add_job(
        send_summary,
        trigger=CronTrigger(hour="11,23", minute=0, timezone="UTC"),
        args=[sources, db, settings, state],
        id="send_summary",
        name="Send 12h rate summary",
        misfire_grace_time=300,
    )

    return scheduler
