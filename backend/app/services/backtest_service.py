from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.backtest_engine.engine import BacktestEngine
from app.domain.enums import BacktestStatus
from app.domain.models import BacktestRun, StrategyConfig
from app.infrastructure.repositories.backtests import BacktestRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.market_data_service import MarketDataService
from app.strategy_engine.registry import registry


@dataclass(frozen=True)
class BacktestRunRequest:
    config_id: int
    start_date: date
    end_date: date


class BacktestService:
    def __init__(
        self,
        session: Session,
        market_data_service: MarketDataService,
        engine: BacktestEngine | None = None,
    ) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.backtests = BacktestRepository(session)
        self.market_data_service = market_data_service
        self.engine = engine or BacktestEngine()

    def run_backtest(self, request: BacktestRunRequest) -> BacktestRun:
        try:
            config = self._get_config(request.config_id)
            prices = self.market_data_service.get_ohlcv(
                config.symbol,
                request.start_date,
                request.end_date,
            )
            strategy = registry.create(config.strategy_type)
            result = self.engine.run(
                strategy=strategy,
                prices=prices,
                initial_capital=config.initial_capital,
                fee_rate=config.fee_rate,
                slippage_rate=config.slippage_rate,
                settings=config.settings_json,
            )
            run = self.backtests.create_run(
                owner_id=config.owner_id,
                strategy_config_snapshot_json=self._snapshot(config),
                start_date=request.start_date,
                end_date=request.end_date,
                status=BacktestStatus.COMPLETED,
                initial_capital=config.initial_capital,
                final_capital=result.summary.final_asset,
                total_return=result.summary.total_return,
                max_drawdown=result.summary.mdd,
                win_rate=result.summary.win_rate,
                total_trades=result.summary.total_trades,
            )
            self.backtests.add_daily_snapshots(run.id, result.daily_snapshots)
            self.backtests.add_trades(run.id, result.trades)
            self.session.commit()
            return run
        except Exception:
            self.session.rollback()
            raise

    def _get_config(self, config_id: int) -> StrategyConfig:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config

    def _snapshot(self, config: StrategyConfig) -> dict:
        return {
            "id": config.id,
            "owner_id": config.owner_id,
            "name": config.name,
            "strategy_type": config.strategy_type,
            "symbol": config.symbol,
            "initial_capital": str(config.initial_capital),
            "fee_rate": str(config.fee_rate),
            "slippage_rate": str(config.slippage_rate),
            "settings_json": config.settings_json,
        }
