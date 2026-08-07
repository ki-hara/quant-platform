from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP


CENT = Decimal("0.01")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class GoldToiletCalculation:
    breakout_buy_price: Decimal
    loc_buy_price: Decimal
    order_quantity: int
    allocation_amount: Decimal
    required_reservation_cash: Decimal
    cash_warning: bool


def calculate_gold_toilet_order(
    *,
    capital: Decimal,
    cash: Decimal,
    market_open: Decimal,
    entry_percent: Decimal,
    allocation_percent: Decimal,
    loc_percent: Decimal,
) -> GoldToiletCalculation:
    breakout_buy_price = _money(
        market_open * (Decimal("1") + entry_percent / HUNDRED)
    )
    loc_buy_price = _money(market_open * (Decimal("1") + loc_percent / HUNDRED))
    allocation_amount = _money(capital * allocation_percent / HUNDRED)
    quantity_price = min(breakout_buy_price, loc_buy_price)
    order_quantity = int(
        (allocation_amount / quantity_price).to_integral_value(rounding=ROUND_FLOOR)
    )
    required_reservation_cash = _money(
        Decimal(order_quantity) * (breakout_buy_price + loc_buy_price)
    )
    return GoldToiletCalculation(
        breakout_buy_price=breakout_buy_price,
        loc_buy_price=loc_buy_price,
        order_quantity=order_quantity,
        allocation_amount=allocation_amount,
        required_reservation_cash=required_reservation_cash,
        cash_warning=required_reservation_cash > cash,
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
