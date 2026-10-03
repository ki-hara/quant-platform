from datetime import date
from decimal import Decimal as D

from app.dto.settlements import SettlementDraftDto
from app.services.settlement_allocation import SettlementContext, calculate_settlement


def context():
    return SettlementContext(sources={
        "s": dict(side="sell", quantity=20, position_id=1, limit_price="90", execution="loc"),
        "b": dict(side="buy", quantity=12, position_id=None, limit_price="120", execution="loc"),
    }, close=D("100"), positions={1: dict(quantity="20", buy_price="80", buy_fee="0", status="open")})


def draft():
    return SettlementDraftDto(trade_date=date(2026, 9, 24), fills=[
        dict(id="f", side="sell", quantity=8, price="110", fee="0.8")
    ], allocations=[
        dict(source_id="s", fill_id="f", side="sell", quantity=8, kind="actual"),
        dict(source_id="s", side="sell", quantity=12, kind="offset"),
        dict(source_id="b", side="buy", quantity=12, kind="offset"),
    ])


def test_offset_and_actual_prices_cash_and_fees():
    result = calculate_settlement(draft(), context())
    assert result.blocking_errors == []
    assert result.cash_delta == D("879.2")
    assert result.total_fee == D("0.8")
    assert result.realized_pnl == D("479.2")
    assert [r.price for r in result.rows] == [D("110"), D("100"), D("100")]
    assert [r.fee for r in result.rows] == [D("0.8"), D("0"), D("0")]


def test_zero_external_fill_full_offset():
    request = draft()
    request.fills = []
    request.allocations = request.allocations[1:]
    result = calculate_settlement(request, context())
    assert not result.blocking_errors
    assert result.cash_delta == 0


def test_missing_close_and_unallocated_fill_are_blocked():
    ctx = context()
    ctx.close = None
    assert calculate_settlement(draft(), ctx).blocking_errors
    request = draft()
    request.allocations = request.allocations[1:]
    assert calculate_settlement(request, context()).blocking_errors


def test_overallocation_and_unconfirmed_price_change_are_blocked():
    request = draft()
    request.allocations[0].quantity = 9
    assert calculate_settlement(request, context()).blocking_errors
    request = draft()
    ctx = context()
    ctx.sources["s"]["limit_price"] = "130"
    assert calculate_settlement(request, ctx).blocking_errors
    for row in request.allocations:
        row.change_reason = "주문 변경 확인"
    assert not calculate_settlement(request, ctx).blocking_errors
