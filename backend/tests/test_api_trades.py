from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import create_database_engine
from app.domain.enums import LocOrderStatus, PositionStatus, StrategyMode, TradeSide
from app.domain.models import LocOrder, MarketPrice, Owner
from app.api.routes_trades import (
    BuyOrderPositionCreateDto,
    PositionUpdateDto,
    create_buy_order_position,
    update_position,
)
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.services.daily_plan_service import DailyPlanService
from app.services.dashboard_service import DashboardService
from app.services.loc_order_service import LocOrderFillRequest, LocOrderService
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.strategy_config_service import StrategyConfigCreateRequest, StrategyConfigService
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def test_radar_snapshots_and_full_realized_pnl_are_persisted() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )
        service = ManualTradeService(session)
        service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 7, 24),
                quantity=Decimal("2"),
                price=Decimal("40"),
                fee=Decimal("0"),
                mode=StrategyMode.SAFE,
                radar_tier=1,
                radar_profile="pro1",
                radar_cycle_id="cycle-one",
                radar_cycle_capital=Decimal("1000"),
                sell_threshold_percent=Decimal("0.01"),
                sell_limit_price=Decimal("40.00"),
                max_holding_days=10,
            )
        )
        position = PositionRepository(session).list_open(config.id)[0]
        assert (position.radar_tier, position.radar_profile, position.radar_cycle_id) == (
            1,
            "pro1",
            "cycle-one",
        )
        service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.SELL,
                trade_date=date(2026, 7, 27),
                quantity=Decimal("2"),
                price=Decimal("45"),
                fee=Decimal("0"),
                position_id=position.id,
            )
        )
        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None
        assert portfolio.realized_pnl == Decimal("10")
        assert portfolio.capital == Decimal("1010")
        for market_date, close in (
            (date(2026, 7, 23), Decimal("44")),
            (date(2026, 7, 24), Decimal("45")),
        ):
            session.add(
                MarketPrice(
                    provider="finance_data_reader",
                    symbol="SOXL",
                    date=market_date,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=Decimal("1000"),
                    adjusted=False,
                )
            )
        session.commit()
        dashboard = DashboardService(session).get_dashboard(config.id)
        assert dashboard.capital_update is None


def test_manual_radar_buy_derives_immutable_exit_rules_from_profile() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )

        ManualTradeService(session).record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 7, 24),
                quantity=Decimal("2"),
                price=Decimal("40.126"),
                fee=Decimal("0"),
                mode=StrategyMode.SAFE,
                radar_tier=1,
                radar_profile="pro2",
                radar_cycle_id="cycle-one",
                radar_cycle_capital=Decimal("1000"),
            )
        )

        position = PositionRepository(session).list_open(config.id)[0]
        assert position.sell_threshold_percent == Decimal("1.50")
        assert position.sell_limit_price == Decimal("40.73")
        assert position.max_holding_days == 10


def test_radar_loc_fill_propagates_cycle_metadata_and_snapshots_fill_exit_price() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )
        order = LocOrder(
            strategy_config_id=config.id,
            order_date=date(2026, 7, 24),
            symbol="SOXL",
            limit_price=Decimal("39.99"),
            recommended_quantity=Decimal("2"),
            mode=StrategyMode.SAFE,
            status=LocOrderStatus.PENDING,
        )
        session.add(order)
        pending_position = PositionRepository(session).create_pending(
            strategy_config_id=config.id,
            buy_date=order.order_date,
            limit_price=order.limit_price,
            quantity=order.recommended_quantity,
            mode=order.mode,
            radar_tier=3,
            radar_profile="pro1",
            radar_cycle_id="cycle-one",
            radar_cycle_capital=Decimal("1000"),
            sell_threshold_percent=Decimal("0.01"),
            sell_limit_price=Decimal("39.99"),
            max_holding_days=10,
        )
        order.position_id = pending_position.id
        PositionRepository(session).create_pending(
            strategy_config_id=config.id,
            buy_date=order.order_date,
            limit_price=Decimal("38"),
            quantity=Decimal("1"),
            mode=order.mode,
            radar_tier=4,
            radar_profile="pro1",
            radar_cycle_id="cycle-one",
            radar_cycle_capital=Decimal("1000"),
            sell_threshold_percent=Decimal("0.01"),
            sell_limit_price=Decimal("38.00"),
            max_holding_days=10,
        )
        session.commit()

        LocOrderService(session).fill_order(
            order.id,
            LocOrderFillRequest(
                quantity=Decimal("2"),
                price=Decimal("40.126"),
                fee=Decimal("0"),
            ),
        )

        position = next(
            item
            for item in PositionRepository(session).list_open(config.id)
            if item.status.value == "open"
        )
        assert order.position_id == position.id
        assert position.status.value == "open"
        assert position.radar_tier == 3
        assert position.radar_profile == "pro1"
        assert position.radar_cycle_id == "cycle-one"
        assert position.radar_cycle_capital == Decimal("1000")
        assert position.sell_threshold_percent == Decimal("0.01")
        assert position.sell_limit_price == Decimal("40.13")
        assert position.max_holding_days == 10


def test_radar_ledger_rebuild_preserves_open_snapshots_and_realized_capital() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )
        service = ManualTradeService(session)

        first = service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 7, 1),
                quantity=Decimal("1"),
                price=Decimal("40"),
                fee=Decimal("0"),
                radar_tier=1,
                radar_profile="pro1",
                radar_cycle_id="cycle-one",
                radar_cycle_capital=Decimal("1000"),
            )
        )
        removable = service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 7, 2),
                quantity=Decimal("1"),
                price=Decimal("30"),
                fee=Decimal("0"),
                radar_tier=2,
                radar_profile="pro1",
                radar_cycle_id="cycle-one",
                radar_cycle_capital=Decimal("1000"),
            )
        )
        third = service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.BUY,
                trade_date=date(2026, 7, 3),
                quantity=Decimal("1"),
                price=Decimal("20"),
                fee=Decimal("0"),
                radar_tier=3,
                radar_profile="pro1",
                radar_cycle_id="cycle-one",
                radar_cycle_capital=Decimal("1000"),
            )
        )
        third_position = next(
            position
            for position in PositionRepository(session).list_open(config.id)
            if position.radar_tier == 3
        )
        service.record_manual_trade(
            ManualTradeRequest(
                config_id=config.id,
                side=TradeSide.SELL,
                trade_date=date(2026, 7, 4),
                quantity=Decimal("1"),
                price=Decimal("50"),
                fee=Decimal("0"),
                position_id=third_position.id,
            )
        )
        assert first.trade.id != removable.trade.id
        assert third.trade.id != removable.trade.id

        service.delete_trade(removable.trade.id)

        open_positions = PositionRepository(session).list_open(config.id)
        assert len(open_positions) == 1
        position = open_positions[0]
        assert position.radar_tier == 1
        assert position.radar_profile == "pro1"
        assert position.radar_cycle_id == "cycle-one"
        assert position.radar_cycle_capital == Decimal("1000")
        assert position.sell_threshold_percent == Decimal("0.01")
        assert position.sell_limit_price == Decimal("40.00")
        assert position.max_holding_days == 10
        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None
        assert portfolio.realized_pnl == Decimal("30")
        assert portfolio.capital == Decimal("1030")


def test_pending_to_open_radar_position_rounds_sell_limit_to_usd_cent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        owner = session.get(Owner, "default")
        assert owner is not None
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro2"},
            ),
        )
        position = PositionRepository(session).create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 24),
            limit_price=Decimal("40"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
            radar_tier=1,
            radar_profile="pro2",
            radar_cycle_id="cycle-one",
            radar_cycle_capital=Decimal("1000"),
            sell_threshold_percent=Decimal("1.50"),
            sell_limit_price=Decimal("40.60"),
            max_holding_days=10,
        )
        session.commit()

        updated = update_position(
            position.id,
            PositionUpdateDto(
                buy_price=Decimal("40.126"),
                status="open",
            ),
            session,
            owner,
        )

        assert updated.sell_limit_price == Decimal("40.73")
        buy_trade = next(trade for trade in config.trades if trade.side == TradeSide.BUY)
        assert buy_trade.position_id == updated.id
def test_pending_to_open_rejects_cost_plus_fee_above_cash() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        owner = session.get(Owner, "default")
        assert owner is not None
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("100"),
                fee_rate=Decimal("1"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )
        position = PositionRepository(session).create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 24),
            limit_price=Decimal("100"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
            radar_tier=1,
            radar_profile="pro1",
            radar_cycle_id="cycle-one",
            radar_cycle_capital=Decimal("100"),
            sell_threshold_percent=Decimal("0.01"),
            sell_limit_price=Decimal("100.01"),
            max_holding_days=10,
        )
        session.commit()

        with pytest.raises(HTTPException, match="Insufficient cash"):
            update_position(
                position.id,
                PositionUpdateDto(buy_price=Decimal("100"), status="open"),
                session,
                owner,
            )

        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None
        assert portfolio.cash == Decimal("100")
        assert not config.trades
def test_radar_buy_order_uses_server_snapshot_and_rejects_stale_duplicate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        owner = session.get(Owner, "default")
        assert owner is not None
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("10000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )
        session.add(
            MarketPrice(
                provider="finance_data_reader",
                symbol="SOXL",
                date=date(2026, 7, 24),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=Decimal("1000"),
                adjusted=False,
            )
        )
        session.commit()
        plan = DailyPlanService(session).get_daily_plan(config.id, today=date(2026, 7, 27))
        request = BuyOrderPositionCreateDto(
            order_date=date(2026, 7, 27),
            quantity=Decimal("5"),
            limit_price=Decimal("99"),
            mode=StrategyMode.SAFE,
            radar_tier=plan.radar_tier,
            radar_profile=plan.radar_profile,
            radar_cycle_id=plan.radar_cycle_id,
            radar_cycle_capital=plan.radar_cycle_capital,
            sell_threshold_percent=Decimal("99"),
            sell_limit_price=Decimal("999"),
            max_holding_days=999,
        )

        position = create_buy_order_position(config.id, request, session, owner)

        assert position.sell_threshold_percent == Decimal("0.01")
        assert position.sell_limit_price == Decimal("99.01")
        assert position.max_holding_days == 10

        with pytest.raises(HTTPException) as exc_info:
            create_buy_order_position(config.id, request, session, owner)
        assert exc_info.value.status_code == 409


def test_dynamic_wave_buy_order_rejects_radar_snapshots() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        owner = session.get(Owner, "default")
        assert owner is not None
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Dynamic",
                strategy_type="dynamic_wave",
                symbol="TQQQ",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json=DynamicWaveStrategy.default_settings(),
            ),
        )
        request = BuyOrderPositionCreateDto(
            order_date=date(2026, 7, 27),
            quantity=Decimal("1"),
            limit_price=Decimal("40"),
            mode=StrategyMode.SAFE,
            radar_tier=1,
        )

        with pytest.raises(HTTPException) as exc_info:
            create_buy_order_position(config.id, request, session, owner)

        assert exc_info.value.status_code == 400
        assert PositionRepository(session).list_open(config.id) == []

def test_corrected_buy_fill_rejects_negative_cash() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        owner = session.get(Owner, "default")
        assert owner is not None
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Dynamic",
                strategy_type="dynamic_wave",
                symbol="TQQQ",
                initial_capital=Decimal("100"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json=DynamicWaveStrategy.default_settings(),
            ),
        )
        position = PositionRepository(session).create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 27),
            limit_price=Decimal("50"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
        )
        session.commit()
        update_position(
            position.id,
            PositionUpdateDto(buy_price=Decimal("50"), status="open"),
            session,
            owner,
        )

        with pytest.raises(HTTPException, match="Insufficient cash"):
            update_position(
                position.id,
                PositionUpdateDto(quantity=Decimal("3")),
                session,
                owner,
            )


def test_identical_positions_link_to_distinct_buy_trades() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        owner = session.get(Owner, "default")
        assert owner is not None
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Dynamic",
                strategy_type="dynamic_wave",
                symbol="TQQQ",
                initial_capital=Decimal("200"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json=DynamicWaveStrategy.default_settings(),
            ),
        )
        positions = PositionRepository(session)
        first = positions.create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 27),
            limit_price=Decimal("50"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
        )
        second = positions.create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 27),
            limit_price=Decimal("50"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
        )
        session.commit()

        for position in (first, second):
            update_position(
                position.id,
                PositionUpdateDto(buy_price=Decimal("50"), status="open"),
                session,
                owner,
            )

        buy_trades = [trade for trade in config.trades if trade.side == TradeSide.BUY]
        assert len(buy_trades) == 2
        assert {trade.position_id for trade in buy_trades} == {first.id, second.id}


def test_active_radar_tier_unique_index_allows_reuse_only_after_close() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("1000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro1"},
            ),
        )
        positions = PositionRepository(session)
        first = positions.create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 27),
            limit_price=Decimal("40"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
            radar_tier=1,
            radar_profile="pro1",
            radar_cycle_id="cycle-one",
            radar_cycle_capital=Decimal("1000"),
        )
        session.commit()
        with pytest.raises(IntegrityError):
            positions.create_pending(
                strategy_config_id=config.id,
                buy_date=date(2026, 7, 28),
                limit_price=Decimal("39"),
                quantity=Decimal("1"),
                mode=StrategyMode.SAFE,
                radar_tier=1,
                radar_profile="pro1",
                radar_cycle_id="cycle-one",
                radar_cycle_capital=Decimal("1000"),
            )
        session.rollback()

        first.status = PositionStatus.CLOSED
        session.add(first)
        session.commit()
        replacement = positions.create_pending(
            strategy_config_id=config.id,
            buy_date=date(2026, 7, 28),
            limit_price=Decimal("39"),
            quantity=Decimal("1"),
            mode=StrategyMode.SAFE,
            radar_tier=1,
            radar_profile="pro1",
            radar_cycle_id="cycle-one",
            radar_cycle_capital=Decimal("1000"),
        )
        session.commit()

        assert replacement.id != first.id
