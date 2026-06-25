from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import StrategyConfig


class StrategyConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        owner_id: str,
        name: str,
        strategy_type: str,
        symbol: str,
        initial_capital: Decimal,
        fee_rate: Decimal,
        slippage_rate: Decimal,
        settings_json: dict[str, Any],
    ) -> StrategyConfig:
        config = StrategyConfig(
            owner_id=owner_id,
            name=name,
            strategy_type=strategy_type,
            symbol=symbol,
            initial_capital=initial_capital,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
            settings_json=settings_json,
        )
        self.session.add(config)
        self.session.flush()
        self.session.refresh(config)
        return config

    def get(self, config_id: int, include_archived: bool = False) -> StrategyConfig | None:
        config = self.session.get(StrategyConfig, config_id)
        if config is None:
            return None
        if config.archived_at is not None and not include_archived:
            return None
        return config

    def list_by_owner(self, owner_id: str) -> list[StrategyConfig]:
        stmt = (
            select(StrategyConfig)
            .where(StrategyConfig.owner_id == owner_id, StrategyConfig.archived_at.is_(None))
            .order_by(StrategyConfig.created_at, StrategyConfig.id)
        )
        return list(self.session.scalars(stmt))

    def archive(self, config: StrategyConfig) -> StrategyConfig:
        config.archived_at = datetime.utcnow()
        return self.save(config)

    def save(self, config: StrategyConfig) -> StrategyConfig:
        self.session.add(config)
        self.session.flush()
        self.session.refresh(config)
        return config
