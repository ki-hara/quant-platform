from datetime import date
from decimal import Decimal

from app.backtest_engine.simulator import DailySnapshot, SimulatedTrade


MONEY_QUANT = Decimal("0.000001")


def total_return(initial_capital: Decimal, final_asset: Decimal) -> Decimal:
    if initial_capital == 0:
        return Decimal("0")
    return ((final_asset - initial_capital) / initial_capital).quantize(MONEY_QUANT)


def cagr(initial_capital: Decimal, final_asset: Decimal, start_date: date, end_date: date) -> Decimal:
    if initial_capital <= 0 or final_asset <= 0:
        return Decimal("0")
    days = (end_date - start_date).days
    if days <= 0:
        return Decimal("0")
    years = Decimal(days) / Decimal("365")
    rate = (float(final_asset / initial_capital) ** (1 / float(years))) - 1
    return Decimal(str(rate)).quantize(MONEY_QUANT)


def mdd(snapshots: list[DailySnapshot]) -> Decimal:
    if not snapshots:
        return Decimal("0")
    return min(snapshot.drawdown for snapshot in snapshots).quantize(MONEY_QUANT)


def win_rate(trades: list[SimulatedTrade]) -> Decimal:
    sells = [trade for trade in trades if trade.side == "SELL"]
    if not sells:
        return Decimal("0")
    wins = sum(1 for trade in sells if trade.realized_pnl > 0)
    return (Decimal(wins) / Decimal(len(sells))).quantize(MONEY_QUANT)


def total_trades(trades: list[SimulatedTrade]) -> int:
    return len(trades)


def average_holding_days(trades: list[SimulatedTrade]) -> Decimal:
    holding_days = [
        Decimal(trade.holding_days)
        for trade in trades
        if trade.side == "SELL" and trade.holding_days is not None
    ]
    if not holding_days:
        return Decimal("0")
    return (sum(holding_days) / Decimal(len(holding_days))).quantize(MONEY_QUANT)


def cumulative_fees(trades: list[SimulatedTrade]) -> Decimal:
    return sum((trade.fee for trade in trades), Decimal("0")).quantize(MONEY_QUANT)
