from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import MarketPrice
from app.dto.market_data import OhlcvDto


class MarketPriceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_prices(
        self,
        provider: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[MarketPrice]:
        stmt = (
            select(MarketPrice)
            .where(MarketPrice.provider == provider)
            .where(MarketPrice.symbol == symbol)
            .where(MarketPrice.date >= start_date)
            .where(MarketPrice.date <= end_date)
            .order_by(MarketPrice.date)
        )
        return list(self.session.scalars(stmt))

    def list_prices_up_to(self, provider: str, symbol: str, end_date: date) -> list[MarketPrice]:
        return self.list_prices(provider, symbol, date.min, end_date)

    def latest_price_on_or_before(
        self,
        provider: str,
        symbol: str,
        end_date: date,
    ) -> MarketPrice | None:
        prices = self.list_prices_up_to(provider, symbol, end_date)
        return prices[-1] if prices else None

    def list_prices_in_range(
        self,
        provider: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[MarketPrice]:
        return self.list_prices(provider, symbol, start_date, end_date)

    def upsert_prices(self, provider: str, prices: list[OhlcvDto]) -> None:
        for price in prices:
            existing = self.session.scalar(
                select(MarketPrice)
                .where(MarketPrice.provider == provider)
                .where(MarketPrice.symbol == price.symbol)
                .where(MarketPrice.date == price.date)
                .where(MarketPrice.adjusted == price.adjusted)
            )
            values = price.model_dump()
            if existing is None:
                self.session.add(MarketPrice(provider=provider, **values))
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
        self.session.commit()
