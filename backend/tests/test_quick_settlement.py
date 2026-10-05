from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from tests.test_chart_service import create_session, create_config
from app.domain.enums import StrategyMode
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.services.quick_settlement_service import QuickSettlementService

DAY = date(2026, 9, 24)


def setup(session, monkeypatch, close=D('100')):
    config = create_config(session)
    config.fee_rate = D('0')
    monkeypatch.setattr(MarketPriceRepository, 'latest_price_on_or_before',
        lambda *a, **k: SimpleNamespace(date=DAY, close=close) if close else None)
    return config, PositionRepository(session), QuickSettlementService(session)


def position(repo, config, target, days=30, quantity=20):
    return repo.create_open(config.id, date(2026, 9, 21), D('80'), D(quantity), StrategyMode.SAFE,
        sell_threshold_percent=D('1'), sell_limit_price=D(target), max_holding_days=days)


def test_candidates_select_profit_and_maturity_only(monkeypatch):
    with create_session() as session:
        config, repo, service = setup(session, monkeypatch)
        position(repo, config, '90')
        position(repo, config, '120', days=2)
        position(repo, config, '120')
        session.commit()
        result = service.candidates(config.id, DAY)
        assert [r['selected'] for r in result['rows']] == [True, True, False]
        assert [r['reason'] for r in result['rows']] == ['profit', 'maturity', 'holding']
        assert all(r['price'] == '100' for r in result['rows'])


def test_quick_preview_keeps_edited_price_quantity_and_no_close_is_not_guessed(monkeypatch):
    with create_session() as session:
        config, repo, service = setup(session, monkeypatch, close=None)
        pos = position(repo, config, '90')
        session.commit()
        candidates = service.candidates(config.id, DAY)
        assert not candidates['rows'][0]['selected']
        assert candidates['rows'][0]['price'] is None
        result = service.prepare(config.id, DAY, candidates['state_hash'], [
            dict(position_id=pos.id, quantity=3, price=D('99.25'), fee=D('0.12'))], netting=True)
        assert not result['preview'].blocking_errors
        assert result['preview'].cash_delta == D('297.63')


def test_netting_generated_automatically_and_pending_policy_preserved(monkeypatch):
    with create_session() as session:
        config, repo, service = setup(session, monkeypatch)
        sell = position(repo, config, '90')
        buy = repo.create_pending(config.id, DAY, D('110'), D(12), StrategyMode.SAFE,
            sell_threshold_percent=D('2'), max_holding_days=10)
        session.commit()
        candidates = service.candidates(config.id, DAY)
        result = service.prepare(config.id, DAY, candidates['state_hash'], [
            dict(position_id=sell.id, quantity=20, price=D('100'), fee=None),
            dict(position_id=buy.id, quantity=12, price=D('100'), fee=None)], netting=True)
        preview = result['preview']
        assert not preview.blocking_errors
        assert sum(r.quantity for r in preview.rows if r.kind=='actual') == 8
        assert preview.cash_delta == D('800')
        from app.services.settlement_service import SettlementService
        SettlementService(session).confirm(result['record'].id, preview.preview_hash, 'quick-net')
        assert buy.status.value == 'open'
        assert buy.sell_threshold_percent == D('2')
        assert buy.sell_limit_price == D('102')


def test_stale_candidates_cannot_be_silently_reinterpreted(monkeypatch):
    with create_session() as session:
        config, repo, service = setup(session, monkeypatch)
        pos = position(repo, config, '90')
        session.commit()
        candidates = service.candidates(config.id, DAY)
        pos.quantity = D(1)
        session.commit()
        with pytest.raises(ValueError, match='변경'):
            service.prepare(config.id, DAY, candidates['state_hash'], [
                dict(position_id=pos.id, quantity=2, price=D('100'), fee=None)], netting=True)


def test_legacy_pending_uses_existing_confirmation_policy(monkeypatch):
    with create_session() as session:
        config, repo, service = setup(session, monkeypatch)
        buy = repo.create_pending(config.id, DAY, D('110'), D(2), StrategyMode.SAFE)
        session.commit()
        candidates = service.candidates(config.id, DAY)
        assert candidates['rows'][0]['selected']
        result = service.prepare(config.id, DAY, candidates['state_hash'], [
            dict(position_id=buy.id, quantity=2, price=D('100'), fee=None)], netting=True)
        assert not result['preview'].blocking_errors
        from app.services.settlement_service import SettlementService
        SettlementService(session).confirm(result['record'].id, result['preview'].preview_hash, 'legacy')
        assert buy.sell_threshold_percent == D(str(config.settings_json['safe']['sell_threshold_percent']))
