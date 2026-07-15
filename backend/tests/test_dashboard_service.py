from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.dto.market_data import OhlcvDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.services.dashboard_service import DashboardService, _trading_days_held
from app.services.strategy_config_service import StrategyConfigCreateRequest, StrategyConfigService
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy

def test_trading_days_held_falls_back_to_weekdays_when_market_data_is_stale() -> None:
    prices = [SimpleNamespace(date=date(2026, 6, 25))]

    assert _trading_days_held(prices, date(2026, 6, 26), date(2026, 6, 29)) == 1


def test_dashboard_ignores_prices_after_confirmed_market_close(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config = StrategyConfigService(session).create_config(
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
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [
                OhlcvDto(
                    symbol="TEST",
                    date=date(2026, 7, 14),
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100"),
                    volume=1000,
                ),
                OhlcvDto(
                    symbol="TEST",
                    date=date(2026, 7, 15),
                    open=Decimal("200"),
                    high=Decimal("201"),
                    low=Decimal("199"),
                    close=Decimal("200"),
                    volume=2000,
                ),
            ],
        )
        from app.services import dashboard_service

        monkeypatch.setattr(
            dashboard_service,
            "latest_confirmed_market_date",
            lambda symbol: date(2026, 7, 14),
            raising=False,
        )
        monkeypatch.setattr(dashboard_service.FearGreedService, "get_current", lambda self: None)
        monkeypatch.setattr(dashboard_service.TrendFilterService, "get_summary", lambda *args: None)

        dashboard = DashboardService(session).get_dashboard(config.id)

    assert dashboard.latest_price is not None
    assert dashboard.latest_price.date == date(2026, 7, 14)