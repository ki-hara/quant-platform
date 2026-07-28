from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.enums import LocOrderStatus, TradeSide, TradeSource
from app.domain.models import LocOrder, Position
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.daily_plan_service import DailyPlanService
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.market_session_service import current_market_date
from app.strategy_engine.radar0458_pro import get_radar_preset


@dataclass(frozen=True)
class LocOrderFillRequest:
    quantity: Decimal
    price: Decimal
    fee: Decimal
    memo: str | None = None


class LocOrderService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)

    def list_orders(self, config_id: int) -> list[LocOrder]:
        config = self._get_config(config_id)
        self._expire_old_pending(config_id, current_market_date(config.symbol))
        stmt = (
            select(LocOrder)
            .where(LocOrder.strategy_config_id == config_id)
            .order_by(LocOrder.order_date.desc(), LocOrder.id.desc())
        )
        return list(self.session.scalars(stmt))

    def create_from_daily_plan(self, config_id: int, memo: str | None = None) -> LocOrder:
        config = self._get_config(config_id)
        plan = DailyPlanService(self.session).get_daily_plan(
            config_id, current_market_date(config.symbol)
        )
        if plan.LOC.blocking_reason is not None:
            raise ValueError(f"LOC buy order unavailable: {plan.LOC.blocking_reason}")
        if plan.LOC.quantity <= 0:
            raise ValueError("LOC quantity must be greater than zero.")
        order = LocOrder(
            strategy_config_id=config_id,
            order_date=current_market_date(config.symbol),
            symbol=config.symbol,
            limit_price=plan.LOC.limit_price,
            recommended_quantity=Decimal(plan.LOC.quantity),
            mode=plan.confirmed_mode,
            status=LocOrderStatus.PENDING,
            memo=memo,
        )
        self.session.add(order)
        if config.strategy_type == "radar0458_pro":
            preset = get_radar_preset(plan.radar_profile)
            sell_limit = (
                plan.LOC.limit_price
                * (Decimal("1") + preset.sell_threshold_percent / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            pending_position = PositionRepository(self.session).create_pending(
                strategy_config_id=config_id,
                buy_date=order.order_date,
                limit_price=order.limit_price,
                quantity=order.recommended_quantity,
                mode=order.mode,
                radar_tier=plan.radar_tier,
                radar_profile=plan.radar_profile,
                radar_cycle_id=plan.radar_cycle_id,
                radar_cycle_capital=plan.radar_cycle_capital,
                sell_threshold_percent=preset.sell_threshold_percent,
                sell_limit_price=sell_limit,
                max_holding_days=preset.max_holding_days,
            )
            order.position_id = pending_position.id
        self.session.commit()
        self.session.refresh(order)
        return order

    def fill_order(self, order_id: int, request: LocOrderFillRequest) -> LocOrder:
        try:
            order = self._get_order(order_id)
            if order.status != LocOrderStatus.PENDING:
                raise ValueError("Only pending LOC orders can be filled.")
            radar_position = None
            if self._get_config(order.strategy_config_id).strategy_type == "radar0458_pro":
                radar_position = self._linked_pending_position(order)
                if radar_position is None:
                    raise ValueError("radar_position_snapshot_missing")
                self.session.delete(radar_position)
            result = ManualTradeService(self.session).record_manual_trade(
                ManualTradeRequest(
                    config_id=order.strategy_config_id,
                    side=TradeSide.BUY,
                    trade_date=order.order_date,
                    quantity=request.quantity,
                    price=request.price,
                    fee=request.fee,
                    limit_price=order.limit_price,
                    source=TradeSource.MANUAL,
                    mode=order.mode,
                    radar_tier=radar_position.radar_tier if radar_position else None,
                    radar_profile=radar_position.radar_profile if radar_position else None,
                    radar_cycle_id=radar_position.radar_cycle_id if radar_position else None,
                    radar_cycle_capital=radar_position.radar_cycle_capital
                    if radar_position
                    else None,
                    sell_threshold_percent=radar_position.sell_threshold_percent
                    if radar_position
                    else None,
                    sell_limit_price=radar_position.sell_limit_price if radar_position else None,
                    max_holding_days=radar_position.max_holding_days if radar_position else None,
                ),
                commit=False,
            )
            transition = self.session.execute(
                update(LocOrder)
                .where(
                    LocOrder.id == order.id,
                    LocOrder.status == LocOrderStatus.PENDING,
                )
                .values(
                    status=LocOrderStatus.FILLED,
                    trade_id=result.trade.id,
                    position_id=result.trade.position_id,
                    memo=request.memo or order.memo,
                )
                .execution_options(synchronize_session=False)
            )
            if transition.rowcount != 1:
                raise ValueError("Only pending LOC orders can be filled.")
            self.session.commit()
            self.session.refresh(order)
            return order
        except Exception:
            self.session.rollback()
            raise

    def mark_unfilled(self, order_id: int) -> LocOrder:
        order = self._get_order(order_id)
        if order.status != LocOrderStatus.PENDING:
            raise ValueError("Only pending LOC orders can be marked unfilled.")
        order.status = LocOrderStatus.UNFILLED
        self.session.add(order)
        config = self._get_config(order.strategy_config_id)
        if config.strategy_type == "radar0458_pro":
            self._delete_linked_pending_position(order)
        self.session.commit()
        self.session.refresh(order)
        return order

    def _expire_old_pending(self, config_id: int, today) -> None:
        stmt = select(LocOrder).where(
            LocOrder.strategy_config_id == config_id,
            LocOrder.status == LocOrderStatus.PENDING,
            LocOrder.order_date < today,
        )
        changed = False
        for order in self.session.scalars(stmt):
            if order.position_id is not None:
                self._delete_linked_pending_position(order)
            order.status = LocOrderStatus.UNFILLED
            self.session.add(order)
            changed = True
        if changed:
            self.session.commit()

    def _linked_pending_position(self, order: LocOrder) -> Position | None:
        if order.position_id is None:
            return None
        position = self.session.get(Position, order.position_id)
        if (
            position is None
            or position.strategy_config_id != order.strategy_config_id
            or position.status.value != "pending"
        ):
            return None
        return position

    def _delete_linked_pending_position(self, order: LocOrder) -> None:
        position = self._linked_pending_position(order)
        if position is not None:
            self.session.delete(position)
        order.position_id = None

    def _get_config(self, config_id: int):
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config

    def _get_order(self, order_id: int) -> LocOrder:
        order = self.session.get(LocOrder, order_id)
        if order is None:
            raise ValueError(f"LOC order not found: {order_id}")
        return order
