from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import ModeConfirmationSource, StrategyMode
from app.domain.models import ModeRecommendation, StrategyConfig, StrategyModeState
from app.dto.market_data import OhlcvDto
from app.dto.trading_plan import ModeRecommendationDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeRecommendationRepository, ModeStateRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.strategy_engine.weekly_rsi import DailyClose, aggregate_daily_closes_to_weekly_closes, resolve_weekly_rsi_transition


@dataclass(frozen=True)
class _RecommendationContext:
    state: StrategyModeState
    recommendation: ModeRecommendation | None


class ModeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.mode_states = ModeStateRepository(session)
        self.mode_recommendations = ModeRecommendationRepository(session)

    def get_state(self, config_id: int) -> StrategyModeState:
        self._get_config(config_id)
        return self.mode_states.get_or_create_safe(config_id)

    def get_mode_recommendation(self, config_id: int, as_of: date) -> ModeRecommendationDto:
        config = self._get_config(config_id)
        state = self.mode_states.get_or_create_safe(config_id)
        recommendation = self._recalculate(config, state, as_of)
        return self._to_dto(state, recommendation)

    def set_confirmed_mode(self, config_id: int, mode: StrategyMode) -> ModeRecommendationDto:
        self._get_config(config_id)
        state = self.mode_states.get_or_create_safe(config_id)
        state.confirmed_mode = mode
        state.confirmed_source = ModeConfirmationSource.MANUAL
        state.confirmed_at = self._utc_now()
        self.mode_states.save(state)
        self.session.commit()
        return self._to_state_only_dto(state)

    def apply_recommendation(self, config_id: int) -> ModeRecommendationDto:
        self._get_config(config_id)
        state = self.mode_states.get_or_create_safe(config_id)
        if state.recommended_mode is None or state.recommendation_effective_week is None:
            raise ValueError("Current recommendation is not available.")
        state.confirmed_mode = state.recommended_mode
        state.confirmed_source = ModeConfirmationSource.RECOMMENDATION_APPLIED
        state.confirmed_at = self._utc_now()
        self.mode_states.save(state)
        self.session.commit()
        return self._to_state_only_dto(state)

    def list_mode_recommendations(self, config_id: int) -> list[ModeRecommendationDto]:
        self._get_config(config_id)
        state = self.mode_states.get_or_create_safe(config_id)
        return [self._to_dto(state, recommendation) for recommendation in self.mode_recommendations.list_by_config(config_id)]

    def _get_config(self, config_id: int) -> StrategyConfig:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config

    def _recalculate(
        self,
        config: StrategyConfig,
        state: StrategyModeState,
        as_of: date,
    ) -> ModeRecommendation:
        symbol = str(config.settings_json.get("mode_rsi_symbol", "QQQ"))
        prices = self.market_prices.list_prices(
            settings.market_data_provider,
            symbol,
            date(1970, 1, 1),
            as_of,
        )
        weekly_closes = [
            weekly_close
            for weekly_close in aggregate_daily_closes_to_weekly_closes(
                [DailyClose(date=price.date, close=price.close) for price in prices]
            )
            if weekly_close.week_ending <= as_of
        ]
        if len(weekly_closes) < 16:
            raise ValueError("At least 16 completed weekly closes are required.")

        transition = resolve_weekly_rsi_transition(weekly_closes, prior_mode=state.confirmed_mode)
        if transition is None:
            raise ValueError("At least 16 completed weekly closes are required.")

        recommendation = ModeRecommendation(
            strategy_config_id=config.id,
            effective_week=transition.effective_week,
            data_as_of=transition.data_as_of,
            previous_rsi=transition.previous_rsi,
            current_rsi=transition.current_rsi,
            recommended_mode=transition.recommended_mode,
            rule_code=transition.rule_code,
            calculated_at=self._utc_now(),
        )
        stored_recommendation = self.mode_recommendations.upsert(recommendation)
        state.recommended_mode = stored_recommendation.recommended_mode
        state.recommendation_effective_week = stored_recommendation.effective_week
        state.recommendation_data_as_of = stored_recommendation.data_as_of
        state.recommendation_previous_rsi = stored_recommendation.previous_rsi
        state.recommendation_current_rsi = stored_recommendation.current_rsi
        state.recommendation_rule_code = stored_recommendation.rule_code
        state.recommendation_calculated_at = self._utc_now()
        self.mode_states.save(state)
        self.session.commit()
        return stored_recommendation

    def _to_state_only_dto(self, state: StrategyModeState) -> ModeRecommendationDto:
        return ModeRecommendationDto(
            confirmed_mode=state.confirmed_mode,
            confirmed_source=state.confirmed_source,
            recommended_mode=state.recommended_mode,
            differs=state.recommended_mode is not None and state.recommended_mode != state.confirmed_mode,
            effective_week=state.recommendation_effective_week,
            data_as_of=state.recommendation_data_as_of,
            previous_rsi=state.recommendation_previous_rsi,
            current_rsi=state.recommendation_current_rsi,
            rule_code=state.recommendation_rule_code,
        )

    def _to_dto(
        self,
        state: StrategyModeState,
        recommendation: ModeRecommendation | None,
    ) -> ModeRecommendationDto:
        if recommendation is None:
            return self._to_state_only_dto(state)
        return ModeRecommendationDto(
            confirmed_mode=state.confirmed_mode,
            confirmed_source=state.confirmed_source,
            recommended_mode=recommendation.recommended_mode,
            differs=recommendation.recommended_mode != state.confirmed_mode,
            effective_week=recommendation.effective_week,
            data_as_of=recommendation.data_as_of,
            previous_rsi=recommendation.previous_rsi,
            current_rsi=recommendation.current_rsi,
            rule_code=recommendation.rule_code,
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
