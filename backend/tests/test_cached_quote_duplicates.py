from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.infrastructure.market_data.cached_provider import CachedMarketDataProvider


def quote(day, adjusted, close):
    return SimpleNamespace(symbol="SOXL", date=day, adjusted=adjusted,
                           open=Decimal(close), high=Decimal(close),
                           low=Decimal(close), close=Decimal(close), volume=100)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("cache_hit", [False, True])
def test_august_28_is_returned_once_after_cache_read_or_refetch(reverse, cache_hit):
    day = date(2026, 8, 28)
    rows = [quote(day, False, "111.34"), quote(day, True, "111.339996")]
    if reverse:
        rows.reverse()

    class Repository:
        calls = 0

        def list_prices(self, *args):
            self.calls += 1
            return [] if not cache_hit and self.calls == 1 else rows

        def upsert_prices(self, *args):
            pass

    class Provider:
        def get_ohlcv(self, *args):
            assert not cache_hit
            return []

    result = CachedMarketDataProvider("finance_data_reader", Repository(), Provider()).get_ohlcv("SOXL", day, day)
    assert len(result) == 1
    assert result[0].adjusted is True
    assert result[0].close == Decimal("111.339996")


def test_fallback_only_day_is_preserved_and_dates_sorted():
    provider = CachedMarketDataProvider("test", None, None)
    result = provider._to_dtos([
        quote(date(2026, 8, 28), False, "111.34"),
        quote(date(2026, 8, 27), True, "110"),
    ])
    assert [p.date.day for p in result] == [27, 28]
    assert result[1].adjusted is False
