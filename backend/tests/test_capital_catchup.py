from datetime import date
from decimal import Decimal as D
from sqlalchemy import select
from tests.test_chart_service import create_session, create_config
from app.domain.enums import TradeSide, TradeSource
from app.domain.models import PortfolioAdjustment
from app.infrastructure.repositories.trades import TradeRepository
from app.services.dashboard_service import DashboardService


def test_empty_period_catchup_loss_late_fill_and_idempotence(monkeypatch):
    with create_session() as session:
        config = create_config(session)
        config.symbol = 'SOXL'
        config.settings_json = dict(config.settings_json, profit_compounding_rate=80,
                                    loss_compounding_rate=30,
                                    capital_update={'interval': 5})
        svc = DashboardService(session)
        portfolio = svc.portfolios.get_by_config(config.id)
        initial = portfolio.capital
        cash = portfolio.cash
        def trade(day, pnl):
            return TradeRepository(session).create(
                strategy_config_id=config.id, trade_date=day, side=TradeSide.SELL,
                quantity=D(1),price=D(100),fee=D(0),realized_pnl=D(pnl),
                sell_reason='profit_target',source=TradeSource.MANUAL)
        trade(date(2026,7,23), '0')
        trade(date(2026,8,3), '-100')
        trade(date(2026,8,10), '100')
        monkeypatch.setattr('app.services.dashboard_service.current_market_date',lambda s:date(2026,8,13))
        monkeypatch.setattr('app.services.dashboard_service.latest_confirmed_market_date',lambda s:date(2026,8,13))
        session.commit()
        svc._auto_apply_capital_update(config,portfolio,[])
        assert portfolio.capital == initial + D(50)
        adjustments = list(session.scalars(select(PortfolioAdjustment)))
        assert len(adjustments)==3
        assert adjustments[0].capital_delta == 0
        svc._auto_apply_capital_update(config,portfolio,[])
        assert portfolio.capital == initial + D(50)
        trade(date(2026,7,28), '-200')
        session.commit()
        config.settings_json = dict(config.settings_json, loss_compounding_rate=100)
        svc._auto_apply_capital_update(config,portfolio,[])
        assert portfolio.capital == initial - D(10)
        svc._auto_apply_capital_update(config,portfolio,[])
        assert portfolio.capital == initial - D(10)
        assert portfolio.cash == cash
        assert len(list(session.scalars(select(PortfolioAdjustment))))==3
