from datetime import date
from decimal import Decimal

from app.dto.market_data import OhlcvDto


def simple_prices() -> list[OhlcvDto]:
    closes = ["100", "103", "108", "107", "106", "112"]
    return [
        OhlcvDto(
            symbol="TEST",
            date=date(2026, 1, index + 1),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]
