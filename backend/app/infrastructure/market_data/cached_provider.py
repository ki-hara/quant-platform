from datetime import date

from app.dto.market_data import OhlcvDto
from app.infrastructure.market_data.base import MarketDataProvider
from app.infrastructure.repositories.market_data import MarketPriceRepository


class CachedMarketDataProvider:
    def __init__(
        self,
        provider_name: str,
        repository: MarketPriceRepository,
        provider: MarketDataProvider,
    ) -> None:
        self.provider_name = provider_name
        self.repository = repository
        self.provider = provider

    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
        cached = self.repository.list_prices(
            self.provider_name,
            symbol,
            start_date,
            end_date,
        )
        if self._covers_requested_range(cached, start_date, end_date):
            return self._to_dtos(cached)

        # This deliberately refetches the full requested range when cache coverage is
        # incomplete. It avoids guessing exchange-specific trading calendars here.
        fetched = self.provider.get_ohlcv(symbol, start_date, end_date)
        self.repository.upsert_prices(self.provider_name, fetched)
        return self._to_dtos(
            self.repository.list_prices(self.provider_name, symbol, start_date, end_date)
        )

    def _covers_requested_range(
        self,
        cached: list[object],
        start_date: date,
        end_date: date,
    ) -> bool:
        if not cached:
            return False
        cached_dates = {price.date for price in cached}
        return start_date in cached_dates and end_date in cached_dates

    def _to_dtos(self, prices: list[object]) -> list[OhlcvDto]:
        return [
            OhlcvDto(
                symbol=price.symbol,
                date=price.date,
                open=price.open,
                high=price.high,
                low=price.low,
                close=price.close,
                volume=int(price.volume),
                adjusted=price.adjusted,
            )
            for price in sorted(prices, key=lambda item: item.date)
        ]
