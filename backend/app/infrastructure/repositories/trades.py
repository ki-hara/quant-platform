from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import PositionStatus, TradeSide, TradeSource
from app.domain.models import Position, Trade


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
        limit_price: Decimal | None = None,
        position_id: int | None = None,
        entry_date: date | None = None,
        entry_price: Decimal | None = None,
    ) -> Trade:
        trade = Trade(
            strategy_config_id=strategy_config_id,
            date=trade_date,
            side=side,
            quantity=quantity,
            position_id=position_id,
            entry_date=entry_date,
            entry_price=entry_price,
            limit_price=limit_price,
            price=price,
            fee=fee,
            realized_pnl=realized_pnl,
            sell_reason=sell_reason,
            source=source,
        )
        self.session.add(trade)
        self.session.flush()
        self.session.refresh(trade)
        return trade

    def list_by_strategy_config(self, strategy_config_id: int) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.strategy_config_id == strategy_config_id)
            .order_by(Trade.date, Trade.id)
        )
        return list(self.session.scalars(stmt))

    def get(self, trade_id: int) -> Trade | None:
        return self.session.get(Trade, trade_id)

    def delete(self, trade: Trade) -> None:
        self.session.delete(trade)
        self.session.flush()

    def list_in_range(
        self,
        strategy_config_id: int,
        start_date: date,
        end_date: date,
    ) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.strategy_config_id == strategy_config_id)
            .where(Trade.date >= start_date)
            .where(Trade.date <= end_date)
            .order_by(Trade.date, Trade.id)
        )
        return list(self.session.scalars(stmt))

    def list_position_history(self, strategy_config_id: int) -> list[dict[str, object]]:
        open_stmt = (
            select(Position)
            .where(Position.strategy_config_id == strategy_config_id)
            .where(Position.status.in_([PositionStatus.PENDING, PositionStatus.OPEN]))
            .order_by(Position.buy_date, Position.id)
        )
        rows: list[dict[str, object]] = [
            {
                "trade_id": None,
                "position_id": position.id,
                "buy_date": position.buy_date,
                "sell_date": None,
                "status": position.status.value,
                "quantity": position.quantity,
                "entry_price": position.buy_price,
                "exit_price": None,
                "fee": position.buy_fee,
                "realized_pnl": None,
                "sell_reason": None,
            }
            for position in self.session.scalars(open_stmt)
        ]
        sell_stmt = (
            select(Trade)
            .where(Trade.strategy_config_id == strategy_config_id)
            .where(Trade.side == TradeSide.SELL)
            .where(Trade.entry_price.is_not(None))
            .order_by(Trade.date, Trade.id)
        )
        rows.extend(
            {
                "trade_id": trade.id,
                "position_id": trade.position_id,
                "buy_date": trade.entry_date or trade.date,
                "sell_date": trade.date,
                "status": "closed",
                "quantity": trade.quantity,
                "entry_price": trade.entry_price or trade.price,
                "exit_price": trade.price,
                "fee": trade.fee,
                "realized_pnl": trade.realized_pnl,
                "sell_reason": trade.sell_reason,
            }
            for trade in self.session.scalars(sell_stmt)
        )
        return sorted(
            rows,
            key=lambda row: (row["sell_date"] or row["buy_date"], row["position_id"] or 0),
            reverse=True,
        )
