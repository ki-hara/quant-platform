from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import ModeConfirmationSource, StrategyMode
from app.domain.models import ModeRecommendation, StrategyModeState
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.modes import (
    ModeRecommendationRepository,
    ModeStateRepository,
)
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


def create_file_session(tmp_path) -> tuple:
    engine = create_engine(f"sqlite:///{tmp_path / 'modes.sqlite'}")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


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


def create_config_without_mode_state(session: Session):
    return StrategyConfigRepository(session).create(
        owner_id="default",
        name="Live Strategy",
        strategy_type="dynamic_wave",
        symbol="TEST",
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0.1"),
        slippage_rate=Decimal("0"),
        settings_json=DynamicWaveStrategy.default_settings(),
    )


def make_recommendation(
    config_id: int,
    effective_week: date,
    rule_code: str = "A1",
) -> ModeRecommendation:
    return ModeRecommendation(
        strategy_config_id=config_id,
        effective_week=effective_week,
        data_as_of=date(2026, 6, 19),
        previous_rsi=Decimal("49.3589779596"),
        current_rsi=Decimal("53.5996753027"),
        recommended_mode=StrategyMode.AGGRESSIVE,
        rule_code=rule_code,
        calculated_at=datetime(2026, 6, 19, 15, 30),
    )


def test_strategy_config_service_initializes_safe_mode_state_transactionally() -> None:
    with create_session() as session:
        config = create_config(session)

        state = ModeStateRepository(session).get(config.id)

        assert state is not None
        assert state.confirmed_mode == StrategyMode.SAFE
        assert state.confirmed_source == ModeConfirmationSource.MANUAL
        assert state.recommended_mode is None
        assert state.recommendation_effective_week is None
        assert state.recommendation_rule_code is None


def test_mode_state_repository_get_or_create_safe_is_idempotent() -> None:
    with create_session() as session:
        config = create_config(session)
        repository = ModeStateRepository(session)

        first = repository.get_or_create_safe(config.id)
        second = repository.get_or_create_safe(config.id)

        assert first.strategy_config_id == config.id
        assert second.strategy_config_id == config.id
        assert first is second
        assert first.confirmed_mode == StrategyMode.SAFE
        assert first.confirmed_source == ModeConfirmationSource.MANUAL


def test_mode_state_repository_get_or_create_safe_recovers_from_concurrent_insert(
    tmp_path,
) -> None:
    engine, session = create_file_session(tmp_path)
    try:
        seed_default_owner(session, "default")
        config = create_config_without_mode_state(session)
        config_id = config.id
        session.commit()
        session.close()

        with Session(engine) as outer_session:
            repository = ModeStateRepository(outer_session)
            racer_triggered = {"value": False}

            def racer(orm_execute_state):
                result = orm_execute_state.invoke_statement()
                if not racer_triggered["value"] and orm_execute_state.is_select:
                    sql = str(orm_execute_state.statement)
                    if "strategy_mode_states" in sql:
                        racer_triggered["value"] = True
                        with Session(engine) as competitor:
                            competitor.add(
                                StrategyModeState(
                                    strategy_config_id=config_id,
                                    confirmed_mode=StrategyMode.SAFE,
                                    confirmed_source=ModeConfirmationSource.MANUAL,
                                )
                            )
                            competitor.commit()
                return result

            from sqlalchemy import event

            event.listen(outer_session, "do_orm_execute", racer, retval=True)
            try:
                with outer_session.begin():
                    state = repository.get_or_create_safe(config_id)
                    outer_session.flush()
                    assert outer_session.in_transaction()
                    assert state.confirmed_mode == StrategyMode.SAFE
                    assert state.confirmed_source == ModeConfirmationSource.MANUAL
            finally:
                event.remove(outer_session, "do_orm_execute", racer)

            with Session(engine) as verify_session:
                stored = ModeStateRepository(verify_session).get(config_id)
                assert stored is not None
                assert stored.confirmed_mode == StrategyMode.SAFE
    finally:
        session.close()
        engine.dispose()


def test_mode_recommendation_repository_upsert_is_idempotent_for_same_effective_week() -> None:
    with create_session() as session:
        config = create_config(session)
        repository = ModeRecommendationRepository(session)

        first = repository.upsert(make_recommendation(config.id, date(2026, 6, 22)))
        second = repository.upsert(make_recommendation(config.id, date(2026, 6, 22)))

        assert first.id == second.id
        assert repository.list_by_config(config.id) == [second]


def test_mode_recommendation_repository_current_returns_newest_recommendation() -> None:
    with create_session() as session:
        config = create_config(session)
        repository = ModeRecommendationRepository(session)

        older = repository.upsert(make_recommendation(config.id, date(2026, 6, 15), "S1"))
        newer = repository.upsert(make_recommendation(config.id, date(2026, 6, 22), "A1"))

        assert repository.current(config.id) == newer
        assert repository.list_by_config(config.id) == [newer, older]


def test_mode_recommendation_repository_upsert_recovers_from_concurrent_insert(
    tmp_path,
) -> None:
    engine, session = create_file_session(tmp_path)
    try:
        seed_default_owner(session, "default")
        config = create_config_without_mode_state(session)
        config_id = config.id
        session.commit()
        session.close()

        with Session(engine) as outer_session:
            repository = ModeRecommendationRepository(outer_session)
            racer_triggered = {"value": False}

            def racer(orm_execute_state):
                result = orm_execute_state.invoke_statement()
                if not racer_triggered["value"] and orm_execute_state.is_select:
                    sql = str(orm_execute_state.statement)
                    if "mode_recommendations" in sql:
                        racer_triggered["value"] = True
                        with Session(engine) as competitor:
                            competitor.add(make_recommendation(config_id, date(2026, 6, 22)))
                            competitor.commit()
                return result

            from sqlalchemy import event

            event.listen(outer_session, "do_orm_execute", racer, retval=True)
            try:
                with outer_session.begin():
                    recommendation = repository.upsert(make_recommendation(config_id, date(2026, 6, 22)))
                    outer_session.flush()
                    assert outer_session.in_transaction()
                    assert recommendation.strategy_config_id == config_id
                    assert recommendation.recommended_mode == StrategyMode.AGGRESSIVE
            finally:
                event.remove(outer_session, "do_orm_execute", racer)

            with Session(engine) as verify_session:
                recommendations = ModeRecommendationRepository(verify_session).list_by_config(
                    config_id
                )
                assert len(recommendations) == 1
                assert recommendations[0].effective_week == date(2026, 6, 22)
    finally:
        session.close()
        engine.dispose()
