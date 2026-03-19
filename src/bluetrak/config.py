"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "BLUETRAK_"}

    # Database
    db_path: Path = Path("bluetrak.db")

    # Scheduling intervals (in minutes)
    fetch_interval_minutes: int = 15

    # Alerting
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""

    # Alert thresholds
    sell_rate_alert_above: float = 0.0  # Alert when any sell rate exceeds this

    @property
    def alerts_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id) or bool(self.webhook_url)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


settings = Settings()
