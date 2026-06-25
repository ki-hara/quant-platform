from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN


MONEY_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class LocOrder:
    step: int
    limit_price: Decimal
    quantity: int
    cumulative_quantity: int


@dataclass(frozen=True)
class LocPlan:
    limit_price: Decimal
    allocation: Decimal
    quantity: int
    estimated_fee: Decimal
    required_cash: Decimal
    available: Decimal
    blocking_reason: str | None
    orders: list[LocOrder] = field(default_factory=list)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


def calculate_loc_plan(
    previous_close: Decimal,
    capital: Decimal,
    cash: Decimal,
    fee_rate: Decimal,
    split_count: int,
    buy_threshold_percent: Decimal,
    open_position_count: int,
) -> LocPlan:
    if split_count <= 0:
        raise ValueError("split_count_must_be_positive")

    previous_close = Decimal(str(previous_close))
    capital = Decimal(str(capital))
    cash = Decimal(str(cash))
    fee_rate = Decimal(str(fee_rate))
    buy_threshold_percent = Decimal(str(buy_threshold_percent))
    split_decimal = Decimal(split_count)
    threshold_decimal = Decimal("1") + (buy_threshold_percent / Decimal("100"))
    limit_price = _money(previous_close * threshold_decimal)
    allocation = _money(capital / split_decimal)
    quantity = int((allocation / limit_price).to_integral_value(rounding=ROUND_DOWN))
    estimated_fee = _money(limit_price * Decimal(quantity) * fee_rate / Decimal("100"))
    required_cash = _money(limit_price * Decimal(quantity) + estimated_fee)
    available = _money(cash)

    if open_position_count >= split_count:
        blocking_reason = "split_limit_reached"
    elif quantity == 0:
        blocking_reason = "quantity_zero"
    elif required_cash > available:
        blocking_reason = "insufficient_cash"
    else:
        blocking_reason = None
    orders = _ladder_orders(limit_price, allocation, quantity)

    return LocPlan(
        limit_price=limit_price,
        allocation=allocation,
        quantity=quantity,
        estimated_fee=estimated_fee,
        required_cash=required_cash,
        available=available,
        blocking_reason=blocking_reason,
        orders=orders,
    )


def _ladder_orders(base_limit: Decimal, allocation: Decimal, base_quantity: int) -> list[LocOrder]:
    if base_quantity <= 0:
        return []
    floor_limit = _money(base_limit * Decimal("0.70"))
    orders = [
        LocOrder(
            step=1,
            limit_price=base_limit,
            quantity=base_quantity,
            cumulative_quantity=base_quantity,
        )
    ]
    previous_total = base_quantity
    target_total = base_quantity + 1
    while True:
        trigger_price = _money(allocation / Decimal(target_total))
        if trigger_price < floor_limit:
            break
        orders.append(
            LocOrder(
                step=len(orders) + 1,
                limit_price=trigger_price,
                quantity=target_total - previous_total,
                cumulative_quantity=target_total,
            )
        )
        previous_total = target_total
        target_total += 1
    return orders
