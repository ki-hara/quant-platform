from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.backtest_engine.simulator import DailySnapshot, SimulatedTrade
from app.domain.enums import BacktestStatus, TradeSide, TradeSource
from app.domain.models import BacktestDailySnapshot, BacktestRun, BacktestTrade


class BacktestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        owner_id: str,
        strategy_config_snapshot_json: dict[str, Any],
        start_date: date,
        end_date: date,
        status: BacktestStatus,
        initial_capital: Decimal,
        final_capital: Decimal,
        total_return: Decimal,
        max_drawdown: Decimal,
        win_rate: Decimal,
        total_trades: int,
        error_message: str | None = None,
    ) -> BacktestRun:
        run = BacktestRun(
            owner_id=owner_id,
            strategy_config_snapshot_json=strategy_config_snapshot_json,
            start_date=start_date,
            end_date=end_date,
            status=status,
            error_message=error_message,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
        )
        self.session.add(run)
        self.session.flush()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: int) -> BacktestRun | None:
        return self.session.get(BacktestRun, run_id)

    def add_daily_snapshots(
        self,
        backtest_run_id: int,
        snapshots: list[DailySnapshot],
    ) -> list[BacktestDailySnapshot]:
        rows = [
            BacktestDailySnapshot(
                backtest_run_id=backtest_run_id,
                date=snapshot.date,
                capital=snapshot.capital,
                cash=snapshot.cash,
                position_value=snapshot.position_value,
                total_asset=snapshot.total_asset,
                drawdown=snapshot.drawdown,
                cumulative_fees=snapshot.cumulative_fees,
                mode=snapshot.mode,
                mode_rule_code=snapshot.mode_rule_code,
            )
            for snapshot in snapshots
        ]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def add_trades(
        self,
        backtest_run_id: int,
        trades: list[SimulatedTrade],
    ) -> list[BacktestTrade]:
        rows = [
            BacktestTrade(
                backtest_run_id=backtest_run_id,
                date=trade.date,
                side=self._trade_side(trade.side),
                quantity=Decimal(trade.quantity),
                price=trade.price,
                fee=trade.fee,
                realized_pnl=trade.realized_pnl,
                sell_reason=trade.sell_reason,
                source=TradeSource.SIGNAL_EXECUTION,
            )
            for trade in trades
        ]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def _trade_side(self, side: str) -> TradeSide:
        normalized = side.lower()
        if normalized == TradeSide.BUY.value:
            return TradeSide.BUY
        if normalized == TradeSide.SELL.value:
            return TradeSide.SELL
        raise ValueError(f"Unknown trade side: {side}")
