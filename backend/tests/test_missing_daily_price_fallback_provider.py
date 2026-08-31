from datetime import date, timedelta
from decimal import Decimal

from app.dto.market_data import OhlcvDto
from app.infrastructure.market_data.missing_daily_price_fallback_provider import (
    MissingDailyPriceFallbackProvider,
)
from app.services.market_refresh_service import get_market_data_provider


def _price(symbol: str, quote_date: date, close: str) -> OhlcvDto:
    value = Decimal(close)
    return OhlcvDto(
        symbol=symbol,
        date=quote_date,
        open=value,
        high=value,
        low=value,
        close=value,
        volume=1,
    )


class StubProvider:
    def __init__(self, prices: list[OhlcvDto]) -> None:
        self.prices = prices
        self.calls: list[tuple[str, date, date]] = []

    def get_ohlcv(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[OhlcvDto]:
        self.calls.append((symbol, start_date, end_date))
        return self.prices


def test_uses_fallback_only_when_single_day_primary_result_is_missing() -> None:
    target = date(2026, 8, 28)
    primary = StubProvider([])
    fallback = StubProvider([_price("SOXL", target, "111.34")])
    provider = MissingDailyPriceFallbackProvider(primary, fallback)

    prices = provider.get_ohlcv("SOXL", target, target + timedelta(days=1))

    assert [price.close for price in prices] == [Decimal("111.34")]
    assert fallback.calls == [("SOXL", target, target + timedelta(days=1))]


def test_does_not_use_fallback_for_long_range_or_complete_primary_day() -> None:
    target = date(2026, 8, 28)
    primary = StubProvider([_price("SOXL", target, "111.34")])
    fallback = StubProvider([_price("SOXL", target, "999")])
    provider = MissingDailyPriceFallbackProvider(primary, fallback)

    long_prices = provider.get_ohlcv(
        "SOXL", target - timedelta(days=30), target + timedelta(days=1)
    )
    exact_prices = provider.get_ohlcv(
        "SOXL", target, target + timedelta(days=1)
    )

    assert long_prices[0].close == Decimal("111.34")
    assert exact_prices[0].close == Decimal("111.34")
    assert fallback.calls == []


def test_market_refresh_factory_enables_missing_day_fallback() -> None:
    assert isinstance(get_market_data_provider(), MissingDailyPriceFallbackProvider)
