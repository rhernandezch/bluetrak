"""Bluetrak entrypoint — start the scheduler and run forever."""

import logging

from bluetrak.config import settings
from bluetrak.db import Database
from bluetrak.scheduler import create_scheduler, fetch_and_store
from bluetrak.sources import ALL_SOURCES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Bluetrak starting up")
    logger.info("Database: %s", settings.db_path)
    logger.info("Fetch interval: %d minutes", settings.fetch_interval_minutes)
    logger.info("Alerts enabled: %s", settings.alerts_enabled)

    db = Database(settings.db_path)
    db.connect()

    sources = [src() for src in ALL_SOURCES]
    logger.info("Sources: %s", [s.name for s in sources])

    # Run one fetch immediately on startup
    logger.info("Running initial fetch...")
    fetch_and_store(sources, db, settings)

    # Start the scheduler loop
    scheduler = create_scheduler(sources, db, settings)
    try:
        logger.info("Scheduler started — fetching every %d min", settings.fetch_interval_minutes)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown(wait=False)
        for source in sources:
            source.close()
        db.close()


if __name__ == "__main__":
    main()
