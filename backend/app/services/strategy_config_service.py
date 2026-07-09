from dataclasses import dataclass
from copy import deepcopy
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import StrategyConfig, StrategyConfigSnapshot
from app.infrastructure.repositories.modes import ModeStateRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.strategy_engine.registry import registry


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


@dataclass(frozen=True)
class StrategyConfigSnapshotCreateRequest:
    name: str
    memo: str | None = None


class StrategyConfigService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.mode_states = ModeStateRepository(session)

    def list_configs(self, owner_id: str) -> list[StrategyConfig]:
        return self.configs.list_by_owner(owner_id)

    def create_config(
        self,
        owner_id: str,
        request: StrategyConfigCreateRequest,
    ) -> StrategyConfig:
        try:
            registry.create(request.strategy_type)
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
            self.mode_states.get_or_create_safe(config.id)
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

    def list_snapshots(self, config_id: int) -> list[StrategyConfigSnapshot]:
        self.get_config(config_id)
        stmt = (
            select(StrategyConfigSnapshot)
            .where(StrategyConfigSnapshot.strategy_config_id == config_id)
            .order_by(StrategyConfigSnapshot.created_at.desc(), StrategyConfigSnapshot.id.desc())
        )
        return list(self.session.scalars(stmt))

    def create_snapshot(
        self,
        config_id: int,
        request: StrategyConfigSnapshotCreateRequest,
    ) -> StrategyConfigSnapshot:
        try:
            config = self.get_config(config_id)
            snapshot = StrategyConfigSnapshot(
                strategy_config_id=config.id,
                name=request.name,
                memo=request.memo,
                strategy_type=config.strategy_type,
                symbol=config.symbol,
                fee_rate=config.fee_rate,
                slippage_rate=config.slippage_rate,
                settings_json=deepcopy(config.settings_json),
            )
            self.session.add(snapshot)
            self.session.commit()
            self.session.refresh(snapshot)
            return snapshot
        except Exception:
            self.session.rollback()
            raise

    def apply_snapshot(self, config_id: int, snapshot_id: int) -> StrategyConfig:
        try:
            config = self.get_config(config_id)
            snapshot = self._get_snapshot(config_id, snapshot_id)
            config.fee_rate = snapshot.fee_rate
            config.slippage_rate = snapshot.slippage_rate
            config.settings_json = deepcopy(snapshot.settings_json)
            config = self.configs.save(config)
            self.session.commit()
            return config
        except Exception:
            self.session.rollback()
            raise

    def delete_snapshot(self, config_id: int, snapshot_id: int) -> None:
        try:
            snapshot = self._get_snapshot(config_id, snapshot_id)
            self.session.delete(snapshot)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _get_snapshot(self, config_id: int, snapshot_id: int) -> StrategyConfigSnapshot:
        snapshot = self.session.get(StrategyConfigSnapshot, snapshot_id)
        if snapshot is None or snapshot.strategy_config_id != config_id:
            raise ValueError(f"Strategy config snapshot not found: {snapshot_id}")
        return snapshot

    def archive_config(self, config_id: int) -> StrategyConfig:
        try:
            config = self.configs.get(config_id)
            if config is None:
                raise ValueError(f"Strategy config not found: {config_id}")
            archived = self.configs.archive(config)
            self.session.commit()
            return archived
        except Exception:
            self.session.rollback()
            raise

    def update_config(
        self,
        config_id: int,
        request: StrategyConfigUpdateRequest,
    ) -> StrategyConfig:
        try:
            config = self.get_config(config_id)
            if (
                request.initial_capital is not None
                and request.initial_capital != config.initial_capital
            ):
                raise ValueError(
                    "initial_capital cannot be changed after the live portfolio is created."
                )
            if request.strategy_type is not None:
                registry.create(request.strategy_type)
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
