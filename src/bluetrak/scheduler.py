"""APScheduler setup for periodic rate fetching."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bluetrak.alerts.engine import evaluate_alerts
from bluetrak.alerts.telegram import send_telegram
from bluetrak.alerts.webhook import send_webhook
from bluetrak.config import Settings
from bluetrak.db import Database
from bluetrak.sources.base import RateSource

logger = logging.getLogger(__name__)


def fetch_and_store(sources: list[RateSource], db: Database, settings: Settings) -> None:
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

    # Evaluate alerts
    if settings.alerts_enabled:
        signals = evaluate_alerts(fetched_rates, settings, db)
        for signal in signals:
            if signal.should_alert:
                _dispatch_alert(signal.format_message(), settings)


def _dispatch_alert(message: str, settings: Settings) -> None:
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

    trigger = IntervalTrigger(minutes=settings.fetch_interval_minutes)
    scheduler.add_job(
        fetch_and_store,
        trigger=trigger,
        args=[sources, db, settings],
        id="fetch_rates",
        name="Fetch exchange rates",
        misfire_grace_time=60,
    )

    return scheduler
