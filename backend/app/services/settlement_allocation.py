from dataclasses import dataclass, field
from decimal import Decimal

from app.dto.settlements import PreviewRowDto, SettlementDraftDto, SettlementPreviewDto

QUANT = Decimal("0.000001")


@dataclass
class SettlementContext:
    sources: dict
    close: Decimal | None
    positions: dict = field(default_factory=dict)


def calculate_settlement(draft: SettlementDraftDto, context: SettlementContext) -> SettlementPreviewDto:
    result = SettlementPreviewDto()
    errors = result.blocking_errors
    fills = {f.id: f for f in draft.fills}
    if len(fills) != len(draft.fills):
        errors.append("체결 행 식별자가 중복됩니다.")
    used = {key: 0 for key in fills}
    source_used = {}
    position_used = {}
    offsets = {"buy": 0, "sell": 0}
    if not draft.allocations:
        errors.append("배분할 포지션을 선택해 주세요.")
    for allocation in draft.allocations:
        source = context.sources.get(allocation.source_id)
        if not source or source["side"] != allocation.side:
            errors.append("원주문과 배분 방향을 확인해 주세요.")
            continue
        position_id = source.get("position_id") if allocation.side == "sell" else allocation.position_id
        price = context.close
        if allocation.kind == "actual":
            fill = fills.get(allocation.fill_id)
            if fill is None or fill.side != allocation.side:
                errors.append("실제 체결 행과 배분 방향을 확인해 주세요.")
                continue
            used[fill.id] += allocation.quantity
            price = fill.price
        else:
            if allocation.fill_id is not None:
                errors.append("상계 행에는 실제 체결을 연결하지 않습니다.")
            offsets[allocation.side] += allocation.quantity
            if price is None:
                errors.append("해당 거래일의 확정 종가가 없어 상계할 수 없습니다.")
                continue
        source_used[allocation.source_id] = source_used.get(allocation.source_id, 0) + allocation.quantity
        if source_used[allocation.source_id] > int(source["quantity"]) and not allocation.change_reason.strip():
            errors.append("주문 수량 변경 사유를 입력해 주세요.")
        limit = source.get("limit_price")
        if source.get("execution") != "market_on_close" and limit:
            violated = price > Decimal(str(limit)) if allocation.side == "buy" else price < Decimal(str(limit))
            if violated and not allocation.change_reason.strip():
                errors.append("주문 가격 조건과 다릅니다. 변경 사유를 확인해 주세요.")
        if position_id is not None:
            position = context.positions.get(position_id)
            expected = "open" if allocation.side == "sell" else "pending"
            if position is None or position["status"] != expected:
                errors.append("포지션 상태가 변경되었습니다. 다시 확인해 주세요.")
                continue
            key = (position_id, allocation.side)
            position_used[key] = position_used.get(key, 0) + allocation.quantity
            if position_used[key] > Decimal(str(position["quantity"])):
                errors.append("포지션의 가용 수량을 초과했습니다.")
        result.rows.append(PreviewRowDto(
            source_id=allocation.source_id, position_id=position_id, side=allocation.side,
            quantity=allocation.quantity, price=price, fee=Decimal("0"),
            kind=allocation.kind, fill_id=allocation.fill_id,
        ))
    for key, fill in fills.items():
        if used[key] != fill.quantity:
            errors.append(f"체결 {key}: 수량 {fill.quantity}주를 모두 정확히 배분해 주세요.")
        rows = [r for r in result.rows if r.fill_id == key and r.kind == "actual"]
        gross = sum((r.price*r.quantity for r in rows), Decimal("0"))
        remainder = fill.fee
        for index, row in enumerate(rows):
            row.fee = remainder if index == len(rows)-1 else (fill.fee*row.price*row.quantity/gross).quantize(QUANT)
            remainder -= row.fee
    if offsets["buy"] != offsets["sell"]:
        errors.append("상계 매수와 상계 매도 수량이 다릅니다.")
    for row in result.rows:
        amount = row.price * row.quantity
        result.cash_delta += (amount if row.side == "sell" else -amount) - row.fee
        result.total_fee += row.fee
        if row.side == "sell" and row.position_id in context.positions:
            position = context.positions[row.position_id]
            cost = Decimal(str(position["buy_price"])) * row.quantity
            cost += Decimal(str(position["buy_fee"])) * row.quantity / Decimal(str(position["quantity"]))
            row.realized_pnl = (amount-row.fee-cost).quantize(QUANT)
            result.realized_pnl += row.realized_pnl
    expected_cash = sum(((f.price*f.quantity if f.side == "sell" else -f.price*f.quantity)-f.fee
                         for f in draft.fills), Decimal("0"))
    if result.cash_delta != expected_cash:
        errors.append("배분 금액과 실제 체결 순금액이 일치하지 않습니다.")
    result.blocking_errors = list(dict.fromkeys(errors))
    return result
