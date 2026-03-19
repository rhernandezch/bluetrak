"""Tests for exchange rate source parsers using mocked HTTP responses."""

import json

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
    assert rate.raw_response == json.dumps(mock_response)


@respx.mock
def test_western_union_fetch() -> None:
    mock_response = {
        "product_list": [
            {"product_name": "Money Transfer", "exchange_rate": "1471.50", "fee": "0.00"}
        ]
    }
    respx.post("https://www.westernunion.com/wuconnect/prices/catalog").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    source = WesternUnionSource()
    rate = source.fetch()

    assert rate.source == "western_union"
    assert rate.buy_rate == 1471.50
    assert rate.sell_rate == 1471.50


@respx.mock
def test_western_union_nested_rate() -> None:
    """Test that WU parser can find exchange_rate in nested structures."""
    mock_response = {
        "price_inquiry": {
            "details": {"exchange_rate": "1475.25"},
        }
    }
    respx.post("https://www.westernunion.com/wuconnect/prices/catalog").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    source = WesternUnionSource()
    rate = source.fetch()

    assert rate.sell_rate == 1475.25
