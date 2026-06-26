from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import LocOrderStatus, TradeSide, TradeSource
from app.domain.models import LocOrder
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.daily_plan_service import DailyPlanService
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.market_session_service import current_market_date


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
        plan = DailyPlanService(self.session).get_daily_plan(config_id, current_market_date(config.symbol))
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
        self.session.commit()
        self.session.refresh(order)
        return order

    def fill_order(self, order_id: int, request: LocOrderFillRequest) -> LocOrder:
        order = self._get_order(order_id)
        if order.status != LocOrderStatus.PENDING:
            raise ValueError("Only pending LOC orders can be filled.")
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
            )
        )
        order.status = LocOrderStatus.FILLED
        order.trade_id = result.trade.id
        order.memo = request.memo or order.memo
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        return order

    def mark_unfilled(self, order_id: int) -> LocOrder:
        order = self._get_order(order_id)
        if order.status != LocOrderStatus.PENDING:
            raise ValueError("Only pending LOC orders can be marked unfilled.")
        order.status = LocOrderStatus.UNFILLED
        self.session.add(order)
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
            order.status = LocOrderStatus.UNFILLED
            self.session.add(order)
            changed = True
        if changed:
            self.session.commit()

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
