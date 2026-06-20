from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


MONEY_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class AodPlan:
    limit_price: Decimal
    allocation: Decimal
    quantity: int
    estimated_fee: Decimal
    required_cash: Decimal
    available: Decimal
    blocking_reason: str | None


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


def calculate_aod_plan(
    previous_close: Decimal,
    capital: Decimal,
    cash: Decimal,
    fee_rate: Decimal,
    split_count: int,
    buy_threshold_percent: Decimal,
    open_position_count: int,
) -> AodPlan:
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

    return AodPlan(
        limit_price=limit_price,
        allocation=allocation,
        quantity=quantity,
        estimated_fee=estimated_fee,
        required_cash=required_cash,
        available=available,
        blocking_reason=blocking_reason,
    )
