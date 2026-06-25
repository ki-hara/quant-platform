from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import ModeConfirmationSource, StrategyMode
from app.domain.models import ModeRecommendation, StrategyModeState


class ModeStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, strategy_config_id: int) -> StrategyModeState | None:
        stmt = select(StrategyModeState).where(
            StrategyModeState.strategy_config_id == strategy_config_id
        )
        return self.session.scalar(stmt)

    def get_or_create_safe(self, strategy_config_id: int) -> StrategyModeState:
        state = self.get(strategy_config_id)
        if state is None:
            state = StrategyModeState(
                strategy_config_id=strategy_config_id,
                confirmed_mode=StrategyMode.SAFE,
                confirmed_source=ModeConfirmationSource.MANUAL,
                confirmed_at=datetime.utcnow(),
            )
            try:
                with self.session.begin_nested():
                    self.session.add(state)
                    self.session.flush()
            except IntegrityError:
                with self.session.no_autoflush:
                    state = self.get(strategy_config_id)
                if state is None:
                    raise
            self.session.refresh(state)
        return state

    def save(self, state: StrategyModeState) -> StrategyModeState:
        self.session.add(state)
        self.session.flush()
        self.session.refresh(state)
        return state


class ModeRecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, recommendation: ModeRecommendation) -> ModeRecommendation:
        existing = self._get_by_week(
            recommendation.strategy_config_id,
            recommendation.effective_week,
        )
        if existing is None:
            try:
                with self.session.begin_nested():
                    self.session.add(recommendation)
                    self.session.flush()
            except IntegrityError:
                with self.session.no_autoflush:
                    existing = self._get_by_week(
                        recommendation.strategy_config_id,
                        recommendation.effective_week,
                    )
                if existing is None:
                    raise
            else:
                self.session.refresh(recommendation)
                return recommendation

        assert existing is not None
        return existing

    def current(self, strategy_config_id: int) -> ModeRecommendation | None:
        stmt = (
            select(ModeRecommendation)
            .where(ModeRecommendation.strategy_config_id == strategy_config_id)
            .order_by(ModeRecommendation.effective_week.desc(), ModeRecommendation.id.desc())
        )
        return self.session.scalar(stmt)

    def list_by_config(self, strategy_config_id: int) -> list[ModeRecommendation]:
        stmt = (
            select(ModeRecommendation)
            .where(ModeRecommendation.strategy_config_id == strategy_config_id)
            .order_by(ModeRecommendation.effective_week.desc(), ModeRecommendation.id.desc())
        )
        return list(self.session.scalars(stmt))

    def _get_by_week(
        self,
        strategy_config_id: int,
        effective_week: date,
    ) -> ModeRecommendation | None:
        stmt = (
            select(ModeRecommendation)
            .where(ModeRecommendation.strategy_config_id == strategy_config_id)
            .where(ModeRecommendation.effective_week == effective_week)
        )
        return self.session.scalar(stmt)
