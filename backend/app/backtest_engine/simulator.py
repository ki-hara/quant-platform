from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import StrategyMode


@dataclass(frozen=True)
class SimulatedTrade:
    date: date
    side: str
    quantity: int
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal
    sell_reason: str | None = None
    position_id: int | None = None
    holding_days: int | None = None


@dataclass(frozen=True)
class DailySnapshot:
    date: date
    capital: Decimal
    cash: Decimal
    position_value: Decimal
    total_asset: Decimal
    drawdown: Decimal
    cumulative_fees: Decimal
    mode: StrategyMode = StrategyMode.SAFE
    mode_rule_code: str | None = None


@dataclass(frozen=True)
class BacktestSummary:
    cagr: Decimal
    mdd: Decimal
    final_asset: Decimal
    total_return: Decimal
    win_rate: Decimal
    total_trades: int
    average_holding_days: Decimal
    cumulative_fees: Decimal


@dataclass(frozen=True)
class BacktestResult:
    daily_snapshots: list[DailySnapshot]
    trades: list[SimulatedTrade]
    summary: BacktestSummary
