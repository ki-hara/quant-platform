from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.domain.enums import PositionStatus, StrategyMode, TradeSide, TradeSource
from app.domain.models import (
    LivePortfolio,
    LocOrder,
    PortfolioAdjustment,
    Position,
    StrategyConfig,
    Trade,
)
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.position_exit_policy import build_position_exit_policy
from app.strategy_engine.radar0458_pro import get_radar_preset


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
    limit_price: Decimal | None = None
    radar_tier: int | None = None
    radar_profile: str | None = None
    radar_cycle_id: str | None = None
    radar_cycle_capital: Decimal | None = None
    sell_threshold_percent: Decimal | None = None
    sell_limit_price: Decimal | None = None
    max_holding_days: int | None = None


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

    def record_manual_trade(
        self,
        request: ManualTradeRequest,
        *,
        commit: bool = True,
    ) -> ManualTradeResult:
        try:
            self._validate_request(request)
            config = self.configs.get(request.config_id)
            if config is None:
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
                result = self._buy(request, portfolio, config)
            elif request.side == TradeSide.SELL:
                result = self._sell(request, portfolio, config)
            else:
                raise ValidationAppError(
                    "unsupported_trade_side",
                    f"Unsupported trade side: {request.side}",
                )
            if commit:
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
            config = self.configs.get(trade.strategy_config_id)
            if config is None:
                raise NotFoundError(
                    "strategy_config_not_found",
                    f"Strategy config not found: {trade.strategy_config_id}",
                )
            portfolio = self.portfolios.get_by_config(trade.strategy_config_id)
            if portfolio is None:
                raise NotFoundError(
                    "live_portfolio_not_found",
                    f"Live portfolio not found for config: {trade.strategy_config_id}",
                )
            linked_orders = self.session.scalars(
                select(LocOrder).where(LocOrder.trade_id == trade.id)
            ).all()
            for order in linked_orders:
                order.trade_id = None
                self.session.add(order)
            self.trades.delete(trade)
            self._rebuild_live_ledger(config, portfolio)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _validate_request(self, request: ManualTradeRequest) -> None:
        if request.quantity <= 0:
            raise ValidationAppError("invalid_manual_trade", "quantity must be greater than zero.")
        if request.price <= 0:
            raise ValidationAppError("invalid_manual_trade", "price must be greater than zero.")
        if request.limit_price is not None and request.limit_price <= 0:
            raise ValidationAppError(
                "invalid_manual_trade", "limit_price must be greater than zero."
            )
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

    def _buy(
        self,
        request: ManualTradeRequest,
        portfolio: LivePortfolio,
        config: StrategyConfig,
    ) -> ManualTradeResult:
        gross = request.price * request.quantity
        total_cost = gross + request.fee
        if total_cost > portfolio.cash:
            raise ValidationAppError("insufficient_cash", "Insufficient cash for manual buy.")

        if config.strategy_type == "radar0458_pro":
            required = (
                request.radar_tier,
                request.radar_profile,
                request.radar_cycle_id,
                request.radar_cycle_capital,
            )
            if any(value is None for value in required):
                raise ValidationAppError(
                    "radar_position_snapshot_missing",
                    "Radar position snapshot metadata is required.",
                )
            preset = get_radar_preset(request.radar_profile)
            sell_threshold_percent = preset.sell_threshold_percent
            sell_limit_price = (
                request.price * (Decimal("1") + sell_threshold_percent / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            max_holding_days = preset.max_holding_days
        else:
            radar_values = (
                request.radar_tier,
                request.radar_profile,
                request.radar_cycle_id,
                request.radar_cycle_capital,
                request.sell_threshold_percent,
                request.sell_limit_price,
                request.max_holding_days,
            )
            if any(value is not None for value in radar_values):
                raise ValidationAppError(
                    "invalid_strategy_snapshot",
                    "Radar position snapshots are not valid for this strategy.",
                )
            exit_policy = build_position_exit_policy(
                config.settings_json, request.mode, request.price
            )
            sell_threshold_percent = exit_policy.sell_threshold_percent
            sell_limit_price = exit_policy.sell_limit_price
            max_holding_days = exit_policy.max_holding_days
        position = self.positions.create_open(
            strategy_config_id=request.config_id,
            buy_date=request.trade_date,
            buy_price=request.price,
            quantity=request.quantity,
            mode=request.mode,
            buy_fee=request.fee,
            limit_price=request.limit_price,
            sell_threshold_percent=sell_threshold_percent,
            sell_limit_price=sell_limit_price,
            max_holding_days=max_holding_days,
            radar_tier=request.radar_tier,
            radar_profile=request.radar_profile,
            radar_cycle_id=request.radar_cycle_id,
            radar_cycle_capital=request.radar_cycle_capital,
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
            limit_price=request.limit_price,
            position_id=position.id,
        )
        return ManualTradeResult(trade=trade, cash=portfolio.cash, realized_pnl=Decimal("0"))

    def _matching_open_buy_position(self, trade: Trade) -> Position | None:
        for position in self.positions.list_open(trade.strategy_config_id):
            if (
                position.buy_date == trade.date
                and position.buy_price == trade.price
                and position.quantity == trade.quantity
                and position.buy_fee == trade.fee
                and position.limit_price == trade.limit_price
            ):
                return position
        return None

    def _rebuild_live_ledger(self, config: StrategyConfig, portfolio: LivePortfolio) -> None:
        existing_positions = self.positions.list_by_strategy_config(config.id)
        snapshots = {
            position.id: {
                "position_id": position.id,
                "buy_date": position.buy_date,
                "buy_price": position.buy_price,
                "buy_fee": position.buy_fee,
                "limit_price": position.limit_price,
                "quantity": position.quantity,
                "mode": position.mode,
                "sell_threshold_percent": position.sell_threshold_percent,
                "sell_limit_price": position.sell_limit_price,
                "max_holding_days": position.max_holding_days,
                "radar_tier": position.radar_tier,
                "radar_profile": position.radar_profile,
                "radar_cycle_id": position.radar_cycle_id,
                "radar_cycle_capital": position.radar_cycle_capital,
            }
            for position in existing_positions
        }
        loc_orders = list(
            self.session.scalars(select(LocOrder).where(LocOrder.strategy_config_id == config.id))
        )
        loc_order_position_ids = {
            order.id: order.position_id for order in loc_orders if order.position_id is not None
        }
        for order in loc_orders:
            if order.position_id is not None:
                order.position_id = None
                self.session.add(order)
        trades = self.trades.list_by_strategy_config(config.id)
        trade_position_ids = {trade.id: trade.position_id for trade in trades}
        for trade in trades:
            trade.position_id = None
            self.session.add(trade)
        self.session.flush()
        pending_positions = [
            snapshots[position.id]
            for position in existing_positions
            if position.status == PositionStatus.PENDING
        ]
        self.positions.delete_by_strategy_config(config.id)
        portfolio.capital = config.initial_capital
        portfolio.cash = config.initial_capital
        portfolio.realized_pnl = Decimal("0")
        portfolio.cumulative_fees = Decimal("0")
        self._replay_portfolio_adjustments(config.id, portfolio)
        open_positions: list[Position] = []
        rebuilt_positions: dict[int, Position] = {}
        for trade in trades:
            if trade.side == TradeSide.BUY:
                old_position_id = trade_position_ids[trade.id]
                snapshot = snapshots.get(old_position_id)
                position = self.positions.create_open(
                    strategy_config_id=config.id,
                    buy_date=trade.date,
                    buy_price=trade.price,
                    quantity=trade.quantity,
                    mode=snapshot["mode"] if snapshot else StrategyMode.SAFE,
                    buy_fee=trade.fee,
                    limit_price=trade.limit_price,
                    sell_threshold_percent=(
                        snapshot["sell_threshold_percent"] if snapshot else None
                    ),
                    sell_limit_price=snapshot["sell_limit_price"] if snapshot else None,
                    max_holding_days=snapshot["max_holding_days"] if snapshot else None,
                    radar_tier=snapshot["radar_tier"] if snapshot else None,
                    radar_profile=snapshot["radar_profile"] if snapshot else None,
                    radar_cycle_id=snapshot["radar_cycle_id"] if snapshot else None,
                    radar_cycle_capital=snapshot["radar_cycle_capital"] if snapshot else None,
                )
                if old_position_id is not None:
                    rebuilt_positions[old_position_id] = position
                trade.position_id = position.id
                self.session.add(trade)
                open_positions.append(position)
                portfolio.cash -= trade.price * trade.quantity + trade.fee
                portfolio.cumulative_fees += trade.fee
            elif trade.side == TradeSide.SELL:
                old_position_id = trade_position_ids[trade.id]
                rebuilt_position = rebuilt_positions.get(old_position_id)
                if old_position_id is not None and rebuilt_position is None:
                    raise ValidationAppError(
                        "position_replay_mismatch",
                        f"Linked position cannot be rebuilt for sell trade: {trade.id}",
                    )
                trade.position_id = rebuilt_position.id if rebuilt_position is not None else None
                realized_pnl = self._replay_sell(
                    trade, open_positions, target_position=rebuilt_position
                )
                trade.realized_pnl = realized_pnl
                portfolio.cash += trade.price * trade.quantity - trade.fee
                portfolio.realized_pnl += realized_pnl
                if config.strategy_type == "radar0458_pro":
                    portfolio.capital = (portfolio.capital + realized_pnl).quantize(MONEY_QUANT)
                portfolio.cumulative_fees += trade.fee
                self.session.add(trade)
        for pending in pending_positions:
            rebuilt_pending = self.positions.create_pending(
                strategy_config_id=config.id,
                buy_date=pending["buy_date"],
                limit_price=pending["limit_price"] or pending["buy_price"],
                quantity=pending["quantity"],
                mode=pending["mode"],
                radar_tier=pending["radar_tier"],
                radar_profile=pending["radar_profile"],
                radar_cycle_id=pending["radar_cycle_id"],
                radar_cycle_capital=pending["radar_cycle_capital"],
                sell_threshold_percent=pending["sell_threshold_percent"],
                sell_limit_price=pending["sell_limit_price"],
                max_holding_days=pending["max_holding_days"],
            )
            rebuilt_positions[pending["position_id"]] = rebuilt_pending
        for order_id, old_position_id in loc_order_position_ids.items():
            rebuilt_position = rebuilt_positions.get(old_position_id)
            if rebuilt_position is not None:
                self.session.execute(
                    update(LocOrder)
                    .where(LocOrder.id == order_id)
                    .values(position_id=rebuilt_position.id)
                )
        self.portfolios.save(portfolio)

    def _replay_portfolio_adjustments(self, config_id: int, portfolio: LivePortfolio) -> None:
        stmt = (
            select(PortfolioAdjustment)
            .where(PortfolioAdjustment.strategy_config_id == config_id)
            .order_by(PortfolioAdjustment.date, PortfolioAdjustment.id)
        )
        for adjustment in self.session.scalars(stmt):
            portfolio.cash = (portfolio.cash + adjustment.cash_delta).quantize(MONEY_QUANT)
            portfolio.capital = (portfolio.capital + adjustment.capital_delta).quantize(MONEY_QUANT)

    def _replay_sell(
        self,
        trade: Trade,
        open_positions: list[Position],
        target_position: Position | None = None,
    ) -> Decimal:
        if target_position is not None and target_position not in open_positions:
            raise ValidationAppError(
                "position_replay_mismatch",
                f"Linked position is not open for sell trade: {trade.id}",
            )
        remaining_quantity = trade.quantity
        realized_pnl = Decimal("0")
        candidates = [target_position] if target_position is not None else list(open_positions)
        for position in candidates:
            if remaining_quantity <= 0:
                break
            sell_quantity = min(remaining_quantity, position.quantity)
            allocated_buy_fee = (position.buy_fee * sell_quantity / position.quantity).quantize(
                MONEY_QUANT
            )
            cost_basis = position.buy_price * sell_quantity + allocated_buy_fee
            proceeds = trade.price * sell_quantity - (
                trade.fee * sell_quantity / trade.quantity
            ).quantize(MONEY_QUANT)
            realized_pnl += proceeds - cost_basis
            remaining_quantity -= sell_quantity
            if sell_quantity == position.quantity:
                self.positions.close(position)
                open_positions.remove(position)
            else:
                position.quantity = (position.quantity - sell_quantity).quantize(MONEY_QUANT)
                position.buy_fee = (position.buy_fee - allocated_buy_fee).quantize(MONEY_QUANT)
                self.positions.save(position)
        if remaining_quantity > 0:
            raise ValidationAppError(
                "position_replay_mismatch",
                f"Sell trade quantity exceeds rebuilt positions: {trade.id}",
            )
        return realized_pnl.quantize(MONEY_QUANT)

    def _sell(
        self, request: ManualTradeRequest, portfolio: LivePortfolio, config: StrategyConfig
    ) -> ManualTradeResult:
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
        allocated_buy_fee = (position.buy_fee * request.quantity / original_quantity).quantize(
            MONEY_QUANT
        )
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
        if config.strategy_type == "radar0458_pro":
            portfolio.capital = (portfolio.capital + realized_pnl).quantize(MONEY_QUANT)
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
            position_id=position.id,
            entry_date=position.buy_date,
            entry_price=position.buy_price,
        )
        return ManualTradeResult(trade=trade, cash=portfolio.cash, realized_pnl=realized_pnl)
