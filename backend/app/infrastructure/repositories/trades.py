from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TradeSide, TradeSource
from app.domain.models import Trade


class TradeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        strategy_config_id: int,
        trade_date: date,
        side: TradeSide,
        quantity: Decimal,
        price: Decimal,
        fee: Decimal,
        realized_pnl: Decimal,
        sell_reason: str | None,
        source: TradeSource,
    ) -> Trade:
        trade = Trade(
            strategy_config_id=strategy_config_id,
            date=trade_date,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            realized_pnl=realized_pnl,
            sell_reason=sell_reason,
            source=source,
        )
        self.session.add(trade)
        self.session.commit()
        self.session.refresh(trade)
        return trade

    def list_by_strategy_config(self, strategy_config_id: int) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.strategy_config_id == strategy_config_id)
            .order_by(Trade.date, Trade.id)
        )
        return list(self.session.scalars(stmt))
