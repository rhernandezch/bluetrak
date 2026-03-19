"""Western Union exchange rate source.

POST endpoint requiring a JSON body with sender/receiver configuration.
"""

import json
import logging

from bluetrak.models import Rate
from bluetrak.sources.base import RateSource

logger = logging.getLogger(__name__)

WU_URL = "https://www.westernunion.com/wuconnect/prices/catalog"

WU_PAYLOAD = {
    "sender": {
        "country_iso_code": "US",
        "currency_iso_code": "USD",
        "funds_in": "BA",
    },
    "receiver": {
        "country_iso_code": "AR",
        "currency_iso_code": "ARS",
        "funds_out": "BA",
    },
    "payment_details": {
        "origination_amount": "100",
        "origination_currency_iso_code": "USD",
        "destination_currency_iso_code": "ARS",
    },
    "channel": "WEB",
}


class WesternUnionSource(RateSource):
    name = "western_union"

    def __init__(self) -> None:
        super().__init__()
        # WU requires browser-like headers
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

        # Extract exchange rate from the response
        # WU returns the rate in the price catalog response
        exchange_rate = self._extract_rate(data)

        return Rate(
            source=self.name,
            buy_rate=exchange_rate,
            sell_rate=exchange_rate,
            fetched_at=self._now(),
            raw_response=json.dumps(data),
        )

    def _extract_rate(self, data: dict) -> float:  # type: ignore[type-arg]
        """Extract the ARS/USD exchange rate from WU's response.

        WU's response structure varies, so we try multiple paths.
        """
        # Try common response paths
        try:
            # Path: product_list -> exchange_rate
            for product in data.get("product_list", []):
                if "exchange_rate" in product:
                    return float(product["exchange_rate"])
        except (KeyError, TypeError, StopIteration):
            pass

        try:
            # Path: price_inquiry -> exchange_rate
            inquiry = data.get("price_inquiry", {})
            if "exchange_rate" in inquiry:
                return float(inquiry["exchange_rate"])
        except (KeyError, TypeError):
            pass

        try:
            # Fallback: search recursively for exchange_rate key
            rate = self._find_rate_recursive(data)
            if rate is not None:
                return rate
        except (KeyError, TypeError):
            pass

        raise ValueError(
            f"Could not extract exchange rate from WU response. "
            f"Keys: {list(data.keys())}"
        )

    def _find_rate_recursive(self, obj: object, key: str = "exchange_rate") -> float | None:
        """Recursively search for a key in nested dicts/lists."""
        if isinstance(obj, dict):
            if key in obj:
                return float(obj[key])  # type: ignore[arg-type]
            for v in obj.values():
                result = self._find_rate_recursive(v, key)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_rate_recursive(item, key)
                if result is not None:
                    return result
        return None
