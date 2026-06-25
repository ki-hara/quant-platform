from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.dto.trading_plan import DailyPlanDto, LocPlanDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeStateRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.market_session_service import latest_confirmed_market_date
from app.strategy_engine.loc import LocPlan, calculate_loc_plan


class DailyPlanService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.mode_states = ModeStateRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)

    def get_daily_plan(self, config_id: int, today: date, now: datetime | None = None) -> DailyPlanDto:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")

        state = self.mode_states.get_or_create_safe(config_id)
        portfolio = self.portfolios.get_by_config(config_id)
        open_positions = self.positions.list_open(config_id)
        basis_date = latest_confirmed_market_date(config.symbol, now)
        latest_price = self.market_prices.latest_price_on_or_before(
            settings.market_data_provider,
            config.symbol,
            basis_date,
        )
        mode_settings = config.settings_json[state.confirmed_mode.value]
        split_count = int(mode_settings["split_count"])
        buy_threshold = Decimal(str(mode_settings["buy_threshold_percent"]))

        if latest_price is None or portfolio is None:
            loc_plan = LocPlan(
                limit_price=Decimal("0.000000"),
                allocation=Decimal("0.000000"),
                quantity=0,
                estimated_fee=Decimal("0.000000"),
                required_cash=Decimal("0.000000"),
                available=(portfolio.cash if portfolio is not None else Decimal("0")).quantize(Decimal("0.000001")),
                blocking_reason="market_data_unavailable",
                orders=[],
            )
            previous_close: Decimal | None = None
            data_as_of: date | None = None
            capital = portfolio.capital if portfolio is not None else None
            cash = portfolio.cash if portfolio is not None else None
        else:
            loc_plan = calculate_loc_plan(
                previous_close=latest_price.close,
                capital=portfolio.capital,
                cash=portfolio.cash,
                fee_rate=Decimal(str(config.settings_json.get("fee_rate_percent", "0"))),
                split_count=split_count,
                buy_threshold_percent=buy_threshold,
                open_position_count=len(open_positions),
            )
            previous_close = latest_price.close
            data_as_of = latest_price.date
            capital = portfolio.capital
            cash = portfolio.cash

        return DailyPlanDto(
            plan_date=today,
            market_data_as_of=data_as_of,
            symbol=config.symbol,
            confirmed_mode=state.confirmed_mode,
            confirmed_source=state.confirmed_source,
            recommended_mode=state.recommended_mode,
            differs=state.recommended_mode is not None and state.recommended_mode != state.confirmed_mode,
            effective_week=state.recommendation_effective_week,
            data_as_of=state.recommendation_data_as_of,
            previous_rsi=state.recommendation_previous_rsi,
            current_rsi=state.recommendation_current_rsi,
            rule_code=state.recommendation_rule_code,
            previous_close=previous_close,
            loc_basis_date=data_as_of,
            loc_basis_close=previous_close,
            loc_formula=(
                f"{previous_close} * (1 + {buy_threshold} / 100) = {loc_plan.limit_price}"
                if previous_close is not None
                else None
            ),
            mode_buy_threshold_percent=buy_threshold,
            capital=capital,
            cash=cash,
            mode_split_count=split_count,
            open_position_count=len(open_positions),
            buy_available=loc_plan.blocking_reason is None,
            LOC=LocPlanDto.model_validate(loc_plan),
        )
