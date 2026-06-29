from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.backtest_engine import metrics
from app.backtest_engine.simulator import (
    BacktestResult,
    BacktestSummary,
    DailySnapshot,
    SimulatedTrade,
)
from app.dto.market_data import OhlcvDto
from app.domain.enums import BacktestModePolicy, StrategyMode
from app.strategy_engine.base import Strategy
from app.strategy_engine.context import StrategyContext, StrategyPosition
from app.strategy_engine.weekly_rsi import DailyClose, WeeklyRsiTransition, aggregate_daily_closes_to_weekly_closes, resolve_weekly_rsi_transition


MONEY_QUANT = Decimal("0.000001")


@dataclass
class _OpenPosition:
    position_id: int
    buy_date: date
    buy_price: Decimal
    quantity: int
    mode: StrategyMode
    buy_fee: Decimal
    buy_trading_day_index: int

    def as_strategy_position(self, current_trading_day_index: int | None = None) -> StrategyPosition:
        holding_days = None
        if current_trading_day_index is not None:
            holding_days = max(current_trading_day_index - self.buy_trading_day_index, 0)
        return StrategyPosition(
            buy_date=self.buy_date,
            buy_price=self.buy_price,
            quantity=self.quantity,
            mode=self.mode,
            holding_days=holding_days,
        )


class BacktestEngine:
    def run(
        self,
        strategy: Strategy,
        prices: list[OhlcvDto],
        initial_capital: Decimal,
        fee_rate: Decimal,
        slippage_rate: Decimal,
        settings: dict,
        lookahead_date: date | None = None,
        mode_policy: BacktestModePolicy = BacktestModePolicy.FIXED_SAFE,
        rsi_prices: list[OhlcvDto] | None = None,
    ) -> BacktestResult:
        sorted_prices = sorted(prices, key=lambda price: price.date)
        if len(sorted_prices) < 2:
            raise ValueError("Backtest requires at least two price rows.")
        mode_schedule = self._build_mode_schedule(mode_policy, rsi_prices or [])

        cash = initial_capital
        capital = initial_capital
        cumulative_fees = Decimal("0")
        interval_realized_pnl = Decimal("0")
        peak_asset = initial_capital
        next_position_id = 1
        open_positions: list[_OpenPosition] = []
        trades: list[SimulatedTrade] = []
        snapshots: list[DailySnapshot] = []

        for index, price in enumerate(sorted_prices):
            previous_close = sorted_prices[index - 1].close if index > 0 else price.close
            effective_mode, mode_rule_code = self._mode_for_date(
                price.date,
                mode_policy,
                mode_schedule,
            )
            context = self._build_context(
                price=price,
                previous_close=previous_close,
                capital=capital,
                cash=cash,
                open_positions=open_positions,
                settings=settings,
                trading_day_index=index,
                effective_mode=effective_mode,
            )

            if index > 0:
                cash, cumulative_fees, realized_today, sell_trades = self._sell_positions(
                    strategy=strategy,
                    context=context,
                    positions=open_positions,
                    cash=cash,
                    current_close=price.close,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    cumulative_fees=cumulative_fees,
                )
                trades.extend(sell_trades)
                interval_realized_pnl += realized_today

                context = self._build_context(
                    price=price,
                    previous_close=previous_close,
                    capital=capital,
                    cash=cash,
                    open_positions=open_positions,
                    settings=settings,
                    trading_day_index=index,
                    effective_mode=effective_mode,
                )
                buy_signal = strategy.should_buy(context)
                if buy_signal.should_buy:
                    mode = strategy.get_mode(context)
                    size = strategy.calculate_position_size(context)
                    if size.quantity > 0:
                        buy_price = self._apply_buy_slippage(price.close, slippage_rate)
                        transaction_amount = buy_price * Decimal(size.quantity)
                        fee = self._fee(transaction_amount, fee_rate)
                        total_cost = transaction_amount + fee
                        if total_cost <= cash:
                            cash -= total_cost
                            cumulative_fees += fee
                            position = _OpenPosition(
                                position_id=next_position_id,
                                buy_date=price.date,
                                buy_price=buy_price,
                                quantity=size.quantity,
                                mode=mode,
                                buy_fee=fee,
                                buy_trading_day_index=index,
                            )
                            open_positions.append(position)
                            trades.append(
                                SimulatedTrade(
                                    date=price.date,
                                    side="BUY",
                                    quantity=size.quantity,
                                    price=buy_price.quantize(MONEY_QUANT),
                                    fee=fee.quantize(MONEY_QUANT),
                                    realized_pnl=Decimal("0"),
                                    position_id=next_position_id,
                                )
                            )
                            next_position_id += 1

                if (
                    self._is_capital_update_due(
                        settings,
                        index,
                        sorted_prices,
                        lookahead_date,
                    )
                    and interval_realized_pnl != 0
                ):
                    context = self._build_context(
                        price=price,
                        previous_close=previous_close,
                        capital=capital,
                        cash=cash,
                        open_positions=open_positions,
                        settings=settings,
                        trading_day_index=index,
                        effective_mode=effective_mode,
                    )
                    capital = strategy.update_capital(context, interval_realized_pnl).capital
                    interval_realized_pnl = Decimal("0")

            position_value = self._position_value(open_positions, price.close)
            total_asset = cash + position_value
            if total_asset > peak_asset:
                peak_asset = total_asset
            drawdown = self._drawdown(total_asset, peak_asset)
            snapshots.append(
                DailySnapshot(
                    date=price.date,
                    capital=capital.quantize(MONEY_QUANT),
                    cash=cash.quantize(MONEY_QUANT),
                    position_value=position_value.quantize(MONEY_QUANT),
                    total_asset=total_asset.quantize(MONEY_QUANT),
                    drawdown=drawdown,
                    cumulative_fees=cumulative_fees.quantize(MONEY_QUANT),
                    mode=effective_mode,
                    mode_rule_code=mode_rule_code,
                )
            )

        final_asset = snapshots[-1].total_asset
        summary = BacktestSummary(
            cagr=metrics.cagr(initial_capital, final_asset, snapshots[0].date, snapshots[-1].date),
            mdd=metrics.mdd(snapshots),
            final_asset=final_asset,
            total_return=metrics.total_return(initial_capital, final_asset),
            win_rate=metrics.win_rate(trades),
            total_trades=metrics.total_trades(trades),
            average_holding_days=metrics.average_holding_days(trades),
            cumulative_fees=metrics.cumulative_fees(trades),
        )
        return BacktestResult(snapshots, trades, summary)

    def _build_context(
        self,
        price: OhlcvDto,
        previous_close: Decimal,
        capital: Decimal,
        cash: Decimal,
        open_positions: list[_OpenPosition],
        settings: dict,
        trading_day_index: int,
        effective_mode: StrategyMode,
    ) -> StrategyContext:
        return StrategyContext(
            current_date=price.date,
            previous_close=previous_close,
            current_close=price.close,
            capital=capital,
            cash=cash,
            open_positions=[
                position.as_strategy_position(trading_day_index)
                for position in open_positions
            ],
            settings=settings,
            trading_day_index=trading_day_index,
            effective_mode=effective_mode,
        )

    def _build_mode_schedule(
        self,
        mode_policy: BacktestModePolicy,
        rsi_prices: list[OhlcvDto],
    ) -> list[WeeklyRsiTransition]:
        if mode_policy is not BacktestModePolicy.WEEKLY_RSI:
            return []
        weekly_closes = aggregate_daily_closes_to_weekly_closes(
            [DailyClose(date=price.date, close=price.close) for price in rsi_prices]
        )
        schedule: list[WeeklyRsiTransition] = []
        prior_mode = StrategyMode.SAFE
        for end_index in range(16, len(weekly_closes) + 1):
            transition = resolve_weekly_rsi_transition(
                weekly_closes[:end_index],
                prior_mode=prior_mode,
            )
            if transition is None:
                continue
            prior_mode = transition.recommended_mode
            schedule.append(transition)
        return schedule

    def _mode_for_date(
        self,
        current_date: date,
        mode_policy: BacktestModePolicy,
        mode_schedule: list[WeeklyRsiTransition],
    ) -> tuple[StrategyMode, str | None]:
        if mode_policy is BacktestModePolicy.FIXED_AGGRESSIVE:
            return StrategyMode.AGGRESSIVE, BacktestModePolicy.FIXED_AGGRESSIVE.value
        if mode_policy is BacktestModePolicy.FIXED_SAFE:
            return StrategyMode.SAFE, BacktestModePolicy.FIXED_SAFE.value

        active_transition: WeeklyRsiTransition | None = None
        for transition in mode_schedule:
            if transition.effective_week <= current_date:
                active_transition = transition
            else:
                break
        if active_transition is None:
            return StrategyMode.SAFE, None
        return active_transition.recommended_mode, active_transition.rule_code

    def _sell_positions(
        self,
        strategy: Strategy,
        context: StrategyContext,
        positions: list[_OpenPosition],
        cash: Decimal,
        current_close: Decimal,
        fee_rate: Decimal,
        slippage_rate: Decimal,
        cumulative_fees: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal, list[SimulatedTrade]]:
        remaining_positions: list[_OpenPosition] = []
        trades: list[SimulatedTrade] = []
        realized_today = Decimal("0")

        for position in positions:
            strategy_position = position.as_strategy_position(context.trading_day_index)
            signal = strategy.should_sell(context, strategy_position)
            if not signal.should_sell:
                remaining_positions.append(position)
                continue

            sell_price = self._apply_sell_slippage(current_close, slippage_rate)
            transaction_amount = sell_price * Decimal(position.quantity)
            fee = self._fee(transaction_amount, fee_rate)
            net_proceeds = transaction_amount - fee
            cost_basis = position.buy_price * Decimal(position.quantity) + position.buy_fee
            realized_pnl = net_proceeds - cost_basis
            holding_days = strategy_position.holding_days
            if holding_days is None:
                holding_days = max((context.current_date - position.buy_date).days, 0)

            cash += net_proceeds
            cumulative_fees += fee
            realized_today += realized_pnl
            trades.append(
                SimulatedTrade(
                    date=context.current_date,
                    side="SELL",
                    quantity=position.quantity,
                    price=sell_price.quantize(MONEY_QUANT),
                    fee=fee.quantize(MONEY_QUANT),
                    realized_pnl=realized_pnl.quantize(MONEY_QUANT),
                    sell_reason=signal.reason,
                    position_id=position.position_id,
                    holding_days=holding_days,
                )
            )

        positions[:] = remaining_positions
        return cash, cumulative_fees, realized_today, trades

    def _is_capital_update_due(
        self,
        settings: dict,
        trading_day_index: int,
        prices: list[OhlcvDto],
        lookahead_date: date | None,
    ) -> bool:
        schedule = settings.get("capital_update", {})
        if trading_day_index <= 0:
            return False
        if schedule.get("type") == "trading_days":
            interval = int(schedule.get("interval", 0))
            return interval > 0 and trading_day_index % interval == 0
        if schedule.get("type") == "calendar":
            period = schedule.get("period")
            if period not in {"monthly", "quarterly", "yearly"}:
                return False
            return self._is_last_available_period_day(
                prices,
                trading_day_index,
                period,
                lookahead_date,
            )
        return False

    def _is_last_available_period_day(
        self,
        prices: list[OhlcvDto],
        trading_day_index: int,
        period: str,
        lookahead_date: date | None,
    ) -> bool:
        next_date = (
            prices[trading_day_index + 1].date
            if trading_day_index < len(prices) - 1
            else lookahead_date
        )
        if next_date is None:
            return False
        current_key = self._period_key(prices[trading_day_index].date, period)
        next_key = self._period_key(next_date, period)
        return current_key != next_key

    def _period_key(self, value: date, period: str) -> tuple[int, int]:
        if period == "monthly":
            return (value.year, value.month)
        if period == "quarterly":
            return (value.year, (value.month - 1) // 3 + 1)
        return (value.year, 1)

    def _apply_buy_slippage(self, price: Decimal, slippage_rate: Decimal) -> Decimal:
        return price * (Decimal("1") + slippage_rate / Decimal("100"))

    def _apply_sell_slippage(self, price: Decimal, slippage_rate: Decimal) -> Decimal:
        return price * (Decimal("1") - slippage_rate / Decimal("100"))

    def _fee(self, transaction_amount: Decimal, fee_rate: Decimal) -> Decimal:
        return transaction_amount * fee_rate / Decimal("100")

    def _position_value(self, positions: list[_OpenPosition], close: Decimal) -> Decimal:
        return sum((close * Decimal(position.quantity) for position in positions), Decimal("0"))

    def _drawdown(self, total_asset: Decimal, peak_asset: Decimal) -> Decimal:
        if peak_asset == 0:
            return Decimal("0")
        return ((total_asset - peak_asset) / peak_asset).quantize(MONEY_QUANT)
