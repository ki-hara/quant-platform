from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import PortfolioAdjustment
from app.infrastructure.repositories.portfolios import PortfolioRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.strategy_engine.loc import MONEY_QUANT


@dataclass(frozen=True)
class PortfolioAdjustmentRequest:
    adjustment_date: date
    cash_delta: Decimal
    capital_delta: Decimal
    memo: str | None = None


class PortfolioAdjustmentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)

    def list_adjustments(self, config_id: int) -> list[PortfolioAdjustment]:
        self._get_config(config_id)
        stmt = (
            select(PortfolioAdjustment)
            .where(PortfolioAdjustment.strategy_config_id == config_id)
            .order_by(PortfolioAdjustment.date.desc(), PortfolioAdjustment.id.desc())
        )
        return list(self.session.scalars(stmt))

    def create_adjustment(
        self,
        config_id: int,
        request: PortfolioAdjustmentRequest,
    ) -> PortfolioAdjustment:
        try:
            config = self._get_config(config_id)
            portfolio = self.portfolios.get_by_config(config_id)
            if portfolio is None:
                portfolio = self.portfolios.create_for_config(config)

            next_cash = (portfolio.cash + request.cash_delta).quantize(MONEY_QUANT)
            next_capital = (portfolio.capital + request.capital_delta).quantize(MONEY_QUANT)
            if next_cash < 0:
                raise ValueError("Cash cannot be negative after adjustment.")
            if next_capital < 0:
                raise ValueError("Capital cannot be negative after adjustment.")

            portfolio.cash = next_cash
            portfolio.capital = next_capital
            adjustment = PortfolioAdjustment(
                strategy_config_id=config_id,
                date=request.adjustment_date,
                cash_delta=request.cash_delta.quantize(MONEY_QUANT),
                capital_delta=request.capital_delta.quantize(MONEY_QUANT),
                memo=request.memo,
            )
            self.session.add(adjustment)
            self.session.commit()
            self.session.refresh(adjustment)
            return adjustment
        except Exception:
            self.session.rollback()
            raise

    def _get_config(self, config_id: int):
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config
