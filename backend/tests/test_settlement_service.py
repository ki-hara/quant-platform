from datetime import date
from decimal import Decimal as D
import pytest
from sqlalchemy import select

from tests.test_chart_service import create_session, create_config
from app.domain.models import Position, Trade
from app.domain.enums import StrategyMode, TradeSide
from app.dto.settlements import SettlementDraftDto
from app.services.manual_trade_service import ManualTradeService, ManualTradeRequest
from app.services.settlement_service import SettlementService


def prepare(session):
    config = create_config(session)
    trade = ManualTradeService(session).record_manual_trade(ManualTradeRequest(
        config_id=config.id, side=TradeSide.BUY, trade_date=date(2026, 9, 21),
        quantity=D(5), price=D(100), fee=D(0), mode=StrategyMode.SAFE,
    )).trade
    draft = SettlementDraftDto(trade_date=date(2026, 9, 24), fills=[
        dict(id="f", side="sell", quantity=5, price="110", fee="1")
    ], allocations=[dict(source_id=f"sell:{trade.position_id}", side="sell",
        quantity=5, kind="actual", fill_id="f", change_reason="실제 체결 확인")])
    service = SettlementService(session)
    record = service.save_draft(config.id, draft)
    return config, record, service


def test_confirm_is_atomic_and_idempotent_and_cancel_restores():
    with create_session() as session:
        config, record, service = prepare(session)
        preview = service.preview(record.id)
        assert not preview.blocking_errors
        result = service.confirm(record.id, preview.preview_hash, "request1")
        assert config.live_portfolio.cash == D(1049)
        assert service.confirm(record.id, preview.preview_hash, "request1") == result
        assert len(list(session.scalars(select(Trade)))) == 2
        service.cancel(record.id)
        assert config.live_portfolio.cash == D(500)
        assert len(list(session.scalars(select(Trade)))) == 1
        assert list(session.scalars(select(Position)))[0].status.value == "open"


def test_changed_ledger_rejects_old_preview():
    with create_session() as session:
        config, record, service = prepare(session)
        preview = service.preview(record.id)
        config.live_portfolio.cash += D(1)
        session.commit()
        with pytest.raises(ValueError):
            service.confirm(record.id, preview.preview_hash, "request2")
        assert len(list(session.scalars(select(Trade)))) == 1


def test_transaction_failure_rolls_back_all(monkeypatch):
    with create_session() as session:
        config, record, service = prepare(session)
        preview = service.preview(record.id)
        original = service._apply
        def fail(*args):
            original(*args)
            raise RuntimeError("simulated failure")
        monkeypatch.setattr(service, "_apply", fail)
        with pytest.raises(RuntimeError):
            service.confirm(record.id, preview.preview_hash, "request3")
        assert len(list(session.scalars(select(Trade)))) == 1
        assert config.live_portfolio.cash == D(500)


def test_pending_buy_is_reused_and_raw_prices_preserved():
    from app.infrastructure.repositories.portfolios import PositionRepository
    from app.domain.enums import PositionStatus
    with create_session() as session:
        config = create_config(session)
        pending = PositionRepository(session).create_pending(
            strategy_config_id=config.id, buy_date=date(2026, 9, 24),
            limit_price=D(100), quantity=D(5), mode=StrategyMode.SAFE)
        session.commit()
        draft = SettlementDraftDto(trade_date=date(2026, 9, 24),
            manual_buy_settings=dict(mode="safe", sell_threshold_percent="1", max_holding_days=10),
            fills=[dict(id="a", side="buy", quantity=2, price="90", fee="0.2"),
                   dict(id="b", side="buy", quantity=3, price="100", fee="0.3")],
            allocations=[dict(source_id="buy:manual", position_id=pending.id, side="buy",
                              quantity=q, kind="actual", fill_id=i) for i, q in [("a", 2), ("b", 3)]])
        service = SettlementService(session)
        record = service.save_draft(config.id, draft)
        preview = service.preview(record.id)
        assert not preview.blocking_errors
        service.confirm(record.id, preview.preview_hash, "pending")
        assert len(list(session.scalars(select(Position)))) == 1
        assert pending.status == PositionStatus.OPEN
        assert pending.buy_price == 96
        assert config.live_portfolio.cash == D("519.5")
        assert [t.price for t in session.scalars(select(Trade).order_by(Trade.id))] == [90, 100]
        service.cancel(record.id)
        assert pending.status == PositionStatus.PENDING
        assert config.live_portfolio.cash == 1000


def test_individual_trade_deletion_cannot_rebuild_settlement_ledger():
    with create_session() as session:
        config, record, service = prepare(session)
        preview = service.preview(record.id)
        service.confirm(record.id, preview.preview_hash, "guard")
        trade = session.scalars(select(Trade)).first()
        with pytest.raises(Exception, match="정산"):
            ManualTradeService(session).delete_trade(trade.id)
