from datetime import date
from decimal import Decimal

from app.infrastructure.market_data.eastmoney_provider import EastmoneyMarketDataProvider


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def test_fetches_exact_us_symbol_and_parses_daily_ohlcv() -> None:
    calls: list[tuple[str, dict]] = []

    def http_get(url: str, *, params: dict, **kwargs) -> FakeResponse:
        calls.append((url, params))
        if "suggest" in url:
            return FakeResponse(
                {
                    "QuotationCodeTable": {
                        "Data": [
                            {"Code": "SOXL", "QuoteID": "107.SOXL"},
                            {"Code": "SOXS", "QuoteID": "107.SOXS"},
                        ]
                    }
                }
            )
        return FakeResponse(
            {
                "data": {
                    "code": "SOXL",
                    "market": 107,
                    "klines": [
                        "2026-08-28,119.920,111.340,121.200,110.210,60995620,0"
                    ],
                }
            }
        )

    prices = EastmoneyMarketDataProvider(http_get=http_get).get_ohlcv(
        "soxl",
        date(2026, 8, 28),
        date(2026, 8, 29),
    )

    assert len(prices) == 1
    assert prices[0].symbol == "SOXL"
    assert prices[0].date == date(2026, 8, 28)
    assert prices[0].open == Decimal("119.920")
    assert prices[0].high == Decimal("121.200")
    assert prices[0].low == Decimal("110.210")
    assert prices[0].close == Decimal("111.340")
    assert prices[0].volume == 60_995_620
    assert calls[1][1]["secid"] == "107.SOXL"
    assert calls[1][1]["beg"] == "20260828"
    assert calls[1][1]["end"] == "20260828"


def test_rejects_invalid_ohlc_rows() -> None:
    responses = iter(
        [
            FakeResponse(
                {
                    "QuotationCodeTable": {
                        "Data": [{"Code": "SOXL", "QuoteID": "107.SOXL"}]
                    }
                }
            ),
            FakeResponse(
                {
                    "data": {
                        "code": "SOXL",
                        "klines": [
                            "2026-08-28,119.92,111.34,110.00,110.21,60995620"
                        ],
                    }
                }
            ),
        ]
    )
    provider = EastmoneyMarketDataProvider(
        http_get=lambda *args, **kwargs: next(responses)
    )

    assert provider.get_ohlcv(
        "SOXL", date(2026, 8, 28), date(2026, 8, 29)
    ) == []
