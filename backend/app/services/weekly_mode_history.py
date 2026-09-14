from datetime import date, timedelta

from app.core.config import settings
from app.domain.enums import StrategyMode
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeRecommendationRepository
from app.services.exchange_calendar_service import previous_exchange_trading_day
from app.strategy_engine.weekly_rsi import (
    DailyClose, aggregate_daily_closes_to_weekly_closes, resolve_weekly_rsi_transition,
)


def weekly_mode_history(session, config, confirmed_through: date):
    symbol = str(config.settings_json.get("mode_rsi_symbol", "QQQ"))
    prices = MarketPriceRepository(session).list_prices(
        settings.market_data_provider, symbol, date(1970, 1, 1), confirmed_through,
    )
    weeks = aggregate_daily_closes_to_weekly_closes([
        DailyClose(date=price.date, close=price.close) for price in prices
    ])
    stored = {row.effective_week: row for row in
              ModeRecommendationRepository(session).list_by_config(config.id)}
    history = []
    prior = StrategyMode.SAFE
    for index in range(15, len(weeks)):
        week = weeks[index]
        last_session = previous_exchange_trading_day(symbol, week.week_ending + timedelta(days=1))
        if last_session > confirmed_through or week.data_as_of < last_session:
            continue
        transition = resolve_weekly_rsi_transition(weeks[:index + 1], prior_mode=prior)
        if transition is None:
            continue
        # Preserve recorded recommendations; reconstruct only missing history.
        recommendation = stored.get(transition.effective_week, transition)
        if recommendation.data_as_of > confirmed_through:
            continue
        history.append(recommendation)
        prior = recommendation.recommended_mode
    return history
