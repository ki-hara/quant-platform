import logging
from datetime import date, timedelta

from app.core.errors import MarketDataError
from app.infrastructure.market_data.base import MarketDataProvider


logger = logging.getLogger(__name__)


class MissingDailyPriceFallbackProvider:
    def __init__(
        self,
        primary: MarketDataProvider,
        fallback: MarketDataProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list:
        is_single_day = end_date - start_date == timedelta(days=1)
        try:
            primary_prices = self._primary.get_ohlcv(symbol, start_date, end_date)
        except MarketDataError:
            if not is_single_day:
                raise
            primary_prices = []

        if not is_single_day or any(
            price.date == start_date for price in primary_prices
        ):
            return primary_prices

        logger.warning(
            "Primary market data missing confirmed day; trying fallback: "
            "symbol=%s date=%s",
            symbol,
            start_date,
        )
        fallback_prices = self._fallback.get_ohlcv(symbol, start_date, end_date)
        prices_by_date = {
            price.date: price
            for price in [*primary_prices, *fallback_prices]
            if start_date <= price.date < end_date
        }
        return sorted(prices_by_date.values(), key=lambda price: price.date)
