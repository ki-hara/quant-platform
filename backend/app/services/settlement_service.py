import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, update

from app.core.config import settings
from app.domain.enums import PositionStatus, StrategyMode, TradeSide, TradeSource, LocOrderStatus
from app.domain.models import (StrategyConfig, OrderSnapshot, OrderSnapshotInvalidation, TradeSettlement, Position,
                               Trade, LivePortfolio, PortfolioAdjustment, LocOrder)
from app.dto.settlements import SettlementDraftDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.market_session_service import latest_confirmed_market_date
from app.services.exchange_calendar_service import is_exchange_trading_day, count_exchange_trading_days
from app.services.order_snapshot_service import json_value
from app.services.position_exit_policy import build_position_exit_policy
from app.services.settlement_allocation import SettlementContext, calculate_settlement


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def state_of(row):
    return {c.name: json_value(getattr(row, c.name)) if not isinstance(getattr(row, c.name), datetime)
            else getattr(row, c.name).isoformat() for c in row.__table__.columns}


def restore(row, values):
    for column in row.__table__.columns:
        value = values[column.name]
        if value is not None:
            python_type = column.type.python_type
            if python_type in (datetime, date):
                value = python_type.fromisoformat(value)
            elif python_type is Decimal:
                value = Decimal(value)
            elif hasattr(python_type, "__members__"):
                value = python_type(value)
        setattr(row, column.name, value)


class SettlementService:
    def __init__(self, session):
        self.session = session

    def config(self, config_id):
        config = self.session.get(StrategyConfig, config_id)
        if config is None or config.strategy_type != "dynamic_wave":
            raise ValueError("동파법 전략만 정산할 수 있습니다.")
        return config

    def get(self, settlement_id):
        record = self.session.get(TradeSettlement, settlement_id)
        if record is None:
            raise ValueError("정산 내역을 찾을 수 없습니다.")
        return record

    def ledger(self, config_id):
        result = {}
        for model in (LivePortfolio, Position, Trade, PortfolioAdjustment, LocOrder):
            rows = self.session.scalars(select(model).where(model.strategy_config_id == config_id))
            result[model.__tablename__] = [state_of(row) for row in rows]
        return result

    def context(self, config_id, draft):
        config = self.config(config_id)
        snapshot = self.session.get(OrderSnapshot, draft.snapshot_id) if draft.snapshot_id else None
        if draft.snapshot_id and (snapshot is None or snapshot.config_id != config_id
                                  or snapshot.trade_date != draft.trade_date):
            raise ValueError("거래일과 주문표 저장본을 확인해 주세요.")
        positions = list(self.session.scalars(select(Position).where(Position.strategy_config_id == config_id)))
        if snapshot:
            if self.session.get(OrderSnapshotInvalidation, snapshot.id) is not None:
                raise ValueError("거래 내역 재구성으로 저장본의 포지션 연결이 무효화되었습니다. 수동 배분으로 확인해 주세요.")
            if snapshot.payload_json["symbol"] != config.symbol:
                raise ValueError("저장본과 현재 종목이 다릅니다.")
            sources = {s["id"]: s for s in snapshot.payload_json["sources"]}
        else:
            sources = {f"sell:{p.id}": dict(id=f"sell:{p.id}", side="sell", position_id=p.id,
                        quantity=int(p.quantity), limit_price=str(p.sell_limit_price) if p.sell_limit_price else None,
                        execution="loc", buy_date=str(p.buy_date), buy_price=str(p.buy_price))
                       for p in positions if p.status == PositionStatus.OPEN}
            sources["buy:manual"] = dict(id="buy:manual", side="buy", position_id=None,
                                         quantity=100000000, limit_price=None, execution="loc")
            for p in positions:
                if p.status == PositionStatus.OPEN:
                    source = sources[f"sell:{p.id}"]
                    due = p.max_holding_days is not None and count_exchange_trading_days(
                        config.symbol, p.buy_date, draft.trade_date) >= p.max_holding_days
                    if due:
                        source['execution'] = 'market_on_close'
                elif p.status == PositionStatus.PENDING and p.buy_date == draft.trade_date:
                    sources[f"buy:{p.id}"] = dict(id=f"buy:{p.id}", side="buy", position_id=p.id,
                        quantity=int(p.quantity), limit_price=str(p.limit_price or p.buy_price),
                        execution="loc", buy_date=str(p.buy_date), buy_price=str(p.buy_price))
        close = None
        if draft.trade_date <= latest_confirmed_market_date(config.symbol):
            quote = MarketPriceRepository(self.session).latest_price_on_or_before(
                settings.market_data_provider, config.symbol, draft.trade_date)
            if quote is not None and quote.date == draft.trade_date:
                close = quote.close
        return SettlementContext(sources, close, {p.id: state_of(p) for p in positions})

    def save_draft(self, config_id, draft, expected_revision=None, settlement_id=None):
        self.context(config_id, draft)
        if settlement_id is None:
            record = TradeSettlement(config_id=config_id, snapshot_id=draft.snapshot_id,
                                     trade_date=draft.trade_date, draft_json=draft.model_dump(mode="json"))
            self.session.add(record)
        else:
            changed = self.session.execute(update(TradeSettlement).where(
                TradeSettlement.id == settlement_id, TradeSettlement.config_id == config_id,
                TradeSettlement.status == "draft", TradeSettlement.revision == expected_revision
            ).values(draft_json=draft.model_dump(mode="json"), snapshot_id=draft.snapshot_id,
                     trade_date=draft.trade_date, revision=TradeSettlement.revision+1, preview_hash=None))
            if changed.rowcount != 1:
                self.session.rollback()
                raise ValueError("초안이 변경되었거나 이미 확정되었습니다. 다시 불러와 주세요.")
            record = self.get(settlement_id)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _preview(self, record):
        draft = SettlementDraftDto.model_validate(record.draft_json)
        context = self.context(record.config_id, draft)
        result = calculate_settlement(draft, context)
        if record.snapshot_id and self.session.scalar(select(TradeSettlement.id).where(
            TradeSettlement.snapshot_id == record.snapshot_id,
            TradeSettlement.status == "confirmed", TradeSettlement.id != record.id).limit(1)):
            result.blocking_errors.append("이 주문표는 이미 정산되었습니다. 기존 정산을 확인해 주세요.")
        config = self.config(record.config_id)
        if not is_exchange_trading_day(config.symbol, draft.trade_date):
            result.blocking_errors.append("해당 날짜는 거래일이 아닙니다.")
        if draft.trade_date > latest_confirmed_market_date(config.symbol):
            result.blocking_errors.append("마감이 확인된 거래일만 정산할 수 있습니다.")
        for row in result.rows:
            p = context.positions.get(row.position_id)
            if p and date.fromisoformat(p["buy_date"]) > draft.trade_date:
                result.blocking_errors.append("매수일 이전에는 매도할 수 없습니다.")
            if row.side == "buy" and p and p["buy_date"] != str(draft.trade_date):
                result.blocking_errors.append("대기 매수의 거래일이 다릅니다.")
            if row.side == "buy" and not row.position_id and any(
                candidate["status"] == "pending" and candidate["buy_date"] == str(draft.trade_date)
                for candidate in context.positions.values()
            ):
                result.blocking_errors.append("같은 거래일의 대기 매수를 연결해 주세요. 중복 생성을 막기 위해 신규 생성을 보류합니다.")
        if any(r.side == "buy" and not (
            r.position_id in context.positions
            and context.positions[r.position_id]["status"] == "pending"
        ) for r in result.rows) and not draft.snapshot_id and not draft.manual_buy_settings:
            result.blocking_errors.append("당시 매수 모드·익절률·보유기간을 입력해 주세요.")
        portfolio = self.session.get(LivePortfolio, record.config_id)
        if portfolio is None or portfolio.cash + result.cash_delta < 0:
            result.blocking_errors.append("정산 후 현금이 부족합니다. 실제 입금 내역을 먼저 반영해 주세요.")
        result.preview_hash = digest([record.draft_json, self.ledger(record.config_id),
                                     state_of(config), str(context.close)])
        return result

    def preview(self, settlement_id):
        record = self.get(settlement_id)
        if record.status != "draft":
            raise ValueError("이미 처리된 정산입니다.")
        result = self._preview(record)
        record.preview_hash = result.preview_hash
        self.session.commit()
        return result

    def _lock(self, settlement_id):
        # Acquire SQLite's writer lock before reading the account state.
        self.session.execute(update(TradeSettlement).where(TradeSettlement.id == settlement_id)
                             .values(revision=TradeSettlement.revision))
        self.session.expire_all()
        return self.get(settlement_id)

    def confirm(self, settlement_id, preview_hash, idempotency_key):
        try:
            record = self._lock(settlement_id)
            if record.status == "confirmed" and record.idempotency_key == idempotency_key:
                result = record.result_json["response"]
                self.session.rollback()
                return result
            if record.status != "draft":
                raise ValueError("이미 처리된 정산입니다.")
            preview = self._preview(record)
            if preview.preview_hash != preview_hash or record.preview_hash != preview_hash:
                raise ValueError("계좌 또는 입력이 변경되었습니다. 배분을 다시 확인해 주세요.")
            if preview.blocking_errors:
                raise ValueError(" / ".join(preview.blocking_errors))
            before = self.ledger(record.config_id)
            result = self._apply(record, preview)
            self.session.flush()
            self.session.expire_all()
            record = self.get(settlement_id)
            record.status = "confirmed"
            record.idempotency_key = idempotency_key
            record.result_json = dict(response=result, before=before, after=self.ledger(record.config_id))
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def _apply(self, record, preview):
        draft = SettlementDraftDto.model_validate(record.draft_json)
        config = self.config(record.config_id)
        portfolio = self.session.get(LivePortfolio, record.config_id)
        before_cash = portfolio.cash
        trade_ids, position_ids = [], []
        for row in preview.rows:
            if row.side != "sell":
                continue
            result = ManualTradeService(self.session).record_manual_trade(ManualTradeRequest(
                config_id=config.id, side=TradeSide.SELL, trade_date=draft.trade_date,
                quantity=Decimal(row.quantity), price=row.price, fee=row.fee,
                position_id=row.position_id, sell_reason="settlement",
            ), commit=False)
            trade_ids.append(result.trade.id)
            position_ids.append(row.position_id)
        grouped = defaultdict(list)
        for row in preview.rows:
            if row.side == "buy":
                grouped[(row.source_id, row.position_id)].append(row)
        snapshot = self.session.get(OrderSnapshot, draft.snapshot_id) if draft.snapshot_id else None
        used_pending = set()
        for (source_id, pending_id), rows in grouped.items():
            if pending_id in used_pending:
                raise ValueError("같은 대기 매수를 여러 원주문에 연결할 수 없습니다.")
            if pending_id:
                used_pending.add(pending_id)
            quantity = sum(r.quantity for r in rows)
            gross = sum(r.quantity*r.price for r in rows)
            fee = sum(r.fee for r in rows)
            price = (gross/quantity).quantize(Decimal("0.000001"))
            pending = self.session.get(Position, pending_id) if pending_id else None
            if snapshot:
                mode = StrategyMode(snapshot.payload_json["mode"])
                policy = build_position_exit_policy(snapshot.payload_json["settings"], mode, price)
                threshold, limit, days = policy.sell_threshold_percent, policy.sell_limit_price, policy.max_holding_days
            elif pending:
                from app.services.position_exit_policy import sell_limit_price_for
                mode = pending.mode
                fallback = build_position_exit_policy(config.settings_json, mode, price)
                threshold = pending.sell_threshold_percent if pending.sell_threshold_percent is not None else fallback.sell_threshold_percent
                days = pending.max_holding_days if pending.max_holding_days is not None else fallback.max_holding_days
                limit = sell_limit_price_for(price, threshold)
            else:
                policy = draft.manual_buy_settings
                mode = StrategyMode(policy.mode)
                threshold, days = policy.sell_threshold_percent, policy.max_holding_days
                from app.services.position_exit_policy import sell_limit_price_for
                limit = sell_limit_price_for(price, threshold)
            if pending and pending.quantity == quantity:
                position = pending
                position.buy_price, position.buy_fee = price, fee
                position.status = PositionStatus.OPEN
                position.mode = mode
                position.sell_threshold_percent, position.sell_limit_price = threshold, limit
                position.max_holding_days = days
            else:
                if pending:
                    pending.quantity -= quantity
                position = PositionRepository(self.session).create_open(
                    config.id, draft.trade_date, price, Decimal(quantity), mode, fee,
                    sell_threshold_percent=threshold, sell_limit_price=limit, max_holding_days=days)
            self.session.flush()
            position_ids.append(position.id)
            for row in rows:
                trade = TradeRepository(self.session).create(
                    strategy_config_id=config.id, trade_date=draft.trade_date, side=TradeSide.BUY,
                    quantity=Decimal(row.quantity), price=row.price, fee=row.fee,
                    realized_pnl=Decimal("0"), sell_reason=None, source=TradeSource.MANUAL,
                    position_id=position.id)
                trade_ids.append(trade.id)
            if pending and pending.status == PositionStatus.OPEN:
                for order in self.session.scalars(select(LocOrder).where(LocOrder.position_id == pending.id)):
                    order.status = LocOrderStatus.FILLED
                    order.trade_id = trade_ids[-1]
            portfolio.cash -= gross + fee
            portfolio.cumulative_fees += fee
        if portfolio.cash - before_cash != preview.cash_delta:
            raise ValueError("정산 현금 검산에 실패했습니다.")
        return dict(settlement_id=record.id, status="confirmed", trade_ids=trade_ids,
                    position_ids=list(set(position_ids)), cash_delta=str(preview.cash_delta),
                    total_fee=str(preview.total_fee))

    def cancel(self, settlement_id):
        try:
            record = self._lock(settlement_id)
            if record.status == "cancelled":
                self.session.rollback()
                return dict(settlement_id=record.id, status="cancelled")
            if record.status != "confirmed":
                raise ValueError("확정된 정산만 취소할 수 있습니다.")
            stored = record.result_json
            if digest(self.ledger(record.config_id)) != digest(stored["after"]):
                raise ValueError("후속 거래나 계좌 변경이 있어 취소할 수 없습니다.")
            before = stored["before"]
            for model in (LocOrder, Trade, Position, LivePortfolio):
                key = model.__tablename__
                previous = {str(v.get("id", v.get("strategy_config_id"))): v for v in before[key]}
                for row in list(self.session.scalars(select(model).where(model.strategy_config_id == record.config_id))):
                    identity = str(getattr(row, "id", row.strategy_config_id))
                    if identity in previous:
                        restore(row, previous[identity])
                    else:
                        self.session.delete(row)
                self.session.flush()
            record.status = "cancelled"
            self.session.commit()
            return dict(settlement_id=record.id, status="cancelled")
        except Exception:
            self.session.rollback()
            raise
