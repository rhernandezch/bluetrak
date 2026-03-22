"""Tests for exchange rate source parsers using mocked HTTP responses."""

import httpx
import respx

from bluetrak.sources.dolarapp import DolarAppSource
from bluetrak.sources.western_union import WesternUnionSource


@respx.mock
def test_dolarapp_fetch() -> None:
    mock_response = [
        {"book": "usdc_ars", "bid": "1466.0", "ask": "1469.0", "date": "2026-03-19T12:00:00"}
    ]
    respx.get("https://api.dolarapp.com/v1/tickers?currencies=ARS").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    source = DolarAppSource()
    rate = source.fetch()

    assert rate.source == "dolarapp"
    assert rate.buy_rate == 1466.0
    assert rate.sell_rate == 1469.0


@respx.mock
def test_western_union_fetch() -> None:
    mock_response = {
        "services_groups": [
            {
                "service_name": "Money In Minutes",
                "pay_groups": [
                    {"fund_in": "CC", "fx_rate": 1469.25, "gross_fee": 20.99}
                ],
            }
        ]
    }
    respx.post("https://www.westernunion.com/wuconnect/prices/catalog").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    source = WesternUnionSource()
    rate = source.fetch()

    assert rate.source == "western_union"
    assert rate.buy_rate == 1469.25
    assert rate.sell_rate == 1469.25


@respx.mock
def test_western_union_bad_response() -> None:
    """Test that WU parser raises ValueError on unexpected structure."""
    mock_response = {"unexpected": "structure"}
    respx.post("https://www.westernunion.com/wuconnect/prices/catalog").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    source = WesternUnionSource()
    try:
        source.fetch()
        raise AssertionError("Should have raised ValueError")
    except ValueError as exc:
        assert "Could not extract fx_rate" in str(exc)
