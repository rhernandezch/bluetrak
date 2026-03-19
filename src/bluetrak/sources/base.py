"""Abstract base class for exchange rate sources."""

import abc
import logging
from datetime import datetime

import httpx

from bluetrak.models import Rate

logger = logging.getLogger(__name__)


class RateSource(abc.ABC):
    """Base class for all exchange rate fetchers."""

    name: str  # e.g., "dolarapp", "western_union", "infodolar_ccl"

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Bluetrak/0.1)"},
        )

    @abc.abstractmethod
    def fetch(self) -> Rate:
        """Fetch the current exchange rate from the source.

        Raises:
            httpx.HTTPError: On network failures.
            ValueError: When the response cannot be parsed.
        """
        ...

    def _now(self) -> datetime:
        return datetime.now()

    def close(self) -> None:
        self.client.close()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"
