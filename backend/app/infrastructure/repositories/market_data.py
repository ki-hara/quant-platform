from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
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
            .order_by(MarketPrice.date, MarketPrice.adjusted)
        )
        # Prefer the primary quote when both primary and fallback exist.
        by_date = {price.date: price for price in self.session.scalars(stmt)}
        return list(by_date.values())

    def list_prices_up_to(self, provider: str, symbol: str, end_date: date) -> list[MarketPrice]:
        return self.list_prices(provider, symbol, date.min, end_date)

    def latest_price_on_or_before(
        self,
        provider: str,
        symbol: str,
        end_date: date,
    ) -> MarketPrice | None:
        return self.session.scalar(
            select(MarketPrice).where(
                MarketPrice.provider == provider, MarketPrice.symbol == symbol,
                MarketPrice.date <= end_date,
            ).order_by(MarketPrice.date.desc(), MarketPrice.adjusted.desc()).limit(1)
        )

    def list_prices_in_range(
        self,
        provider: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[MarketPrice]:
        return self.list_prices(provider, symbol, start_date, end_date)

    def upsert_prices(self, provider: str, prices: list[OhlcvDto]) -> None:
        rows = [dict(provider=provider, **price.model_dump()) for price in prices]
        try:
            # Bound statement size for SQLite builds with a low variable limit.
            for offset in range(0, len(rows), 80):
                statement = insert(MarketPrice).values(rows[offset:offset + 80])
                self.session.execute(statement.on_conflict_do_update(
                    index_elements=["provider", "symbol", "date", "adjusted"],
                    set_={key: getattr(statement.excluded, key) for key in
                          ("open", "high", "low", "close", "volume")},
                ))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
