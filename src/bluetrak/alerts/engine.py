"""Alert evaluation engine.

Checks latest rates against configured thresholds and dispatches notifications.
"""

import logging

from bluetrak.config import Settings
from bluetrak.models import Rate

logger = logging.getLogger(__name__)


def evaluate_alerts(rates: list[Rate], settings: Settings) -> list[str]:
    """Evaluate rates against alert thresholds. Returns list of alert messages."""
    messages: list[str] = []

    if settings.sell_rate_alert_above <= 0:
        return messages

    threshold = settings.sell_rate_alert_above
    for rate in rates:
        if rate.sell_rate >= threshold:
            msg = (
                f"[{rate.source}] Sell rate {rate.sell_rate:.2f} ARS/USD "
                f"exceeded threshold {threshold:.2f}"
            )
            messages.append(msg)
            logger.info("Alert triggered: %s", msg)

    return messages
