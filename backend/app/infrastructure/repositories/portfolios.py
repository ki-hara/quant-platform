from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import PositionStatus, StrategyMode
from app.domain.models import LivePortfolio, Position, StrategyConfig


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_for_config(self, config: StrategyConfig) -> LivePortfolio:
        portfolio = LivePortfolio(
            strategy_config_id=config.id,
            capital=config.initial_capital,
            cash=config.initial_capital,
            realized_pnl=Decimal("0"),
            cumulative_fees=Decimal("0"),
        )
        self.session.add(portfolio)
        self.session.commit()
        self.session.refresh(portfolio)
        return portfolio

    def get_by_config(self, strategy_config_id: int) -> LivePortfolio | None:
        return self.session.get(LivePortfolio, strategy_config_id)

    def save(self, portfolio: LivePortfolio) -> LivePortfolio:
        self.session.add(portfolio)
        self.session.commit()
        self.session.refresh(portfolio)
        return portfolio


class PositionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_open(self, strategy_config_id: int) -> list[Position]:
        stmt = (
            select(Position)
            .where(Position.strategy_config_id == strategy_config_id)
            .where(Position.status == PositionStatus.OPEN)
            .order_by(Position.buy_date, Position.id)
        )
        return list(self.session.scalars(stmt))

    def list_by_strategy_config(self, strategy_config_id: int) -> list[Position]:
        stmt = (
            select(Position)
            .where(Position.strategy_config_id == strategy_config_id)
            .order_by(Position.buy_date, Position.id)
        )
        return list(self.session.scalars(stmt))

    def create_open(
        self,
        strategy_config_id: int,
        buy_date: date,
        buy_price: Decimal,
        quantity: Decimal,
        mode: StrategyMode,
    ) -> Position:
        position = Position(
            strategy_config_id=strategy_config_id,
            buy_date=buy_date,
            buy_price=buy_price,
            quantity=quantity,
            mode=mode,
            status=PositionStatus.OPEN,
        )
        self.session.add(position)
        self.session.commit()
        self.session.refresh(position)
        return position

    def get(self, position_id: int) -> Position | None:
        return self.session.get(Position, position_id)

    def close(self, position: Position) -> Position:
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.utcnow()
        return self.save(position)

    def save(self, position: Position) -> Position:
        self.session.add(position)
        self.session.commit()
        self.session.refresh(position)
        return position
