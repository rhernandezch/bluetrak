"""Bluetrak entrypoint — start the scheduler and run forever."""

import logging
from datetime import datetime
from pathlib import Path

from bluetrak.config import settings
from bluetrak.db import Database
from bluetrak.scheduler import _SummaryState, create_scheduler, fetch_and_store
from bluetrak.sources import ALL_SOURCES
from bluetrak.sources.base import RateSource

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt=_LOG_DATE_FORMAT,
)
logger = logging.getLogger(__name__)


def _setup_file_logging(log_dir: Path) -> Path:
    """Add a WARNING+ file handler to the root logger.

    Creates one log file per process run, named by start timestamp.
    Returns the path of the log file.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    log_file = log_dir / f"{timestamp}.log"

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT))
    logging.getLogger().addHandler(handler)

    return log_file


def main() -> None:
    log_file = _setup_file_logging(Path("logs"))
    logger.info("🚀 Bluetrak starting up")
    logger.info("📝 Log file (WARN+): %s", log_file)
    logger.info("🗄️  Database: %s", settings.db_path)
    logger.info("⏱️  Fetch interval: %d minutes", settings.fetch_interval_minutes)
    logger.info("🔔 Alerts enabled: %s", settings.alerts_enabled)

    db = Database(settings.db_path)
    db.connect()

    sources: list[RateSource] = [src() for src in ALL_SOURCES]
    logger.info("🌐 Sources: %s", [s.name for s in sources])

    # Run one fetch immediately on startup
    logger.info("⚡ Running initial fetch...")
    fetch_and_store(sources, db, settings, _SummaryState())

    # Start the scheduler loop
    scheduler = create_scheduler(sources, db, settings)
    try:
        logger.info("✅ Scheduler started — fetching every %d min", settings.fetch_interval_minutes)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Shutting down...")
    finally:
        scheduler.shutdown(wait=False)
        for source in sources:
            source.close()
        db.close()


if __name__ == "__main__":
    main()
