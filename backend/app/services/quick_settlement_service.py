from decimal import Decimal

from app.dto.settlements import SettlementDraftDto
from app.services.settlement_service import SettlementService, digest, state_of


class QuickSettlementService:
    def __init__(self, session):
        self.service = SettlementService(session)

    def candidates(self, config_id, trade_date):
        config = self.service.config(config_id)
        context = self.service.context(config_id, SettlementDraftDto(trade_date=trade_date))
        rows = []
        for source in context.sources.values():
            position = context.positions.get(source.get('position_id'))
            if not position or position['buy_date'] > str(trade_date):
                continue
            side = source['side']
            limit = Decimal(source['limit_price']) if source['limit_price'] else None
            due = source['execution'] == 'market_on_close'
            matched = context.close is not None and limit is not None and (
                context.close >= limit if side == 'sell' else context.close <= limit)
            rows.append(dict(position_id=source['position_id'], source_id=source['id'], side=side,
                buy_date=position['buy_date'], buy_price=position['buy_price'], quantity=int(Decimal(position['quantity'])),
                limit_price=source['limit_price'], price=str(context.close) if context.close is not None else None,
                selected=bool(context.close is not None and (due or matched)),
                eligible=True,
                reason='maturity' if due else
                       'profit' if matched and side=='sell' else 'buy' if matched else 'holding'))
        rows.sort(key=lambda r: (r['side']=='buy', r['buy_date'], r['position_id']))
        return dict(trade_date=str(trade_date), close=str(context.close) if context.close is not None else None,
            rows=rows, state_hash=digest([self.service.ledger(config_id), state_of(config), str(context.close)]))

    def prepare(self, config_id, trade_date, state_hash, selections, netting):
        candidates = self.candidates(config_id, trade_date)
        if candidates['state_hash'] != state_hash:
            raise ValueError('포지션 또는 시세가 변경되었습니다. 후보를 다시 조회해 주세요.')
        available = {r['position_id']: r for r in candidates['rows']}
        chosen, seen = [], set()
        for selection in selections:
            row = available.get(selection['position_id'])
            if not row or not row['eligible'] or row['position_id'] in seen:
                raise ValueError('선택한 포지션의 상태를 확인해 주세요.')
            seen.add(row['position_id'])
            if not 0 < selection['quantity'] <= row['quantity'] or selection['price'] <= 0:
                raise ValueError('체결 수량과 가격을 확인해 주세요.')
            chosen.append(dict(row, **{k: selection[k] for k in ('quantity', 'price', 'fee')}))
        if not chosen:
            raise ValueError('반영할 포지션을 선택해 주세요.')
        close = Decimal(candidates['close']) if candidates['close'] else None
        # Only unchanged closing-price rows can offset; edited fills keep their actual price.
        offset = min(sum(r['quantity'] for r in chosen if r['side']==side and r['price']==close)
                     for side in ('buy', 'sell')) if netting and close is not None else 0
        remaining = dict(buy=offset, sell=offset)
        fills, allocations = [], []
        config = self.service.config(config_id)
        for row in chosen:
            internal = min(row['quantity'], remaining[row['side']]) if row['price']==close else 0
            remaining[row['side']] -= internal
            actual = row['quantity'] - internal
            common = dict(source_id=row['source_id'], side=row['side'], position_id=row['position_id'],
                          change_reason='일괄 반영에서 실제 체결 확인')
            if internal:
                allocations.append(dict(common, quantity=internal, kind='offset'))
            if actual:
                fill_id = f"quick:{row['position_id']}"
                fee = row['fee'] if row['fee'] is not None else (
                    row['price']*actual*config.fee_rate/100).quantize(Decimal('0.000001'))
                fills.append(dict(id=fill_id, side=row['side'], quantity=actual, price=row['price'], fee=fee))
                allocations.append(dict(common, quantity=actual, kind='actual', fill_id=fill_id))
            elif row['fee']:
                raise ValueError('전량 상계 포지션에는 실제 체결 수수료를 입력할 수 없습니다.')
        draft = SettlementDraftDto(trade_date=trade_date, fills=fills, allocations=allocations)
        record = self.service.save_draft(config_id, draft)
        preview = self.service.preview(record.id)
        return dict(record=record, preview=preview, offset_quantity=offset,
            actual_buy=sum(f['quantity'] for f in fills if f['side']=='buy'),
            actual_sell=sum(f['quantity'] for f in fills if f['side']=='sell'))
