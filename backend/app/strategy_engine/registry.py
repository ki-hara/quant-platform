from app.strategy_engine.base import Strategy
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, type[Strategy]] = {}

    def register(self, strategy_cls: type[Strategy]) -> None:
        self._strategies[strategy_cls.strategy_type] = strategy_cls

    def create(self, strategy_type: str) -> Strategy:
        return self._strategies[strategy_type]()

    def list(self) -> list[dict[str, str]]:
        return [
            {"type": strategy_type, "name": strategy_cls.display_name}
            for strategy_type, strategy_cls in self._strategies.items()
        ]


registry = StrategyRegistry()
registry.register(DynamicWaveStrategy)
