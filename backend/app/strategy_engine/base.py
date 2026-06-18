from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import StrategyMode
from app.strategy_engine.context import StrategyContext, StrategyPosition


@dataclass(frozen=True)
class BuySignal:
    should_buy: bool
    reason: str | None = None


@dataclass(frozen=True)
class SellSignal:
    should_sell: bool
    reason: str | None = None
    return_percent: Decimal | None = None


@dataclass(frozen=True)
class PositionSize:
    amount: Decimal
    quantity: int


@dataclass(frozen=True)
class CapitalUpdate:
    capital: Decimal


class Strategy(ABC):
    strategy_type: str
    display_name: str

    @abstractmethod
    def get_mode(self, context: StrategyContext) -> StrategyMode:
        raise NotImplementedError

    @abstractmethod
    def should_buy(self, context: StrategyContext) -> BuySignal:
        raise NotImplementedError

    @abstractmethod
    def should_sell(self, context: StrategyContext, position: StrategyPosition) -> SellSignal:
        raise NotImplementedError

    @abstractmethod
    def calculate_position_size(self, context: StrategyContext) -> PositionSize:
        raise NotImplementedError

    @abstractmethod
    def update_capital(self, context: StrategyContext, realized_pnl: Decimal) -> CapitalUpdate:
        """Apply strategy-specific capital compounding when orchestration says it is due.

        Backtest and orchestration services own the configured schedule check and call this
        method only for realized PnL that should update capital.
        """
        raise NotImplementedError

    @abstractmethod
    def get_settings_schema(self) -> dict:
        raise NotImplementedError
