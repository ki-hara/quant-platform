from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.domain.enums import StrategyMode


@dataclass(frozen=True)
class StrategyPosition:
    buy_date: date
    buy_price: Decimal
    quantity: int
    mode: StrategyMode
    holding_days: int | None = None


@dataclass(frozen=True)
class StrategyContext:
    current_date: date
    previous_close: Decimal
    current_close: Decimal
    capital: Decimal
    cash: Decimal
    open_positions: list[StrategyPosition]
    settings: dict[str, Any]
    trading_day_index: int
    effective_mode: StrategyMode = StrategyMode.SAFE
