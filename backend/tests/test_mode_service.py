from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import ModeConfirmationSource, StrategyMode
from app.dto.market_data import OhlcvDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.main import create_app
from app.services.mode_service import ModeService
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
            name="Live Strategy",
            strategy_type="dynamic_wave",
            symbol="TEST",
            initial_capital=Decimal("1000"),
            fee_rate=Decimal("0.1"),
            slippage_rate=Decimal("0"),
            settings_json=DynamicWaveStrategy.default_settings(),
        ),
    )


def seed_weekly_prices(
    session: Session,
    closes: list[str],
    *,
    symbol: str = "QQQ",
    provider: str = "finance_data_reader",
    first_week_ending: date = date(2026, 2, 27),
) -> None:
    prices = [
        OhlcvDto(
            symbol=symbol,
            date=first_week_ending + timedelta(days=7 * index),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]
    MarketPriceRepository(session).upsert_prices(provider, prices)


def seed_incomplete_current_week_prices(session: Session, symbol: str = "QQQ") -> None:
    MarketPriceRepository(session).upsert_prices(
        "finance_data_reader",
        [
            OhlcvDto(
                symbol=symbol,
                date=date(2026, 6, 15),
                open=Decimal("200"),
                high=Decimal("200"),
                low=Decimal("200"),
                close=Decimal("200"),
                volume=1000,
            ),
            OhlcvDto(
                symbol=symbol,
                date=date(2026, 6, 16),
                open=Decimal("201"),
                high=Decimal("201"),
                low=Decimal("201"),
                close=Decimal("201"),
                volume=1000,
            ),
            OhlcvDto(
                symbol=symbol,
                date=date(2026, 6, 17),
                open=Decimal("202"),
                high=Decimal("202"),
                low=Decimal("202"),
                close=Decimal("202"),
                volume=1000,
            ),
        ],
    )


def test_get_mode_recommendation_updates_only_recommendation_fields() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ModeService(session)
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )

        result = service.get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        state = service.get_state(config.id)
        histories = service.list_mode_recommendations(config.id)

        assert result.confirmed_mode == StrategyMode.SAFE
        assert result.confirmed_source == ModeConfirmationSource.MANUAL
        assert result.recommended_mode == StrategyMode.SAFE
        assert result.differs is False
        assert result.effective_week == date(2026, 6, 22)
        assert result.data_as_of == date(2026, 6, 19)
        assert result.rule_code == "S1"
        assert state.confirmed_mode == StrategyMode.SAFE
        assert state.recommended_mode == StrategyMode.SAFE
        assert state.recommendation_effective_week == date(2026, 6, 22)
        assert len(histories) == 1
        assert histories[0].effective_week == date(2026, 6, 22)


def test_get_mode_recommendation_ignores_incomplete_current_week() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ModeService(session)
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )
        seed_incomplete_current_week_prices(session)

        result = service.get_mode_recommendation(config.id, as_of=date(2026, 6, 17))

        assert result.effective_week == date(2026, 6, 15)
        assert result.data_as_of == date(2026, 6, 12)
        assert result.recommended_mode == StrategyMode.SAFE


def test_confirmed_mode_can_be_set_directly_and_apply_recommendation_uses_current_recommendation() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ModeService(session)
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )

        direct = service.set_confirmed_mode(config.id, StrategyMode.AGGRESSIVE)
        recommendation = service.get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        applied = service.apply_recommendation(config.id)
        state = service.get_state(config.id)

        assert direct.confirmed_mode == StrategyMode.AGGRESSIVE
        assert direct.confirmed_source == ModeConfirmationSource.MANUAL
        assert recommendation.confirmed_mode == StrategyMode.AGGRESSIVE
        assert recommendation.recommended_mode == StrategyMode.SAFE
        assert recommendation.differs is True
        assert applied.confirmed_mode == StrategyMode.SAFE
        assert applied.confirmed_source == ModeConfirmationSource.RECOMMENDATION_APPLIED
        assert state.confirmed_mode == StrategyMode.SAFE
        assert state.confirmed_source == ModeConfirmationSource.RECOMMENDATION_APPLIED


def test_apply_recommendation_requires_an_existing_recommendation() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ModeService(session)

        with pytest.raises(ValueError, match="recommendation"):
            service.apply_recommendation(config.id)


def test_get_mode_recommendation_requires_sixteen_completed_weekly_closes() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ModeService(session)
        seed_weekly_prices(
            session,
            [
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
            ],
        )

        with pytest.raises(ValueError, match="16 completed weekly closes"):
            service.get_mode_recommendation(config.id, as_of=date(2026, 6, 19))


def test_mode_recommendation_history_is_newest_first() -> None:
    with create_session() as session:
        config = create_config(session)
        service = ModeService(session)
        seed_weekly_prices(
            session,
            [
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
                "111",
            ],
        )

        service.get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        service.get_mode_recommendation(config.id, as_of=date(2026, 6, 26))

        histories = service.list_mode_recommendations(config.id)

        assert [history.effective_week for history in histories] == [
            date(2026, 6, 29),
            date(2026, 6, 22),
        ]


def test_get_mode_recommendation_missing_config_raises_value_error() -> None:
    with create_session() as session:
        service = ModeService(session)

        with pytest.raises(ValueError, match="Strategy config not found"):
            service.get_mode_recommendation(999, as_of=date(2026, 6, 19))
