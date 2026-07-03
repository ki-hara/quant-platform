from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


LocSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class LocOrderInput:
    side: LocSide
    limit_price: Decimal
    quantity: int


@dataclass(frozen=True)
class NettedLocOrder:
    side: LocSide
    limit_price: Decimal
    quantity: int


def net_loc_orders(orders: list[LocOrderInput], tick_size: Decimal) -> list[NettedLocOrder]:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive.")

    buy_by_price: dict[Decimal, int] = {}
    sell_by_price: dict[Decimal, int] = {}
    for order in orders:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive.")
        if order.limit_price <= 0:
            raise ValueError("limit_price must be positive.")
        target = buy_by_price if order.side == "buy" else sell_by_price
        target[order.limit_price] = target.get(order.limit_price, 0) + order.quantity

    prices = sorted(set(buy_by_price) | set(sell_by_price), reverse=True)
    net_quantity = -sum(sell_by_price.values())
    result: list[NettedLocOrder] = []

    for price in prices:
        buy_quantity = buy_by_price.get(price, 0)
        if buy_quantity:
            next_net_quantity = net_quantity + buy_quantity
            _append_transition_orders(
                result,
                before=net_quantity,
                after=next_net_quantity,
                sell_price=price + tick_size,
                buy_price=price,
            )
            net_quantity = next_net_quantity

        sell_quantity = sell_by_price.get(price, 0)
        if sell_quantity:
            next_net_quantity = net_quantity + sell_quantity
            _append_transition_orders(
                result,
                before=net_quantity,
                after=next_net_quantity,
                sell_price=price,
                buy_price=price - tick_size,
            )
            net_quantity = next_net_quantity

    return [order for order in result if order.quantity > 0]


def _append_transition_orders(
    result: list[NettedLocOrder],
    before: int,
    after: int,
    sell_price: Decimal,
    buy_price: Decimal,
) -> None:
    if after == before:
        return
    if before < 0 and after > 0:
        result.append(NettedLocOrder("buy", buy_price, min(after, after - before)))
        result.append(NettedLocOrder("sell", sell_price, min(-before, after - before)))
        return
    if before < 0:
        result.append(NettedLocOrder("sell", sell_price, min(-before, after - before)))
    if after > 0:
        result.append(NettedLocOrder("buy", buy_price, min(after, after - before)))
