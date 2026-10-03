from copy import deepcopy
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.domain.enums import PositionStatus
from app.domain.models import OrderSnapshot, StrategyConfig
from app.core.config import settings
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.portfolios import PositionRepository
from app.services.daily_plan_service import DailyPlanService
from app.services.dashboard_service import DashboardService
from app.services.position_exit_policy import build_position_exit_policy
from app.strategy_engine.loc_netting import LocOrderInput, net_loc_orders


def json_value(value):
    if isinstance(value, (date, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


class OrderSnapshotService:
    def __init__(self, session):
        self.session = session

    def create(self, config_id: int, sizing_policy: str = "fixed_quantity") -> OrderSnapshot:
        config = self.session.get(StrategyConfig, config_id)
        if config is None or config.strategy_type != "dynamic_wave":
            raise ValueError("동파법 전략만 정산할 수 있습니다.")
        plan = DailyPlanService(self.session).get_daily_plan(config_id, position_sizing_policy=sizing_policy)
        positions = PositionRepository(self.session).list_open(config_id)
        prices = MarketPriceRepository(self.session).list_prices(
            settings.market_data_provider, config.symbol, date.min, plan.market_data_as_of or date.min
        )
        signals = DashboardService(self.session)._signals(config, config.live_portfolio, positions, prices)
        by_id = {s["position_id"]: s for s in (signals.sell_signals or [])}
        sources = []
        if plan.buy_available and plan.LOC.blocking_reason is None:
            for index, row in enumerate(plan.LOC.orders or [plan.LOC]):
                if row.quantity:
                    sources.append(dict(id=f"buy:{index}", side="buy", quantity=row.quantity,
                                        limit_price=row.limit_price, execution="loc", position_id=None,
                                        mode=plan.confirmed_mode.value))
        for position in positions:
            if position.status != PositionStatus.OPEN:
                continue
            policy = build_position_exit_policy(config.settings_json, position.mode, position.buy_price)
            signal = by_id.get(position.id, {})
            due = signal.get("days_to_deadline") is not None and signal["days_to_deadline"] <= 0
            sources.append(dict(id=f"sell:{position.id}", side="sell", quantity=int(position.quantity),
                                position_id=position.id, buy_date=position.buy_date,
                                buy_price=position.buy_price, mode=position.mode.value,
                                limit_price=position.sell_limit_price or policy.sell_limit_price,
                                execution="market_on_close" if due else "loc"))
        netted = net_loc_orders([
            LocOrderInput(s["side"], s["limit_price"], s["quantity"], s["execution"]) for s in sources
        ], Decimal("0.01")) if sources else []
        snapshot = OrderSnapshot(config_id=config_id, trade_date=plan.plan_date, payload_json=json_value({
            "symbol": config.symbol, "settings": deepcopy(config.settings_json),
            "mode": plan.confirmed_mode.value, "plan": plan.model_dump(mode="json"),
            "sources": sources, "netted": [asdict(row) for row in netted],
        }))
        self.session.add(snapshot)
        self.session.commit()
        return snapshot

    def list(self, config_id: int, trade_date: date | None = None):
        query = select(OrderSnapshot).where(OrderSnapshot.config_id == config_id)
        if trade_date:
            query = query.where(OrderSnapshot.trade_date == trade_date)
        return list(self.session.scalars(query.order_by(OrderSnapshot.id.desc())))
