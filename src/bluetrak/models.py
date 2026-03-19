"""Domain models for exchange rate data."""

from datetime import datetime

from pydantic import BaseModel


class Rate(BaseModel):
    """A single exchange rate observation from a source."""

    source: str
    buy_rate: float  # ARS per USD — what you pay to buy USD
    sell_rate: float  # ARS per USD — what you get when selling USD
    fetched_at: datetime
    raw_response: str = ""  # JSON dump for debugging

    def __str__(self) -> str:
        return f"{self.source}: buy={self.buy_rate:.2f} sell={self.sell_rate:.2f}"
