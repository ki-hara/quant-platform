from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.domain.enums import PositionStatus, StrategyMode, TradeSide, TradeSource
from app.domain.models import LivePortfolio, Position, Trade
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository


MONEY_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class ManualTradeRequest:
    config_id: int
    side: TradeSide
    trade_date: date
    quantity: Decimal
    price: Decimal
    fee: Decimal
    sell_reason: str | None = None
    source: TradeSource = TradeSource.MANUAL
    mode: StrategyMode = StrategyMode.SAFE
    position_id: int | None = None


@dataclass(frozen=True)
class ManualTradeResult:
    trade: Trade
    cash: Decimal
    realized_pnl: Decimal


class ManualTradeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.trades = TradeRepository(session)

    def record_manual_trade(self, request: ManualTradeRequest) -> ManualTradeResult:
        try:
            self._validate_request(request)
            if self.configs.get(request.config_id) is None:
                raise NotFoundError(
                    "strategy_config_not_found",
                    f"Strategy config not found: {request.config_id}",
                )
            portfolio = self.portfolios.get_by_config(request.config_id)
            if portfolio is None:
                raise NotFoundError(
                    "live_portfolio_not_found",
                    f"Live portfolio not found for config: {request.config_id}",
                )
            if request.side == TradeSide.BUY:
                result = self._buy(request, portfolio)
            elif request.side == TradeSide.SELL:
                result = self._sell(request, portfolio)
            else:
                raise ValidationAppError(
                    "unsupported_trade_side",
                    f"Unsupported trade side: {request.side}",
                )
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def delete_trade(self, trade_id: int) -> None:
        try:
            trade = self.trades.get(trade_id)
            if trade is None:
                raise NotFoundError("trade_not_found", f"Trade not found: {trade_id}")
            if trade.source not in (TradeSource.MANUAL, TradeSource.CORRECTION):
                raise ValidationAppError(
                    "trade_delete_not_allowed",
                    "Only manual or correction trades can be deleted.",
                )
            if trade.side != TradeSide.BUY:
                raise ValidationAppError(
                    "trade_delete_not_allowed",
                    "Sell trades cannot be safely deleted. Record a correction trade instead.",
                )
            portfolio = self.portfolios.get_by_config(trade.strategy_config_id)
            if portfolio is None:
                raise NotFoundError(
                    "live_portfolio_not_found",
                    f"Live portfolio not found for config: {trade.strategy_config_id}",
                )
            position = self._matching_open_buy_position(trade)
            if position is None:
                raise ValidationAppError(
                    "trade_delete_not_allowed",
                    "This buy trade no longer has an unchanged open position.",
                )
            portfolio.cash += trade.price * trade.quantity + trade.fee
            portfolio.cumulative_fees -= trade.fee
            self.session.delete(position)
            self.portfolios.save(portfolio)
            self.trades.delete(trade)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _validate_request(self, request: ManualTradeRequest) -> None:
        if request.quantity <= 0:
            raise ValidationAppError("invalid_manual_trade", "quantity must be greater than zero.")
        if request.price <= 0:
            raise ValidationAppError("invalid_manual_trade", "price must be greater than zero.")
        if request.fee < 0:
            raise ValidationAppError(
                "invalid_manual_trade",
                "fee must be greater than or equal to zero.",
            )
        if request.source not in (TradeSource.MANUAL, TradeSource.CORRECTION):
            raise ValidationAppError(
                "invalid_manual_trade_source",
                "source must be manual or correction.",
            )

    def _buy(self, request: ManualTradeRequest, portfolio: LivePortfolio) -> ManualTradeResult:
        gross = request.price * request.quantity
        total_cost = gross + request.fee
        if total_cost > portfolio.cash:
            raise ValidationAppError("insufficient_cash", "Insufficient cash for manual buy.")

        self.positions.create_open(
            strategy_config_id=request.config_id,
            buy_date=request.trade_date,
            buy_price=request.price,
            quantity=request.quantity,
            mode=request.mode,
            buy_fee=request.fee,
        )
        portfolio.cash -= total_cost
        portfolio.cumulative_fees += request.fee
        self.portfolios.save(portfolio)
        trade = self.trades.create(
            strategy_config_id=request.config_id,
            trade_date=request.trade_date,
            side=TradeSide.BUY,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            realized_pnl=Decimal("0"),
            sell_reason=None,
            source=request.source,
        )
        return ManualTradeResult(trade=trade, cash=portfolio.cash, realized_pnl=Decimal("0"))

    def _matching_open_buy_position(self, trade: Trade) -> Position | None:
        for position in self.positions.list_open(trade.strategy_config_id):
            if (
                position.buy_date == trade.date
                and position.buy_price == trade.price
                and position.quantity == trade.quantity
                and position.buy_fee == trade.fee
            ):
                return position
        return None

    def _sell(self, request: ManualTradeRequest, portfolio: LivePortfolio) -> ManualTradeResult:
        if request.position_id is None:
            raise ValidationAppError(
                "position_required",
                "position_id is required for a manual sell.",
            )

        gross = request.price * request.quantity
        net_proceeds = gross - request.fee

        position = self.positions.get(request.position_id)
        if position is None:
            raise NotFoundError(
                "open_position_not_found",
                f"Open position not found: {request.position_id}",
            )
        if position.strategy_config_id != request.config_id:
            raise ValidationAppError(
                "position_config_mismatch",
                f"Position does not belong to strategy config: {request.position_id}",
            )
        if position.status != PositionStatus.OPEN:
            raise ValidationAppError(
                "position_not_open",
                f"Position is not open: {request.position_id}",
            )
        if request.quantity > position.quantity:
            raise ValidationAppError(
                "invalid_manual_trade",
                "Sell quantity cannot exceed the open position quantity.",
            )

        original_quantity = position.quantity
        allocated_buy_fee = (
            position.buy_fee * request.quantity / original_quantity
        ).quantize(MONEY_QUANT)
        cost_basis = position.buy_price * request.quantity + allocated_buy_fee
        realized_pnl = (net_proceeds - cost_basis).quantize(MONEY_QUANT)
        if request.quantity == original_quantity:
            self.positions.close(position)
        else:
            position.quantity = (original_quantity - request.quantity).quantize(MONEY_QUANT)
            position.buy_fee = (position.buy_fee - allocated_buy_fee).quantize(MONEY_QUANT)
            self.positions.save(position)

        portfolio.cash += net_proceeds
        portfolio.realized_pnl += realized_pnl
        portfolio.cumulative_fees += request.fee
        self.portfolios.save(portfolio)
        trade = self.trades.create(
            strategy_config_id=request.config_id,
            trade_date=request.trade_date,
            side=TradeSide.SELL,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            realized_pnl=realized_pnl,
            sell_reason=request.sell_reason,
            source=request.source,
        )
        return ManualTradeResult(trade=trade, cash=portfolio.cash, realized_pnl=realized_pnl)
