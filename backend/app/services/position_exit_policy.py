from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.enums import StrategyMode

MONEY_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class PositionExitPolicy:
    sell_threshold_percent: Decimal
    sell_limit_price: Decimal
    max_holding_days: int


def build_position_exit_policy(
    settings: dict[str, Any],
    mode: StrategyMode,
    buy_price: Decimal,
) -> PositionExitPolicy:
    mode_settings = settings[mode.value]
    sell_threshold_percent = Decimal(str(mode_settings["sell_threshold_percent"]))
    sell_limit_price = (
        buy_price * (Decimal("1") + sell_threshold_percent / Decimal("100"))
    ).quantize(MONEY_QUANT)
    return PositionExitPolicy(
        sell_threshold_percent=sell_threshold_percent,
        sell_limit_price=sell_limit_price,
        max_holding_days=int(mode_settings["max_holding_days"]),
    )


def sell_limit_price_for(buy_price: Decimal, sell_threshold_percent: Decimal) -> Decimal:
    return (
        buy_price * (Decimal("1") + sell_threshold_percent / Decimal("100"))
    ).quantize(MONEY_QUANT)