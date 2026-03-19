"""infodolar.com CCL (Contado Con Liquidación) exchange rate source.

Requires HTML scraping since there's no public API.
"""

import json
import logging
import re

from bs4 import BeautifulSoup

from bluetrak.models import Rate
from bluetrak.sources.base import RateSource

logger = logging.getLogger(__name__)

INFODOLAR_URL = "https://www.infodolar.com/"


class InfoDolarSource(RateSource):
    name = "infodolar_ccl"

    def fetch(self) -> Rate:
        resp = self.client.get(INFODOLAR_URL)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        buy_rate, sell_rate = self._parse_ccl_rates(soup)

        return Rate(
            source=self.name,
            buy_rate=buy_rate,
            sell_rate=sell_rate,
            fetched_at=self._now(),
            raw_response=json.dumps({
                "url": INFODOLAR_URL,
                "title": soup.title.string if soup.title else "",
            }),
        )

    def _parse_ccl_rates(self, soup: BeautifulSoup) -> tuple[float, float]:
        """Extract CCL buy/sell rates from infodolar.com HTML.

        The page has multiple elements matching "CCL" (nav links, table rows, etc).
        We scan all matches and use the first <tr> ancestor that contains rate values.
        """
        ccl_pattern = re.compile(r"CCL|Contado con Liquidaci", re.IGNORECASE)

        for ccl_element in soup.find_all(string=ccl_pattern):
            row = ccl_element.find_parent("tr")
            if row is None:
                continue

            rate_values = self._extract_rates_from_container(row)
            if len(rate_values) >= 2:
                return rate_values[0], rate_values[1]

        raise ValueError(
            "Could not find CCL rate row on infodolar.com — "
            "no <tr> with CCL text and at least 2 numeric values. "
            "The page structure may have changed."
        )

    def _extract_rates_from_container(self, container: object) -> list[float]:
        """Extract numeric rate values from an HTML container."""
        rates: list[float] = []

        # Find elements that look like rate values (numbers with optional decimals)
        # Common patterns: "$1,480.50", "1480,50", "1.480,50"
        text = container.get_text(separator=" ")  # type: ignore[union-attr]
        # Match Argentine number format: 1.480,50 or 1480,50
        matches = re.findall(r"(\d{1,2}\.?\d{3}(?:,\d{1,2})?)", text)

        for match in matches:
            # Normalize: "1.480,50" -> "1480.50"
            normalized = match.replace(".", "").replace(",", ".")
            try:
                rates.append(float(normalized))
            except ValueError:
                continue

        return rates
