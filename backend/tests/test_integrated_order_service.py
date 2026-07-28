from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.domain.enums import PositionStatus, StrategyMode
from app.domain.models import Owner, Position, StrategyConfig

from app.dto.integrated_orders import IntegratedOrderSourceDto
from app.services.integrated_order_service import (
    IntegratedOrderService,
    aggregate_integrated_orders,
)


def source(config_id: int, side: str, price: str, quantity: int, tier: int | None = None):
    return IntegratedOrderSourceDto(
        strategy_config_id=config_id,
        strategy_name=f"strategy-{config_id}",
        strategy_type="radar0458_pro" if tier else "dynamic_wave",
        symbol="SOXL",
        side=side,
        limit_price=Decimal(price),
        quantity=quantity,
        tier=tier,
        radar_profile="pro1" if tier else None,
        position_id=99 if side == "sell" else None,
    )


def test_aggregate_same_symbol_side_and_price_preserves_sources_and_sorts_descending():
    rows = aggregate_integrated_orders(
        [
            source(1, "buy", "100.00", 3),
            source(2, "buy", "100.00", 5, tier=2),
            source(2, "sell", "105.00", 4, tier=1),
        ]
    )
    assert [(row.side, row.limit_price, row.quantity) for row in rows] == [
        ("sell", Decimal("105.00"), 4),
        ("buy", Decimal("100.00"), 8),
    ]
    assert [(item.strategy_config_id, item.tier, item.quantity) for item in rows[1].sources] == [
        (1, None, 3),
        (2, 2, 5),
    ]


def test_netted_orders_apply_existing_netting_after_collecting_sources():
    result = IntegratedOrderService.build_result(
        preferences=[],
        sources=[
            source(1, "buy", "100.00", 3),
            source(2, "buy", "100.00", 5, tier=2),
            source(2, "sell", "105.00", 4, tier=1),
        ],
    )
    assert [(row.side, row.limit_price, row.quantity) for row in result.netted_orders] == [
        ("sell", Decimal("105.00"), 4),
        ("buy", Decimal("100.00"), 8),
    ]
    assert {item.strategy_config_id for row in result.netted_orders for item in row.sources} == {
        1,
        2,
    }


def test_netted_orders_never_cross_symbols():
    soxl = source(1, "buy", "100.00", 3)
    tqqq = source(2, "sell", "105.00", 4)
    tqqq.symbol = "TQQQ"

    result = IntegratedOrderService.build_result(preferences=[], sources=[soxl, tqqq])

    assert {(row.symbol, row.side, row.quantity) for row in result.netted_orders} == {
        ("SOXL", "buy", 3),
        ("TQQQ", "sell", 4),
    }
    assert all(item.symbol == row.symbol for row in result.netted_orders for item in row.sources)


def test_netted_breakdown_uses_only_same_side_sources_with_exact_quantities():
    result = IntegratedOrderService.build_result(
        preferences=[],
        sources=[
            source(1, "buy", "100.00", 3),
            source(2, "buy", "100.00", 5, tier=2),
            source(3, "sell", "105.00", 4, tier=1),
        ],
    )

    for row in result.netted_orders:
        assert {item.side for item in row.sources} == {row.side}
        assert sum(item.quantity for item in row.sources) == row.quantity
    buy = next(row for row in result.netted_orders if row.side == "buy")
    sell = next(row for row in result.netted_orders if row.side == "sell")
    assert [(item.strategy_config_id, item.quantity) for item in buy.sources] == [(1, 3), (2, 5)]
    assert [(item.strategy_config_id, item.quantity) for item in sell.sources] == [(3, 4)]


def test_netted_breakdown_splits_source_quantity_across_multiple_rows():
    buy = source(1, "buy", "100.00", 8, tier=2)
    sell = source(2, "sell", "95.00", 4, tier=1)

    result = IntegratedOrderService.build_result(preferences=[], sources=[buy, sell])

    buy_rows = [row for row in result.netted_orders if row.side == "buy"]
    assert [(row.limit_price, row.quantity) for row in buy_rows] == [
        (Decimal("100.00"), 4),
        (Decimal("94.99"), 4),
    ]
    assert [row.sources[0].quantity for row in buy_rows] == [4, 4]
    assert all(row.sources[0].limit_price == Decimal("100.00") for row in buy_rows)
    assert all(row.sources[0].strategy_config_id == 1 for row in buy_rows)
    assert all(
        sum(item.quantity for item in row.sources) == row.quantity for row in result.netted_orders
    )
    assert all({item.side for item in row.sources} == {row.side} for row in result.netted_orders)


def test_all_open_positions_with_valid_sell_loc_targets_are_sell_sources():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Owner(id="owner", name="Owner", is_active=True))
        config = StrategyConfig(
            owner_id="owner",
            name="Radar",
            strategy_type="radar0458_pro",
            symbol="SOXL",
            initial_capital=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            settings_json={"pro_profile": "pro1"},
        )
        session.add(config)
        session.flush()
        session.add_all(
            [
                Position(
                    strategy_config_id=config.id,
                    buy_date=date(2026, 7, 1),
                    buy_price=Decimal("100"),
                    buy_fee=Decimal("0"),
                    quantity=Decimal("4"),
                    mode=StrategyMode.SAFE,
                    sell_limit_price=Decimal("150"),
                    radar_tier=2,
                    radar_profile="pro1",
                    status=PositionStatus.OPEN,
                ),
                Position(
                    strategy_config_id=config.id,
                    buy_date=date(2026, 7, 2),
                    buy_price=Decimal("100"),
                    buy_fee=Decimal("0"),
                    quantity=Decimal("7"),
                    mode=StrategyMode.SAFE,
                    sell_limit_price=Decimal("151"),
                    radar_tier=3,
                    radar_profile="pro1",
                    status=PositionStatus.PENDING,
                ),
            ]
        )
        session.commit()

        sources = IntegratedOrderService(session)._sell_sources(config)

    assert [(item.side, item.limit_price, item.quantity, item.tier) for item in sources] == [
        ("sell", Decimal("150"), 4, 2)
    ]


def test_netted_breakdown_allocates_deterministically_across_multi_price_sources():
    result = IntegratedOrderService.build_result(
        preferences=[],
        sources=[
            source(1, "buy", "101.00", 3, tier=1),
            source(2, "buy", "100.00", 5, tier=2),
            source(3, "sell", "95.00", 4, tier=3),
        ],
    )

    buy_rows = [row for row in result.netted_orders if row.side == "buy"]
    sell_rows = [row for row in result.netted_orders if row.side == "sell"]
    assert [
        [(item.strategy_config_id, item.limit_price, item.quantity) for item in row.sources]
        for row in buy_rows
    ] == [
        [(1, Decimal("101.00"), 3), (2, Decimal("100.00"), 1)],
        [(2, Decimal("100.00"), 4)],
    ]
    assert [
        [(item.strategy_config_id, item.limit_price, item.quantity) for item in row.sources]
        for row in sell_rows
    ] == [
        [(3, Decimal("95.00"), 3)],
        [(3, Decimal("95.00"), 1)],
    ]
    assert all(
        sum(item.quantity for item in row.sources) == row.quantity for row in result.netted_orders
    )
