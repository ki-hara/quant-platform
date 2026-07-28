from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.backtest_engine import metrics
from app.backtest_engine.simulator import (
    BacktestResult,
    BacktestSummary,
    DailySnapshot,
    SimulatedTrade,
)
from app.domain.enums import StrategyMode
from app.dto.market_data import OhlcvDto
from app.strategy_engine.radar0458_pro import build_radar_buy_plan, get_radar_preset

MONEY_QUANT = Decimal("0.000001")


@dataclass
class RadarBacktestPosition:
    position_id: int
    buy_date: date
    buy_price: Decimal
    quantity: int
    buy_fee: Decimal
    buy_trading_day_index: int
    tier: int
    profile: str
    cycle_capital: Decimal
    sell_threshold_percent: Decimal
    max_holding_days: int


def run_radar_backtest(
    engine,
    prices: list[OhlcvDto],
    initial_capital: Decimal,
    fee_rate: Decimal,
    slippage_rate: Decimal,
    settings: dict,
) -> BacktestResult:
    cash = capital = initial_capital
    fees = Decimal("0")
    peak = initial_capital
    next_id = 1
    positions: list[RadarBacktestPosition] = []
    trades: list[SimulatedTrade] = []
    snapshots: list[DailySnapshot] = []
    configured_profile = str(settings.get("pro_profile", "pro1"))
    profile_schedule = settings.get("pro_profile_schedule", {})
    for index, price in enumerate(prices):
        scheduled_profile = profile_schedule.get(price.date.isoformat())
        if scheduled_profile is not None:
            configured_profile = str(scheduled_profile)
        previous_close = prices[index - 1].close if index else price.close
        if index:
            active = positions[0] if positions else None
            profile = active.profile if active else configured_profile
            cycle_capital = active.cycle_capital if active else capital
            plan = build_radar_buy_plan(
                previous_close, cycle_capital, cash, {p.tier for p in positions}, profile
            )
            start_count = len(positions)
            remaining = []
            sold_count = 0
            for position in positions:
                sell_limit = (
                    position.buy_price
                    * (Decimal("1") + position.sell_threshold_percent / Decimal("100"))
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                holding_days = index - position.buy_trading_day_index
                if price.close < sell_limit and holding_days < position.max_holding_days:
                    remaining.append(position)
                    continue
                sell_price = engine._apply_sell_slippage(price.close, slippage_rate)
                amount = sell_price * position.quantity
                fee = engine._fee(amount, fee_rate)
                proceeds = amount - fee
                realized = proceeds - (position.buy_price * position.quantity + position.buy_fee)
                cash += proceeds
                capital += realized
                fees += fee
                sold_count += 1
                trades.append(
                    SimulatedTrade(
                        date=price.date,
                        side="SELL",
                        quantity=position.quantity,
                        price=sell_price.quantize(MONEY_QUANT),
                        fee=fee.quantize(MONEY_QUANT),
                        realized_pnl=realized.quantize(MONEY_QUANT),
                        sell_reason="profit_target"
                        if price.close >= sell_limit
                        else "max_holding_period",
                        position_id=position.position_id,
                        holding_days=holding_days,
                        open_position_count=start_count - sold_count,
                        cash_after=cash.quantize(MONEY_QUANT),
                        capital_after=capital.quantize(MONEY_QUANT),
                        radar_tier=position.tier,
                        radar_profile=position.profile,
                        radar_cycle_capital=position.cycle_capital,
                    )
                )
            positions = remaining
            if (
                plan.blocking_reason is None
                and price.close <= plan.limit_price
                and plan.tier is not None
            ):
                buy_price = engine._apply_buy_slippage(price.close, slippage_rate)
                amount = buy_price * plan.quantity
                fee = engine._fee(amount, fee_rate)
                if plan.quantity > 0 and amount + fee <= cash:
                    cash -= amount + fee
                    fees += fee
                    preset = get_radar_preset(plan.profile)
                    positions.append(
                        RadarBacktestPosition(
                            next_id,
                            price.date,
                            buy_price,
                            plan.quantity,
                            fee,
                            index,
                            plan.tier,
                            plan.profile,
                            plan.cycle_capital,
                            preset.sell_threshold_percent,
                            preset.max_holding_days,
                        )
                    )
                    trades.append(
                        SimulatedTrade(
                            date=price.date,
                            side="BUY",
                            quantity=plan.quantity,
                            price=buy_price.quantize(MONEY_QUANT),
                            fee=fee.quantize(MONEY_QUANT),
                            realized_pnl=Decimal("0"),
                            position_id=next_id,
                            open_position_count=len(positions),
                            cash_after=cash.quantize(MONEY_QUANT),
                            capital_after=capital.quantize(MONEY_QUANT),
                            radar_tier=plan.tier,
                            radar_profile=plan.profile,
                            radar_cycle_capital=plan.cycle_capital,
                        )
                    )
                    next_id += 1
        position_value = sum((price.close * p.quantity for p in positions), Decimal("0"))
        total_asset = cash + position_value
        peak = max(peak, total_asset)
        snapshots.append(
            DailySnapshot(
                price.date,
                capital.quantize(MONEY_QUANT),
                cash.quantize(MONEY_QUANT),
                position_value.quantize(MONEY_QUANT),
                total_asset.quantize(MONEY_QUANT),
                engine._drawdown(total_asset, peak),
                fees.quantize(MONEY_QUANT),
                StrategyMode.SAFE,
                None,
            )
        )
    final_asset = snapshots[-1].total_asset
    summary = BacktestSummary(
        metrics.cagr(initial_capital, final_asset, snapshots[0].date, snapshots[-1].date),
        metrics.mdd(snapshots),
        final_asset,
        metrics.total_return(initial_capital, final_asset),
        metrics.win_rate(trades),
        metrics.total_trades(trades),
        metrics.average_holding_days(trades),
        metrics.cumulative_fees(trades),
    )
    return BacktestResult(snapshots, trades, summary)
