from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import PositionStatus, StrategyMode, TradeSide, TradeSource
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.modes import ModeStateRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.dashboard_service import DashboardService
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.portfolio_adjustment_service import PortfolioAdjustmentRequest, PortfolioAdjustmentService
from app.services.signal_execution_service import SignalExecutionRequest, SignalExecutionService
from app.services.strategy_config_service import (
    StrategyConfigCreateRequest,
    StrategyConfigUpdateRequest,
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
        state = ModeStateRepository(session).get(config.id)

        assert portfolio is not None
        assert portfolio.capital == Decimal("1000.000000")
        assert portfolio.cash == Decimal("1000.000000")
        assert state is not None
        assert state.confirmed_mode == StrategyMode.SAFE


def test_strategy_config_service_archive_hides_config_from_live_lists() -> None:
    with create_session() as session:
        service = StrategyConfigService(session)
        config = create_config(session)

        archived = service.archive_config(config.id)

        assert archived.archived_at is not None
        assert config.id not in [row.id for row in service.list_configs("default")]
        with pytest.raises(ValueError, match="not found"):
            service.get_config(config.id)


def test_portfolio_adjustment_updates_cash_and_capital() -> None:
    with create_session() as session:
        config = create_config(session)

        adjustment = PortfolioAdjustmentService(session).create_adjustment(
            config.id,
            PortfolioAdjustmentRequest(
                adjustment_date=date(2026, 6, 26),
                cash_delta=Decimal("100"),
                capital_delta=Decimal("50"),
                memo="deposit",
            ),
        )

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert adjustment.cash_delta == Decimal("100.000000")
        assert adjustment.capital_delta == Decimal("50.000000")
        assert portfolio is not None
        assert portfolio.cash == Decimal("1100.000000")
        assert portfolio.capital == Decimal("1050.000000")


def test_portfolio_adjustment_rejects_negative_cash() -> None:
    with create_session() as session:
        config = create_config(session)

        with pytest.raises(ValueError, match="Cash cannot be negative"):
            PortfolioAdjustmentService(session).create_adjustment(
                config.id,
                PortfolioAdjustmentRequest(
                    adjustment_date=date(2026, 6, 26),
                    cash_delta=Decimal("-1001"),
                    capital_delta=Decimal("0"),
                    memo="withdrawal",
                ),
            )


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


def test_manual_trade_buy_creates_independent_open_position_and_updates_cash() -> None:
    with create_session() as session:
        config = create_config(session)

        result = ManualTradeService(session).record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("2"),
                price=Decimal("100"),
                fee=Decimal("1.25"),
                source=TradeSource.MANUAL,
            ),
        )

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        positions = PositionRepository(session).list_open(config.id)
        trades = TradeRepository(session).list_by_strategy_config(config.id)

        assert portfolio is not None
        assert portfolio.cash == Decimal("798.750000")
        assert portfolio.cumulative_fees == Decimal("1.250000")
        assert positions[0].buy_price == Decimal("100.000000")
        assert positions[0].buy_fee == Decimal("1.250000")
        assert result.trade == trades[0]
        assert trades[0].source == TradeSource.MANUAL


def test_manual_trade_buy_keeps_loc_limit_separate_from_execution_price() -> None:
    with create_session() as session:
        config = create_config(session)

        ManualTradeService(session).record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("4"),
                price=Decimal("25"),
                fee=Decimal("0.10"),
                source=TradeSource.MANUAL,
                limit_price=Decimal("30"),
            ),
        )

        positions = PositionRepository(session).list_open(config.id)
        trades = TradeRepository(session).list_by_strategy_config(config.id)

        assert positions[0].limit_price == Decimal("30.000000")
        assert positions[0].buy_price == Decimal("25.000000")
        assert trades[0].limit_price == Decimal("30.000000")
        assert trades[0].price == Decimal("25.000000")


def test_manual_trade_sell_requires_position_id() -> None:
    with create_session() as session:
        config = create_config(session)

        with pytest.raises(ValueError, match="position_id"):
            ManualTradeService(session).record_manual_trade(
                ManualTradeRequest(
                    config_id=config.id,
                    side=TradeSide.SELL,
                    trade_date=date(2026, 1, 3),
                    quantity=Decimal("1"),
                    price=Decimal("110"),
                    fee=Decimal("0.50"),
                    source=TradeSource.CORRECTION,
                ),
            )


def test_manual_trade_partial_sell_reduces_position_and_allocates_buy_fee() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ManualTradeService(session)
        service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("2"),
                price=Decimal("100"),
                fee=Decimal("1.25"),
            ),
        )
        position = PositionRepository(session).list_open(config.id)[0]

        result = service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.SELL,
                trade_date=date(2026, 1, 3),
                quantity=Decimal("1"),
                price=Decimal("110"),
                fee=Decimal("0.50"),
                position_id=position.id,
                source=TradeSource.CORRECTION,
            ),
        )

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        positions = PositionRepository(session).list_open(config.id)

        assert portfolio is not None
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("1.000000")
        assert positions[0].buy_fee == Decimal("0.625000")
        assert portfolio.cash == Decimal("908.250000")
        assert portfolio.realized_pnl == Decimal("8.875000")
        assert portfolio.cumulative_fees == Decimal("1.750000")
        assert result.realized_pnl == Decimal("8.875000")


def test_manual_trade_sell_rejects_quantity_above_open_position() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ManualTradeService(session)
        service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("1"),
                price=Decimal("100"),
                fee=Decimal("0"),
            ),
        )
        position = PositionRepository(session).list_open(config.id)[0]

        with pytest.raises(ValueError, match="cannot exceed"):
            service.record_manual_trade(
                ManualTradeRequest(
                    config_id=config.id,
                    side=TradeSide.SELL,
                    trade_date=date(2026, 1, 3),
                    quantity=Decimal("2"),
                    price=Decimal("110"),
                    fee=Decimal("0"),
                    position_id=position.id,
                ),
            )


def test_delete_manual_sell_trade_rebuilds_portfolio_and_positions() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ManualTradeService(session)
        service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("2"),
                price=Decimal("100"),
                fee=Decimal("1.25"),
            ),
        )
        position = PositionRepository(session).list_open(config.id)[0]
        sell = service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.SELL,
                trade_date=date(2026, 1, 3),
                quantity=Decimal("1"),
                price=Decimal("110"),
                fee=Decimal("0.50"),
                position_id=position.id,
                source=TradeSource.MANUAL,
            ),
        ).trade

        service.delete_trade(sell.id)

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        positions = PositionRepository(session).list_open(config.id)
        trades = TradeRepository(session).list_by_strategy_config(config.id)

        assert portfolio is not None
        assert portfolio.cash == Decimal("798.750000")
        assert portfolio.realized_pnl == Decimal("0.000000")
        assert portfolio.cumulative_fees == Decimal("1.250000")
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("2.000000")
        assert [trade.side for trade in trades] == [TradeSide.BUY]


def test_delete_trade_rebuild_preserves_portfolio_adjustments() -> None:
    with create_session() as session:
        config = create_config(session)
        PortfolioAdjustmentService(session).create_adjustment(
            config.id,
            PortfolioAdjustmentRequest(
                adjustment_date=date(2026, 1, 1),
                cash_delta=Decimal("500"),
                capital_delta=Decimal("300"),
                memo="deposit",
            ),
        )
        service = ManualTradeService(session)
        buy = service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 1, 2),
                quantity=Decimal("2"),
                price=Decimal("100"),
                fee=Decimal("1"),
            ),
        ).trade

        service.delete_trade(buy.id)

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None
        assert portfolio.cash == Decimal("1500.000000")
        assert portfolio.capital == Decimal("1300.000000")
        assert portfolio.cumulative_fees == Decimal("0.000000")


def test_strategy_config_update_rejects_initial_capital_change() -> None:
    with create_session() as session:
        config = create_config(session)

        with pytest.raises(ValueError, match="initial_capital"):
            StrategyConfigService(session).update_config(
                config.id,
                StrategyConfigUpdateRequest(initial_capital=Decimal("2000")),
            )


def test_strategy_config_update_allows_unchanged_initial_capital() -> None:
    with create_session() as session:
        config = create_config(session)

        updated = StrategyConfigService(session).update_config(
            config.id,
            StrategyConfigUpdateRequest(
                name="Renamed",
                initial_capital=Decimal("1000"),
            ),
        )

        assert updated.name == "Renamed"


def test_strategy_config_update_rejects_unknown_strategy_type() -> None:
    with create_session() as session:
        config = create_config(session)

        with pytest.raises(ValueError, match="Unknown strategy type"):
            StrategyConfigService(session).update_config(
                config.id,
                StrategyConfigUpdateRequest(strategy_type="missing_strategy"),
            )


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
