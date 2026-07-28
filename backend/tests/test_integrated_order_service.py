from decimal import Decimal

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
