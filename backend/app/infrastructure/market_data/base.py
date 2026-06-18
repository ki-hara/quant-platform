from datetime import date
from typing import Protocol

from app.dto.market_data import OhlcvDto


class MarketDataProvider(Protocol):
    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
        pass
