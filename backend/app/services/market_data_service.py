from datetime import date

from app.dto.market_data import OhlcvDto
from app.infrastructure.market_data.base import MarketDataProvider


class MarketDataService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
        return self.provider.get_ohlcv(symbol, start_date, end_date)
