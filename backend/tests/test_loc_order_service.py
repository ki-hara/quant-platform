from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import LocOrderStatus, StrategyMode, TradeSide, TradeSource
from app.domain.models import LocOrder, Position, Trade
from app.infrastructure.repositories.portfolios import PortfolioRepository
from app.services.loc_order_service import LocOrderFillRequest, LocOrderService
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.strategy_config_service import StrategyConfigCreateRequest, StrategyConfigService
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
            name="LOC Strategy",
            strategy_type="dynamic_wave",
            symbol="TEST",
            initial_capital=Decimal("1000"),
            fee_rate=Decimal("0.1"),
            slippage_rate=Decimal("0"),
            settings_json=DynamicWaveStrategy.default_settings(),
        ),
    )


def create_pending_order(session: Session, config_id: int) -> LocOrder:
    order = LocOrder(
        strategy_config_id=config_id,
        order_date=date(2026, 7, 10),
        symbol="TEST",
        limit_price=Decimal("100"),
        recommended_quantity=Decimal("2"),
        mode=StrategyMode.SAFE,
        status=LocOrderStatus.PENDING,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def fill_request() -> LocOrderFillRequest:
    return LocOrderFillRequest(
        quantity=Decimal("2"),
        price=Decimal("99"),
        fee=Decimal("0.2"),
    )


def test_fill_order_commits_trade_and_order_once() -> None:
    with create_session() as session:
        config = create_config(session)
        order = create_pending_order(session, config.id)

        with patch.object(session, "commit", wraps=session.commit) as commit:
            filled = LocOrderService(session).fill_order(order.id, fill_request())

        assert commit.call_count == 1
        assert filled.status == LocOrderStatus.FILLED
        assert filled.trade_id is not None
        assert len(session.scalars(select(Trade)).all()) == 1
        assert len(session.scalars(select(Position)).all()) == 1


def test_manual_trade_can_defer_commit_for_composite_operation() -> None:
    with create_session() as session:
        config = create_config(session)
        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None

        with patch.object(session, "commit", wraps=session.commit) as commit:
            result = ManualTradeService(session).record_manual_trade(
                ManualTradeRequest(
                    config_id=config.id,
                    side=TradeSide.BUY,
                    trade_date=date(2026, 7, 10),
                    quantity=Decimal("2"),
                    price=Decimal("99"),
                    fee=Decimal("0.2"),
                    source=TradeSource.MANUAL,
                    mode=StrategyMode.SAFE,
                ),
                commit=False,
            )

        assert commit.call_count == 0
        assert result.trade.id is not None
        assert portfolio.cash == Decimal("801.800000")
        session.rollback()
        assert session.scalar(select(Trade)) is None
        assert session.scalar(select(Position)) is None


def test_fill_order_rolls_back_every_change_when_commit_fails() -> None:
    with create_session() as session:
        config = create_config(session)
        order = create_pending_order(session, config.id)
        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None
        cash_before = portfolio.cash

        with patch.object(session, "commit", side_effect=RuntimeError("commit failed")):
            with pytest.raises(RuntimeError, match="commit failed"):
                LocOrderService(session).fill_order(order.id, fill_request())

        session.refresh(order)
        session.refresh(portfolio)
        assert order.status == LocOrderStatus.PENDING
        assert order.trade_id is None
        assert portfolio.cash == cash_before
        assert session.scalar(select(Trade)) is None
        assert session.scalar(select(Position)) is None


def test_fill_order_rejects_a_stale_pending_order_loaded_by_another_session(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'loc-orders.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup_session:
        seed_default_owner(setup_session, "default")
        config = create_config(setup_session)
        order = create_pending_order(setup_session, config.id)
        config_id = config.id
        order_id = order.id

    with Session(engine, expire_on_commit=False) as first, Session(engine, expire_on_commit=False) as stale:
        stale_order = stale.get(LocOrder, order_id)
        assert stale_order is not None
        assert stale_order.status == LocOrderStatus.PENDING

        LocOrderService(first).fill_order(order_id, fill_request())

        with pytest.raises(ValueError, match="pending"):
            LocOrderService(stale).fill_order(order_id, fill_request())

    with Session(engine) as verification:
        trades = verification.scalars(
            select(Trade).where(Trade.strategy_config_id == config_id)
        ).all()
        positions = verification.scalars(
            select(Position).where(Position.strategy_config_id == config_id)
        ).all()
        assert len(trades) == 1
        assert len(positions) == 1
