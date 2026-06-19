from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.domain.models import StrategyConfig
from app.infrastructure.repositories.portfolios import PortfolioRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository


@dataclass(frozen=True)
class StrategyConfigCreateRequest:
    name: str
    strategy_type: str
    symbol: str
    initial_capital: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    settings_json: dict[str, Any]


@dataclass(frozen=True)
class StrategyConfigUpdateRequest:
    name: str | None = None
    strategy_type: str | None = None
    symbol: str | None = None
    initial_capital: Decimal | None = None
    fee_rate: Decimal | None = None
    slippage_rate: Decimal | None = None
    settings_json: dict[str, Any] | None = None


class StrategyConfigService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)

    def list_configs(self, owner_id: str) -> list[StrategyConfig]:
        return self.configs.list_by_owner(owner_id)

    def create_config(
        self,
        owner_id: str,
        request: StrategyConfigCreateRequest,
    ) -> StrategyConfig:
        try:
            config = self.configs.create(
                owner_id=owner_id,
                name=request.name,
                strategy_type=request.strategy_type,
                symbol=request.symbol,
                initial_capital=request.initial_capital,
                fee_rate=request.fee_rate,
                slippage_rate=request.slippage_rate,
                settings_json=request.settings_json,
            )
            self.portfolios.create_for_config(config)
            self.session.commit()
            return config
        except Exception:
            self.session.rollback()
            raise

    def get_config(self, config_id: int) -> StrategyConfig:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config

    def update_config(
        self,
        config_id: int,
        request: StrategyConfigUpdateRequest,
    ) -> StrategyConfig:
        try:
            config = self.get_config(config_id)
            for field in (
                "name",
                "strategy_type",
                "symbol",
                "initial_capital",
                "fee_rate",
                "slippage_rate",
                "settings_json",
            ):
                value = getattr(request, field)
                if value is not None:
                    setattr(config, field, value)
            config = self.configs.save(config)
            self.session.commit()
            return config
        except Exception:
            self.session.rollback()
            raise
