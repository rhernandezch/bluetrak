"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings

from bluetrak.models import AlertLevel


class Settings(BaseSettings):
    model_config = {"env_prefix": "BLUETRAK_", "env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    db_path: Path = Path("bluetrak.db")

    # Scheduling intervals (in minutes)
    fetch_interval_minutes: int = 15

    # Alerting
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""

    # Alert thresholds
    sell_rate_alert_above: float = 0.0  # Alert when any sell rate exceeds this (legacy fallback)

    # Intelligent alert settings
    alert_percentile_threshold: float = 90.0  # Percentile rank to trigger alert (0-100)
    alert_percentile_window_days: int = 7  # Days of history for percentile calculation
    alert_trend_window_days: int = 14  # Days of history for linear trend fitting

    # Per-source alert levels
    alert_level_dolarapp: AlertLevel = AlertLevel.NORMAL
    alert_level_western_union: AlertLevel = AlertLevel.NORMAL
    alert_level_infodolar_ccl: AlertLevel = AlertLevel.NORMAL

    def alert_level_for(self, source_name: str) -> AlertLevel:
        """Return the configured alert level for a source, defaulting to NORMAL."""
        field_name = f"alert_level_{source_name}"
        return getattr(self, field_name, AlertLevel.NORMAL)

    @property
    def alerts_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id) or bool(self.webhook_url)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


settings = Settings()
