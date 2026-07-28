from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import ModeConfirmationSource, StrategyMode
from app.dto.trading_plan import DailyPlanDto, LocPlanDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeStateRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.exchange_calendar_service import previous_exchange_trading_day
from app.services.market_session_service import current_market_date
from app.strategy_engine.loc import LocPlan, calculate_loc_plan
from app.strategy_engine.radar0458_pro import build_radar_buy_plan


class DailyPlanService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.mode_states = ModeStateRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)

    def get_daily_plan(
        self,
        config_id: int,
        today: date | None = None,
        now: datetime | None = None,
        position_sizing_policy: str = "fixed_quantity",
    ) -> DailyPlanDto:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")

        portfolio = self.portfolios.get_by_config(config_id)
        open_positions = self.positions.list_open(config_id)
        order_date = (
            current_market_date(config.symbol, now)
            if now is not None
            else (today or current_market_date(config.symbol))
        )
        basis_date = previous_exchange_trading_day(config.symbol, order_date)
        latest_price = self.market_prices.latest_price_on_or_before(
            settings.market_data_provider,
            config.symbol,
            basis_date,
        )
        if config.strategy_type == "radar0458_pro":
            return self._get_radar_daily_plan(
                config, portfolio, open_positions, order_date, latest_price
            )
        state = self.mode_states.get_or_create_safe(config_id)
        mode_settings = config.settings_json[state.confirmed_mode.value]
        split_count = int(mode_settings["split_count"])
        buy_threshold = Decimal(str(mode_settings["buy_threshold_percent"]))
        if position_sizing_policy not in {"fixed_quantity", "full_allocation"}:
            raise ValueError(f"Unknown position sizing policy: {position_sizing_policy}")

        if latest_price is None or portfolio is None:
            loc_plan = LocPlan(
                limit_price=Decimal("0.000000"),
                allocation=Decimal("0.000000"),
                quantity=0,
                estimated_fee=Decimal("0.000000"),
                required_cash=Decimal("0.000000"),
                available=(portfolio.cash if portfolio is not None else Decimal("0")).quantize(
                    Decimal("0.000001")
                ),
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
                position_sizing_policy=position_sizing_policy,
            )
            previous_close = latest_price.close
            data_as_of = latest_price.date
            capital = portfolio.capital
            cash = portfolio.cash

        return DailyPlanDto(
            plan_date=order_date,
            market_data_as_of=data_as_of,
            symbol=config.symbol,
            confirmed_mode=state.confirmed_mode,
            confirmed_source=state.confirmed_source,
            recommended_mode=state.recommended_mode,
            differs=state.recommended_mode is not None
            and state.recommended_mode != state.confirmed_mode,
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

    def _get_radar_daily_plan(
        self, config, portfolio, positions, order_date, latest_price
    ) -> DailyPlanDto:
        required = (
            "radar_tier",
            "radar_profile",
            "radar_cycle_id",
            "radar_cycle_capital",
            "sell_threshold_percent",
            "sell_limit_price",
            "max_holding_days",
        )
        snapshot_missing = any(
            any(getattr(position, field) is None for field in required) for position in positions
        )
        active = positions[0] if positions and not snapshot_missing else None
        profile = (
            active.radar_profile if active is not None else config.settings_json["pro_profile"]
        )
        cycle_capital = (
            active.radar_cycle_capital
            if active is not None
            else (portfolio.capital if portfolio is not None else None)
        )
        cycle_id = (
            active.radar_cycle_id
            if active is not None
            else str(uuid5(NAMESPACE_URL, f"radar0458-pro:{config.id}:{order_date.isoformat()}"))
        )
        previous_close = latest_price.close if latest_price is not None else None
        reason = (
            "market_data_unavailable"
            if portfolio is None or latest_price is None
            else ("radar_position_snapshot_missing" if snapshot_missing else None)
        )

        if reason is None:
            radar_plan = build_radar_buy_plan(
                previous_close=previous_close,
                cycle_capital=cycle_capital,
                available_cash=portfolio.cash,
                occupied_tiers={position.radar_tier for position in positions},
                profile=profile,
            )
            required_cash = radar_plan.limit_price * Decimal(radar_plan.quantity)
            estimated_fee = (required_cash * config.fee_rate / Decimal("100")).quantize(
                Decimal("0.000001")
            )
            loc_plan = LocPlan(
                limit_price=radar_plan.limit_price,
                allocation=radar_plan.allocation,
                quantity=radar_plan.quantity,
                estimated_fee=estimated_fee,
                required_cash=(required_cash + estimated_fee).quantize(Decimal("0.000001")),
                available=portfolio.cash.quantize(Decimal("0.000001")),
                blocking_reason=radar_plan.blocking_reason,
                orders=[],
            )
            radar_tier = radar_plan.tier
        else:
            loc_plan = LocPlan(
                limit_price=Decimal("0.000000"),
                allocation=Decimal("0.000000"),
                quantity=0,
                estimated_fee=Decimal("0.000000"),
                required_cash=Decimal("0.000000"),
                available=(portfolio.cash if portfolio is not None else Decimal("0")).quantize(
                    Decimal("0.000001")
                ),
                blocking_reason=reason,
                orders=[],
            )
            radar_tier = None

        return DailyPlanDto(
            plan_date=order_date,
            market_data_as_of=latest_price.date if latest_price is not None else None,
            symbol=config.symbol,
            confirmed_mode=StrategyMode.SAFE,
            confirmed_source=ModeConfirmationSource.MANUAL,
            recommended_mode=None,
            differs=False,
            effective_week=None,
            data_as_of=None,
            previous_rsi=None,
            current_rsi=None,
            rule_code=None,
            previous_close=previous_close,
            loc_basis_date=latest_price.date if latest_price is not None else None,
            loc_basis_close=previous_close,
            loc_formula=None,
            mode_buy_threshold_percent=None,
            capital=portfolio.capital if portfolio is not None else None,
            cash=portfolio.cash if portfolio is not None else None,
            mode_split_count=None,
            open_position_count=len(positions),
            buy_available=loc_plan.blocking_reason is None,
            LOC=LocPlanDto.model_validate(loc_plan),
            strategy_type=config.strategy_type,
            radar_profile=profile,
            radar_tier=radar_tier,
            radar_cycle_id=cycle_id,
            radar_cycle_capital=cycle_capital,
        )
