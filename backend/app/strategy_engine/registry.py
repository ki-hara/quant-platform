from app.strategy_engine.base import Strategy
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, type[Strategy]] = {}

    def register(self, strategy_cls: type[Strategy]) -> None:
        self._strategies[strategy_cls.strategy_type] = strategy_cls

    def create(self, strategy_type: str) -> Strategy:
        strategy_cls = self._strategies.get(strategy_type)
        if strategy_cls is None:
            available = ", ".join(self._strategies.keys()) or "none"
            raise ValueError(
                f"Unknown strategy type '{strategy_type}'. Available strategy types: {available}"
            )
        return strategy_cls()

    def list(self) -> list[dict[str, str]]:
        return [
            {"type": strategy_type, "name": strategy_cls.display_name}
            for strategy_type, strategy_cls in self._strategies.items()
        ]


registry = StrategyRegistry()
registry.register(DynamicWaveStrategy)
