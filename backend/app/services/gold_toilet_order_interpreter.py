from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.domain.models import GoldToiletOrderSheet
from app.dto.gold_toilet_orders import GoldToiletOrderResponseDto, GoldToiletOrderSheetDto
from app.infrastructure.market_data.yahoo_regular_open_provider import RegularOpenLookup
from app.infrastructure.repositories.gold_toilet_orders import GoldToiletOrderRepository
from app.services.gold_toilet_order_service import (
    calculate_allocation_amount,
    calculate_gold_toilet_order,
)


class MarketProvider(Protocol):
    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup: ...


NEW_YORK = ZoneInfo("America/New_York")


def manual_open_allowed(order_date: date, now: datetime) -> bool:
    aware_now = now.replace(tzinfo=UTC) if now.tzinfo is None else now
    session_start = datetime.combine(order_date, time(9, 30), NEW_YORK)
    return aware_now.astimezone(NEW_YORK) >= session_start


class GoldToiletOrderInterpreter:
    def __init__(self, session: Session, market_provider: MarketProvider) -> None:
        self.session = session
        self.market_provider = market_provider
        self.repository = GoldToiletOrderRepository(session)

    def get(self, owner_id: str, order_date: date, *, capture_open: bool = True):
        account = self.repository.get_account(owner_id)
        sheet = self.repository.get_sheet(owner_id, order_date)
        if capture_open and sheet is not None and sheet.provider_market_open is None:
            self._capture_market_open(sheet)
        return self._response(account, sheet)

    def update_account(self, owner_id: str, capital: Decimal, cash: Decimal):
        self.repository.save_account(owner_id, capital, cash)
        self.session.commit()
        return self.get(owner_id, date.today(), capture_open=False)

    def update_sheet(
        self,
        owner_id: str,
        order_date: date,
        entry_percent: Decimal,
        allocation_percent: Decimal,
        loc_percent: Decimal,
    ):
        sheet = self.repository.save_sheet(
            owner_id=owner_id,
            order_date=order_date,
            entry_percent=entry_percent,
            allocation_percent=allocation_percent,
            loc_percent=loc_percent,
        )
        self.session.commit()
        if sheet.provider_market_open is None:
            self._capture_market_open(sheet)
        self.session.commit()
        return self.get(owner_id, order_date, capture_open=False)

    def set_manual_open(self, owner_id: str, order_date: date, market_open: Decimal):
        sheet = self._require_sheet(owner_id, order_date)
        observed_at = self._now()
        if not manual_open_allowed(order_date, observed_at):
            raise ValueError("뉴욕 정규장 시작 후 시가를 직접 입력할 수 있습니다.")
        self.repository.set_manual_open(sheet, market_open, observed_at)
        self.session.commit()
        return self.get(owner_id, order_date, capture_open=False)

    def clear_manual_open(self, owner_id: str, order_date: date):
        sheet = self._require_sheet(owner_id, order_date)
        self.repository.clear_manual_open(sheet)
        self.session.commit()
        return self.get(owner_id, order_date, capture_open=False)

    def _capture_market_open(self, sheet) -> None:
        lookup = self.market_provider.get_open("SOXL", sheet.order_date)
        checked_at = self._now()
        if lookup.quote is None:
            self.repository.record_provider_failure(
                sheet,
                lookup.failure_reason or "opening_price_provider_unavailable",
                checked_at,
            )
        else:
            self.repository.snapshot_provider_open(sheet, lookup.quote.price, checked_at)
        self.session.commit()

    def _response(self, account, sheet) -> GoldToiletOrderResponseDto:
        calculation = None
        allocation_amount = None
        effective_open = None
        effective_source = None
        sheet_dto = None
        open_status = "waiting"
        failure_reason = None
        observed_at = self._now()
        allow_manual_open = False
        if sheet is not None:
            effective_open, effective_source = self._effective_open(sheet)
            allow_manual_open = manual_open_allowed(sheet.order_date, observed_at)
            open_status = classify_open_status(
                sheet.order_date,
                effective_open is not None,
                observed_at,
            )
            failure_reason = sheet.provider_open_failure_reason
            sheet_dto = GoldToiletOrderSheetDto(
                order_date=sheet.order_date,
                entry_percent=sheet.entry_percent,
                allocation_percent=sheet.allocation_percent,
                loc_percent=sheet.loc_percent,
                provider_market_open=sheet.provider_market_open,
                provider_open_observed_at=sheet.provider_open_observed_at,
                provider_open_source=sheet.provider_open_source,
                provider_open_last_checked_at=sheet.provider_open_last_checked_at,
                provider_open_failure_reason=sheet.provider_open_failure_reason,
                manual_market_open=sheet.manual_market_open,
                manual_open_observed_at=sheet.manual_open_observed_at,
                effective_market_open=effective_open,
                effective_open_source=effective_source,
                updated_at=sheet.updated_at,
            )
        if account is not None and sheet is not None:
            allocation_amount = calculate_allocation_amount(
                account.capital, sheet.allocation_percent
            )
            if effective_open is not None:
                calculation = calculate_gold_toilet_order(
                    capital=account.capital,
                    cash=account.cash,
                    market_open=effective_open,
                    entry_percent=sheet.entry_percent,
                    allocation_percent=sheet.allocation_percent,
                    loc_percent=sheet.loc_percent,
                )
        return GoldToiletOrderResponseDto(
            account=account,
            sheet=sheet_dto,
            calculation=calculation,
            allocation_amount=allocation_amount,
            manual_open_allowed=allow_manual_open,
            open_status=open_status,
            open_failure_reason=failure_reason,
        )

    def _require_sheet(self, owner_id: str, order_date: date) -> GoldToiletOrderSheet:
        sheet = self.repository.get_sheet(owner_id, order_date)
        if sheet is None:
            raise LookupError("황금변기 주문표를 찾을 수 없습니다.")
        return sheet

    @staticmethod
    def _effective_open(
        sheet: GoldToiletOrderSheet,
    ) -> tuple[Decimal | None, str | None]:
        if sheet.manual_market_open is not None:
            return sheet.manual_market_open, "manual"
        if sheet.provider_market_open is None:
            return None, None
        return sheet.provider_market_open, "yahoo_1d_regular_session"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)


def classify_open_status(order_date: date, has_open: bool, now: datetime) -> str:
    if has_open:
        return "ready"
    aware_now = now.replace(tzinfo=UTC) if now.tzinfo is None else now
    failed_at = datetime.combine(order_date, time(9, 35), NEW_YORK)
    return "failed" if aware_now.astimezone(NEW_YORK) >= failed_at else "waiting"
