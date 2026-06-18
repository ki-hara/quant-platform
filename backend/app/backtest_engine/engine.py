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
from app.domain.enums import StrategyMode
from app.strategy_engine.base import Strategy
from app.strategy_engine.context import StrategyContext, StrategyPosition


MONEY_QUANT = Decimal("0.000001")


@dataclass
class _OpenPosition:
    position_id: int
    buy_date: date
    buy_price: Decimal
    quantity: int
    mode: StrategyMode
    buy_fee: Decimal

    def as_strategy_position(self) -> StrategyPosition:
        return StrategyPosition(
            buy_date=self.buy_date,
            buy_price=self.buy_price,
            quantity=self.quantity,
            mode=self.mode,
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
    ) -> BacktestResult:
        sorted_prices = sorted(prices, key=lambda price: price.date)
        if len(sorted_prices) < 2:
            raise ValueError("Backtest requires at least two price rows.")

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
            context = self._build_context(
                price=price,
                previous_close=previous_close,
                capital=capital,
                cash=cash,
                open_positions=open_positions,
                settings=settings,
                trading_day_index=index,
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

                if self._is_capital_update_due(settings, index) and interval_realized_pnl != 0:
                    context = self._build_context(
                        price=price,
                        previous_close=previous_close,
                        capital=capital,
                        cash=cash,
                        open_positions=open_positions,
                        settings=settings,
                        trading_day_index=index,
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
    ) -> StrategyContext:
        return StrategyContext(
            current_date=price.date,
            previous_close=previous_close,
            current_close=price.close,
            capital=capital,
            cash=cash,
            open_positions=[position.as_strategy_position() for position in open_positions],
            settings=settings,
            trading_day_index=trading_day_index,
        )

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
            signal = strategy.should_sell(context, position.as_strategy_position())
            if not signal.should_sell:
                remaining_positions.append(position)
                continue

            sell_price = self._apply_sell_slippage(current_close, slippage_rate)
            transaction_amount = sell_price * Decimal(position.quantity)
            fee = self._fee(transaction_amount, fee_rate)
            net_proceeds = transaction_amount - fee
            cost_basis = position.buy_price * Decimal(position.quantity) + position.buy_fee
            realized_pnl = net_proceeds - cost_basis
            holding_days = (context.current_date - position.buy_date).days

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

    def _is_capital_update_due(self, settings: dict, trading_day_index: int) -> bool:
        schedule = settings.get("capital_update", {})
        if schedule.get("type") != "trading_days":
            return False
        interval = int(schedule.get("interval", 0))
        return interval > 0 and trading_day_index > 0 and trading_day_index % interval == 0

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
