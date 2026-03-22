"""bluetrak-test-telegram — send a test message to validate Telegram configuration."""

import sys

from bluetrak.alerts.telegram import send_telegram
from bluetrak.config import settings


def main() -> None:
    if not settings.telegram_enabled:
        print(
            "❌ ERROR: Telegram is not configured.\n"
            "   Set BLUETRAK_TELEGRAM_BOT_TOKEN and BLUETRAK_TELEGRAM_CHAT_ID."
        )
        sys.exit(1)

    print(f"📤 Sending test message to chat {settings.telegram_chat_id}...")
    try:
        send_telegram(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            "🤖 *Bluetrak* — test message\n\n✅ Telegram is configured correctly!",
        )
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

    print("✅ OK — message sent successfully!")
