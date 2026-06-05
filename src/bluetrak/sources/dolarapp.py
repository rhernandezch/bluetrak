"""DolarApp / ARQ Finance exchange rate source.

Simple GET endpoint returning JSON with bid/ask rates for ARS.
"""

import logging

from bluetrak.models import Rate
from bluetrak.sources.base import RateSource

logger = logging.getLogger(__name__)

DOLARAPP_URL = "https://api.dolarapp.com/v1/tickers?currencies=ARS"


class DolarAppSource(RateSource):
    name = "dolarapp"

    def fetch(self) -> Rate:
        resp = self.client.get(DOLARAPP_URL)
        resp.raise_for_status()
        data = resp.json()

        # Response shape: [{"book": "usdc_ars", "bid": "1462.16", "ask": "1466.53", ...}]
        ars_ticker = next(t for t in data if "ars" in t.get("book", "").lower())

        return Rate(
            source=self.name,
            buy_rate=float(ars_ticker["ask"]),
            sell_rate=float(ars_ticker["bid"]),
            fetched_at=self._now(),
        )
