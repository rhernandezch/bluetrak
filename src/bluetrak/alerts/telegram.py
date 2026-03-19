"""Telegram notification dispatch."""

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send_telegram(bot_token: str, chat_id: str, message: str) -> None:
    """Send a message via Telegram Bot API (raw HTTP, no extra dependency needed)."""
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    resp = httpx.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
    resp.raise_for_status()
    logger.info("Telegram message sent to chat %s", chat_id)
