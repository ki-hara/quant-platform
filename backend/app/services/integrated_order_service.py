from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import PositionStatus
from app.domain.models import IntegratedOrderPreference, Position
from app.dto.integrated_orders import (
    IntegratedOrderDto,
    IntegratedOrderPreferenceDto,
    IntegratedOrderSourceDto,
    IntegratedOrdersResponseDto,
)
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.daily_plan_service import DailyPlanService
from app.services.position_exit_policy import build_position_exit_policy
from app.strategy_engine.loc_netting import LocOrderInput, net_loc_orders


class IntegratedOrderService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)

    def get_orders(self, owner_id: str) -> IntegratedOrdersResponseDto:
        configs = self.configs.list_by_owner(owner_id)
        stored = (
            {
                item.strategy_config_id: item
                for item in self.session.scalars(
                    select(IntegratedOrderPreference).where(
                        IntegratedOrderPreference.strategy_config_id.in_(
                            [config.id for config in configs]
                        )
                    )
                )
            }
            if configs
            else {}
        )
        preferences = [
            IntegratedOrderPreferenceDto(
                strategy_config_id=config.id,
                strategy_name=config.name,
                strategy_type=config.strategy_type,
                symbol=config.symbol,
                included=stored.get(config.id).included if config.id in stored else False,
            )
            for config in configs
        ]
        sources: list[IntegratedOrderSourceDto] = []
        for config in configs:
            if not preferences[configs.index(config)].included:
                continue
            sources.extend(self._buy_sources(config))
            sources.extend(self._sell_sources(config))
        return self.build_result(preferences, sources)

    def set_preference(
        self, owner_id: str, config_id: int, included: bool
    ) -> IntegratedOrderPreferenceDto:
        config = self.configs.get(config_id)
        if config is None or config.owner_id != owner_id:
            raise ValueError(f"Strategy config not found: {config_id}")
        preference = self.session.get(IntegratedOrderPreference, config_id)
        if preference is None:
            preference = IntegratedOrderPreference(strategy_config_id=config_id)
        preference.included = included
        preference.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(preference)
        self.session.commit()
        return IntegratedOrderPreferenceDto(
            strategy_config_id=config.id,
            strategy_name=config.name,
            strategy_type=config.strategy_type,
            symbol=config.symbol,
            included=preference.included,
        )

    def _buy_sources(self, config) -> list[IntegratedOrderSourceDto]:
        plan = DailyPlanService(self.session).get_daily_plan(config.id)
        if not plan.buy_available or plan.LOC.blocking_reason is not None:
            return []
        order_rows = plan.LOC.orders or [plan.LOC]
        return [
            IntegratedOrderSourceDto(
                strategy_config_id=config.id,
                strategy_name=config.name,
                strategy_type=config.strategy_type,
                symbol=config.symbol,
                side="buy",
                limit_price=row.limit_price,
                quantity=int(row.quantity),
                tier=plan.radar_tier,
                radar_profile=plan.radar_profile,
            )
            for row in order_rows
            if int(row.quantity) > 0
        ]

    def _sell_sources(self, config) -> list[IntegratedOrderSourceDto]:
        positions = self.session.scalars(
            select(Position).where(
                Position.strategy_config_id == config.id,
                Position.status == PositionStatus.OPEN,
            )
        )
        result = []
        for position in positions:
            limit_price = position.sell_limit_price
            if limit_price is None and config.strategy_type != "radar0458_pro":
                limit_price = build_position_exit_policy(
                    config.settings_json, position.mode, position.buy_price
                ).sell_limit_price
            if limit_price is None or int(position.quantity) <= 0:
                continue
            result.append(
                IntegratedOrderSourceDto(
                    strategy_config_id=config.id,
                    strategy_name=config.name,
                    strategy_type=config.strategy_type,
                    symbol=config.symbol,
                    side="sell",
                    limit_price=limit_price,
                    quantity=int(position.quantity),
                    tier=position.radar_tier,
                    radar_profile=position.radar_profile,
                    position_id=position.id,
                )
            )
        return result

    @staticmethod
    def build_result(preferences, sources) -> IntegratedOrdersResponseDto:
        original = aggregate_integrated_orders(sources)
        sources_by_symbol: dict[str, list[IntegratedOrderSourceDto]] = {}
        for source in sources:
            sources_by_symbol.setdefault(source.symbol, []).append(source)

        netted_rows = []
        for symbol, symbol_sources in sources_by_symbol.items():
            netted = net_loc_orders(
                [
                    LocOrderInput(
                        side=source.side,
                        limit_price=source.limit_price,
                        quantity=source.quantity,
                    )
                    for source in symbol_sources
                ],
                Decimal("0.01"),
            )
            symbol_rows = [
                IntegratedOrderDto(
                    symbol=symbol,
                    side=row.side,
                    limit_price=row.limit_price,
                    quantity=row.quantity,
                    sources=[],
                )
                for row in netted
            ]
            symbol_rows.sort(key=lambda row: row.limit_price, reverse=True)
            _allocate_netted_sources(symbol_rows, symbol_sources)
            netted_rows.extend(symbol_rows)
        netted_rows.sort(key=lambda row: row.limit_price, reverse=True)
        return IntegratedOrdersResponseDto(
            preferences=preferences,
            original_orders=original,
            netted_orders=netted_rows,
        )


def aggregate_integrated_orders(
    sources: list[IntegratedOrderSourceDto],
) -> list[IntegratedOrderDto]:
    grouped: dict[tuple[str, str, Decimal], list[IntegratedOrderSourceDto]] = {}
    for source in sources:
        grouped.setdefault((source.symbol, source.side, source.limit_price), []).append(source)
    rows = [
        IntegratedOrderDto(
            symbol=symbol,
            side=side,
            limit_price=price,
            quantity=sum(item.quantity for item in items),
            sources=items,
        )
        for (symbol, side, price), items in grouped.items()
    ]
    return sorted(rows, key=lambda row: row.limit_price, reverse=True)


def _allocate_netted_sources(
    rows: list[IntegratedOrderDto],
    sources: list[IntegratedOrderSourceDto],
) -> None:
    for side in ("buy", "sell"):
        pool = sorted(
            (source.model_copy() for source in sources if source.side == side),
            key=lambda source: (
                -source.limit_price,
                source.strategy_config_id,
                source.position_id or 0,
                source.tier or 0,
            ),
        )
        source_index = 0
        source_remaining = pool[0].quantity if pool else 0
        for row in (item for item in rows if item.side == side):
            needed = row.quantity
            allocated = []
            while needed > 0:
                if source_index >= len(pool):
                    raise ValueError(f"Insufficient {side} sources for netted order.")
                amount = min(needed, source_remaining)
                allocated.append(pool[source_index].model_copy(update={"quantity": amount}))
                needed -= amount
                source_remaining -= amount
                if source_remaining == 0:
                    source_index += 1
                    source_remaining = (
                        pool[source_index].quantity if source_index < len(pool) else 0
                    )
            row.sources = allocated
        if source_index < len(pool) or source_remaining:
            raise ValueError(f"Unallocated {side} sources remain after netting.")
