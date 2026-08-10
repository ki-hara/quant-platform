from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import GoldToiletAccount, GoldToiletOrderSheet


class GoldToiletOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_account(self, owner_id: str) -> GoldToiletAccount | None:
        return self.session.get(GoldToiletAccount, owner_id)

    def save_account(self, owner_id: str, capital: Decimal, cash: Decimal) -> GoldToiletAccount:
        account = self.get_account(owner_id)
        if account is None:
            account = GoldToiletAccount(owner_id=owner_id, capital=capital, cash=cash)
        else:
            account.capital = capital
            account.cash = cash
        self.session.add(account)
        self.session.flush()
        self.session.refresh(account)
        return account

    def get_sheet(self, owner_id: str, order_date: date) -> GoldToiletOrderSheet | None:
        statement = select(GoldToiletOrderSheet).where(
            GoldToiletOrderSheet.owner_id == owner_id,
            GoldToiletOrderSheet.order_date == order_date,
        )
        return self.session.scalar(statement)

    def list_unresolved_sheets(self, order_date: date) -> list[GoldToiletOrderSheet]:
        statement = select(GoldToiletOrderSheet).where(
            GoldToiletOrderSheet.order_date == order_date,
            GoldToiletOrderSheet.provider_market_open.is_(None),
        )
        return list(self.session.scalars(statement))

    def save_sheet(
        self,
        *,
        owner_id: str,
        order_date: date,
        entry_percent: Decimal,
        allocation_percent: Decimal,
        loc_percent: Decimal,
    ) -> GoldToiletOrderSheet:
        sheet = self.get_sheet(owner_id, order_date)
        if sheet is None:
            sheet = GoldToiletOrderSheet(owner_id=owner_id, order_date=order_date)
        sheet.entry_percent = entry_percent
        sheet.allocation_percent = allocation_percent
        sheet.loc_percent = loc_percent
        self.session.add(sheet)
        self.session.flush()
        self.session.refresh(sheet)
        return sheet

    def snapshot_provider_open(
        self,
        sheet: GoldToiletOrderSheet,
        market_open: Decimal,
        observed_at: datetime,
    ) -> GoldToiletOrderSheet:
        if sheet.provider_market_open is None:
            sheet.provider_market_open = market_open
            sheet.provider_open_observed_at = observed_at
            sheet.provider_open_source = "yahoo_1d_regular_session"
        sheet.provider_open_last_checked_at = observed_at
        sheet.provider_open_failure_reason = None
        return self.save(sheet)

    def record_provider_failure(
        self, sheet: GoldToiletOrderSheet, reason: str, checked_at: datetime
    ) -> GoldToiletOrderSheet:
        sheet.provider_open_last_checked_at = checked_at
        sheet.provider_open_failure_reason = reason
        return self.save(sheet)

    def set_manual_open(
        self, sheet: GoldToiletOrderSheet, market_open: Decimal, observed_at: datetime
    ) -> GoldToiletOrderSheet:
        sheet.manual_market_open = market_open
        sheet.manual_open_observed_at = observed_at
        return self.save(sheet)

    def clear_manual_open(self, sheet: GoldToiletOrderSheet) -> GoldToiletOrderSheet:
        sheet.manual_market_open = None
        sheet.manual_open_observed_at = None
        return self.save(sheet)

    def save(self, sheet: GoldToiletOrderSheet) -> GoldToiletOrderSheet:
        self.session.add(sheet)
        self.session.flush()
        self.session.refresh(sheet)
        return sheet
