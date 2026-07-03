from decimal import Decimal

from app.strategy_engine.loc_netting import LocOrderInput, net_loc_orders


def _plain(orders):
    return [(order.side, order.limit_price, order.quantity) for order in orders]


def test_net_loc_orders_converts_crossed_buy_and_sell_pair() -> None:
    orders = net_loc_orders(
        [
            LocOrderInput(side="sell", limit_price=Decimal("65.00"), quantity=15),
            LocOrderInput(side="buy", limit_price=Decimal("70.00"), quantity=10),
        ],
        tick_size=Decimal("0.01"),
    )

    assert _plain(orders) == [
        ("sell", Decimal("70.01"), 10),
        ("buy", Decimal("64.99"), 10),
        ("sell", Decimal("65.00"), 5),
    ]


def test_net_loc_orders_handles_multiple_crossed_levels() -> None:
    orders = net_loc_orders(
        [
            LocOrderInput(side="buy", limit_price=Decimal("6.00"), quantity=6),
            LocOrderInput(side="sell", limit_price=Decimal("5.00"), quantity=2),
            LocOrderInput(side="buy", limit_price=Decimal("4.00"), quantity=4),
            LocOrderInput(side="sell", limit_price=Decimal("3.00"), quantity=6),
            LocOrderInput(side="buy", limit_price=Decimal("2.00"), quantity=3),
            LocOrderInput(side="sell", limit_price=Decimal("1.00"), quantity=1),
        ],
        tick_size=Decimal("0.01"),
    )

    assert _plain(orders) == [
        ("sell", Decimal("6.01"), 6),
        ("sell", Decimal("5.00"), 2),
        ("buy", Decimal("4.00"), 3),
        ("sell", Decimal("4.01"), 1),
        ("buy", Decimal("2.99"), 6),
        ("buy", Decimal("2.00"), 3),
        ("buy", Decimal("0.99"), 1),
    ]


def test_net_loc_orders_preserves_non_crossed_orders() -> None:
    orders = net_loc_orders(
        [
            LocOrderInput(side="sell", limit_price=Decimal("70.00"), quantity=2),
            LocOrderInput(side="buy", limit_price=Decimal("65.00"), quantity=3),
        ],
        tick_size=Decimal("0.01"),
    )

    assert _plain(orders) == [
        ("sell", Decimal("70.00"), 2),
        ("buy", Decimal("65.00"), 3),
    ]
