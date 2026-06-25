from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import TradeSide
from app.dto.trading_plan import (
    ChartCandleDto,
    ChartLineDto,
    ChartResponseDto,
    ModeMarkerDto,
    RsiPointDto,
    RsiSeriesDto,
    TradeMarkerDto,
)
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeRecommendationRepository, ModeStateRepository
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.market_session_service import latest_confirmed_market_date
from app.strategy_engine.loc import calculate_loc_plan
from app.strategy_engine.weekly_rsi import (
    DailyClose,
    aggregate_daily_closes_to_weekly_closes,
    calculate_simple_rsi,
    latest_completed_mode_week_ending,
)


RANGE_DAYS = {"1m": 31, "3m": 93, "6m": 186, "1y": 366}
RSI_GUIDES = [
    Decimal("35.000000"),
    Decimal("40.000000"),
    Decimal("50.000000"),
    Decimal("60.000000"),
    Decimal("65.000000"),
]


class ChartService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.mode_states = ModeStateRepository(session)
        self.mode_recommendations = ModeRecommendationRepository(session)
        self.positions = PositionRepository(session)
        self.trades = TradeRepository(session)

    def get_chart(self, config_id: int, range_key: str, today: date) -> ChartResponseDto:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        days = RANGE_DAYS.get(range_key)
        if days is None:
            raise ValueError(f"Unsupported chart range: {range_key}")

        start_date = today - timedelta(days=days - 1)
        prices = self.market_prices.list_prices_in_range(
            settings.market_data_provider,
            config.symbol,
            start_date,
            today,
        )
        candles = [
            ChartCandleDto(
                date=price.date,
                open=price.open,
                high=price.high,
                low=price.low,
                close=price.close,
                volume=int(price.volume),
            )
            for price in prices
        ]
        loc = self._loc_line(config_id, config.symbol, config.settings_json, today)
        return ChartResponseDto(
            candles=candles,
            LOC=loc,
            trade_markers=self._trade_markers(config_id, start_date, today),
            rsi=self._rsi_series(config.settings_json, start_date, today),
            mode_markers=self._mode_markers(config_id, start_date, today + timedelta(days=7)),
        )

    def _loc_line(self, config_id: int, symbol: str, config_settings: dict, today: date) -> ChartLineDto:
        state = self.mode_states.get_or_create_safe(config_id)
        basis_date = latest_confirmed_market_date(
            symbol,
            datetime.combine(today, time(23, 59)).astimezone(),
        )
        latest_price = self.market_prices.latest_price_on_or_before(
            settings.market_data_provider,
            symbol,
            basis_date,
        )
        if latest_price is None:
            return ChartLineDto(value=Decimal("0.000000"), as_of=None)
        mode_settings = config_settings[state.confirmed_mode.value]
        plan = calculate_loc_plan(
            previous_close=latest_price.close,
            capital=Decimal("1"),
            cash=Decimal("1"),
            fee_rate=Decimal("0"),
            split_count=int(mode_settings["split_count"]),
            buy_threshold_percent=Decimal(str(mode_settings["buy_threshold_percent"])),
            open_position_count=len(self.positions.list_open(config_id)),
        )
        return ChartLineDto(value=plan.limit_price, as_of=latest_price.date)

    def _trade_markers(self, config_id: int, start_date: date, end_date: date) -> list[TradeMarkerDto]:
        markers: list[TradeMarkerDto] = []
        for trade in self.trades.list_in_range(config_id, start_date, end_date):
            markers.append(
                TradeMarkerDto(
                    date=trade.date,
                    kind="buy" if trade.side is TradeSide.BUY else "sell",
                    price=trade.price,
                    quantity=trade.quantity,
                    source=trade.source.value,
                    sell_reason=trade.sell_reason,
                )
            )
        return markers

    def _rsi_series(self, config_settings: dict, start_date: date, today: date) -> RsiSeriesDto:
        symbol = str(config_settings.get("mode_rsi_symbol", "QQQ"))
        prices = self.market_prices.list_prices(
            settings.market_data_provider,
            symbol,
            date(1970, 1, 1),
            today,
        )
        weekly_closes = aggregate_daily_closes_to_weekly_closes(
            [DailyClose(date=price.date, close=price.close) for price in prices]
        )
        latest_completed_week_ending = latest_completed_mode_week_ending(today)
        weekly_closes = [
            weekly_close
            for weekly_close in weekly_closes
            if weekly_close.week_ending <= latest_completed_week_ending
        ]
        points: list[RsiPointDto] = []
        for index in range(14, len(weekly_closes)):
            rsi = calculate_simple_rsi([item.close for item in weekly_closes[index - 14 : index + 1]])
            if rsi is not None and weekly_closes[index].week_ending >= start_date:
                points.append(RsiPointDto(date=weekly_closes[index].week_ending, value=rsi))
        return RsiSeriesDto(guides=RSI_GUIDES, points=points)

    def _mode_markers(self, config_id: int, start_date: date, end_date: date) -> list[ModeMarkerDto]:
        return [
            ModeMarkerDto(
                date=recommendation.effective_week,
                mode=recommendation.recommended_mode,
                rule_code=recommendation.rule_code,
            )
            for recommendation in self.mode_recommendations.list_by_config(config_id)
            if start_date <= recommendation.effective_week <= end_date
        ]
