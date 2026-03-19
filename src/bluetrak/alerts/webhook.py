"""Generic webhook notification dispatch."""

import logging

import httpx

logger = logging.getLogger(__name__)


def send_webhook(url: str, message: str) -> None:
    """POST a JSON payload to a webhook URL."""
    resp = httpx.post(url, json={"text": message})
    resp.raise_for_status()
    logger.info("Webhook sent to %s", url)
