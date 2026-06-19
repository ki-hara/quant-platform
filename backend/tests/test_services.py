from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import PositionStatus, TradeSide
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.dashboard_service import DashboardService
from app.services.signal_execution_service import SignalExecutionRequest, SignalExecutionService
from app.services.strategy_config_service import (
    StrategyConfigCreateRequest,
    StrategyConfigService,
)
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def create_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_default_owner(session, "default")
    return session


def create_config(session: Session):
    return StrategyConfigService(session).create_config(
        "default",
        StrategyConfigCreateRequest(
            name="Live Strategy",
            strategy_type="dynamic_wave",
            symbol="TEST",
            initial_capital=Decimal("1000"),
            fee_rate=Decimal("0.1"),
            slippage_rate=Decimal("0"),
            settings_json=DynamicWaveStrategy.default_settings(),
        ),
    )


def test_strategy_config_service_create_config_creates_matching_live_portfolio() -> None:
    with create_session() as session:
        config = create_config(session)
        portfolio = PortfolioRepository(session).get_by_config(config.id)

        assert portfolio is not None
        assert portfolio.capital == Decimal("1000.000000")
        assert portfolio.cash == Decimal("1000.000000")


def test_signal_execution_buy_creates_position_with_fee_updates_cash_and_trade() -> None:
    with create_session() as session:
        config = create_config(session)

        result = SignalExecutionService(session).execute_signal(
            config.id,
            SignalExecutionRequest(
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("3"),
                price=Decimal("100"),
                fee=Decimal("1.25"),
            ),
        )

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        positions = PositionRepository(session).list_open(config.id)
        trades = TradeRepository(session).list_by_strategy_config(config.id)

        assert portfolio is not None
        assert portfolio.cash == Decimal("698.750000")
        assert positions[0].buy_fee == Decimal("1.250000")
        assert result.trade == trades[0]
        assert trades[0].side == TradeSide.BUY
        assert trades[0].fee == Decimal("1.250000")


def test_signal_execution_sell_closes_position_and_realized_pnl_subtracts_buy_and_sell_fees() -> None:
    with create_session() as session:
        config = create_config(session)
        service = SignalExecutionService(session)
        service.execute_signal(
            config.id,
            SignalExecutionRequest(
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("3"),
                price=Decimal("100"),
                fee=Decimal("1.25"),
            ),
        )
        position = PositionRepository(session).list_open(config.id)[0]

        result = service.execute_signal(
            config.id,
            SignalExecutionRequest(
                side=TradeSide.SELL,
                trade_date=date(2026, 1, 3),
                quantity=Decimal("3.000000"),
                price=Decimal("120"),
                fee=Decimal("1.50"),
                position_id=position.id,
                sell_reason="profit_target",
            ),
        )

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        closed_position = PositionRepository(session).get(position.id)
        trades = TradeRepository(session).list_by_strategy_config(config.id)

        assert portfolio is not None
        assert closed_position is not None
        assert closed_position.status == PositionStatus.CLOSED
        assert portfolio.cash == Decimal("1057.250000")
        assert result.realized_pnl == Decimal("57.250000")
        assert portfolio.realized_pnl == Decimal("57.250000")
        assert trades[-1].side == TradeSide.SELL
        assert trades[-1].realized_pnl == Decimal("57.250000")


@pytest.mark.parametrize(
    ("quantity", "price", "fee", "message"),
    [
        (Decimal("0"), Decimal("100"), Decimal("0"), "quantity"),
        (Decimal("1"), Decimal("0"), Decimal("0"), "price"),
        (Decimal("1"), Decimal("100"), Decimal("-0.01"), "fee"),
    ],
)
def test_signal_execution_validates_positive_quantity_price_and_non_negative_fee(
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    message: str,
) -> None:
    with create_session() as session:
        config = create_config(session)

        with pytest.raises(ValueError, match=message):
            SignalExecutionService(session).execute_signal(
                config.id,
                SignalExecutionRequest(
                    side=TradeSide.BUY,
                    trade_date=date(2026, 1, 2),
                    quantity=quantity,
                    price=price,
                    fee=fee,
                ),
            )


def test_dashboard_missing_market_data_returns_unavailable_signals() -> None:
    with create_session() as session:
        config = create_config(session)

        dashboard = DashboardService(session).get_dashboard(config.id)

        assert dashboard.latest_price is None
        assert dashboard.total_asset is None
        assert dashboard.signals.available is False
        assert dashboard.signals.reason == "market_data_unavailable"
