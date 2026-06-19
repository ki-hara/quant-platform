from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import PositionStatus, StrategyMode, TradeSide, TradeSource
from app.domain.models import LivePortfolio, Trade
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository


@dataclass(frozen=True)
class SignalExecutionRequest:
    side: TradeSide
    trade_date: date
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: TradeSource = TradeSource.SIGNAL_EXECUTION
    mode: StrategyMode = StrategyMode.SAFE
    position_id: int | None = None
    sell_reason: str | None = None


@dataclass(frozen=True)
class SignalExecutionResult:
    trade: Trade
    cash: Decimal
    realized_pnl: Decimal


class SignalExecutionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.trades = TradeRepository(session)

    def execute_signal(
        self,
        config_id: int,
        request: SignalExecutionRequest,
    ) -> SignalExecutionResult:
        try:
            self._validate_request(request)
            if self.configs.get(config_id) is None:
                raise ValueError(f"Strategy config not found: {config_id}")
            portfolio = self.portfolios.get_by_config(config_id)
            if portfolio is None:
                raise ValueError(f"Live portfolio not found for config: {config_id}")
            if request.side == TradeSide.BUY:
                result = self._buy(config_id, request, portfolio)
            elif request.side == TradeSide.SELL:
                result = self._sell(config_id, request, portfolio)
            else:
                raise ValueError(f"Unsupported trade side: {request.side}")
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def _validate_request(self, request: SignalExecutionRequest) -> None:
        if request.quantity <= 0:
            raise ValueError("quantity must be greater than zero.")
        if request.price <= 0:
            raise ValueError("price must be greater than zero.")
        if request.fee < 0:
            raise ValueError("fee must be greater than or equal to zero.")

    def _buy(
        self,
        config_id: int,
        request: SignalExecutionRequest,
        portfolio: LivePortfolio,
    ) -> SignalExecutionResult:
        gross = request.price * request.quantity
        total_cost = gross + request.fee
        if total_cost > portfolio.cash:
            raise ValueError("Insufficient cash for buy signal.")
        self.positions.create_open(
            strategy_config_id=config_id,
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
            strategy_config_id=config_id,
            trade_date=request.trade_date,
            side=TradeSide.BUY,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            realized_pnl=Decimal("0"),
            sell_reason=None,
            source=request.source,
        )
        return SignalExecutionResult(trade=trade, cash=portfolio.cash, realized_pnl=Decimal("0"))

    def _sell(
        self,
        config_id: int,
        request: SignalExecutionRequest,
        portfolio: LivePortfolio,
    ) -> SignalExecutionResult:
        if request.position_id is None:
            raise ValueError("position_id is required for sell signals.")
        position = self.positions.get(request.position_id)
        if (
            position is None
            or position.strategy_config_id != config_id
            or position.status != PositionStatus.OPEN
        ):
            raise ValueError(f"Open position not found: {request.position_id}")
        if request.quantity != position.quantity:
            raise ValueError("Sell quantity must match the open position quantity.")

        gross = request.price * request.quantity
        net_proceeds = gross - request.fee
        cost_basis = position.buy_price * position.quantity + position.buy_fee
        realized_pnl = net_proceeds - cost_basis

        self.positions.close(position)
        portfolio.cash += net_proceeds
        portfolio.realized_pnl += realized_pnl
        portfolio.cumulative_fees += request.fee
        self.portfolios.save(portfolio)
        trade = self.trades.create(
            strategy_config_id=config_id,
            trade_date=request.trade_date,
            side=TradeSide.SELL,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            realized_pnl=realized_pnl,
            sell_reason=request.sell_reason,
            source=request.source,
        )
        return SignalExecutionResult(trade=trade, cash=portfolio.cash, realized_pnl=realized_pnl)
