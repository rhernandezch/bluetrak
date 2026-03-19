"""Western Union exchange rate source.

POST endpoint requiring a JSON body with sender/receiver configuration.
The rate is the same across all payment methods — only fees differ.
"""

import json
import logging

from bluetrak.models import Rate
from bluetrak.sources.base import RateSource

logger = logging.getLogger(__name__)

WU_URL = "https://www.westernunion.com/wuconnect/prices/catalog"

WU_PAYLOAD = {
    "header_request": {"version": "0.5", "request_type": "PRICECATALOG"},
    "sender": {
        "client": "WUCOM",
        "channel": "WWEB",
        "funds_in": "*",
        "curr_iso3": "USD",
        "cty_iso2_ext": "US",
        "send_amount": "100.00",
    },
    "receiver": {
        "curr_iso3": "ARS",
        "cty_iso2_ext": "AR",
        "cty_iso2": "AR",
    },
}


class WesternUnionSource(RateSource):
    name = "western_union"

    def __init__(self) -> None:
        super().__init__()
        self.client.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://www.westernunion.com",
                "Referer": "https://www.westernunion.com/us/en/web/send-money/start",
            }
        )

    def fetch(self) -> Rate:
        resp = self.client.post(WU_URL, json=WU_PAYLOAD)
        resp.raise_for_status()
        data = resp.json()

        fx_rate = self._extract_rate(data)

        return Rate(
            source=self.name,
            buy_rate=fx_rate,
            sell_rate=fx_rate,
            fetched_at=self._now(),
            raw_response=json.dumps(data),
        )

    def _extract_rate(self, data: dict) -> float:  # type: ignore[type-arg]
        """Extract fx_rate from services_groups[0].pay_groups[0].fx_rate."""
        try:
            return float(data["services_groups"][0]["pay_groups"][0]["fx_rate"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(
                f"Could not extract fx_rate from WU response. "
                f"Top-level keys: {list(data.keys())}"
            ) from exc
