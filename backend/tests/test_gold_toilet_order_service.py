from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.domain.models import Owner
from app.infrastructure.repositories.gold_toilet_orders import GoldToiletOrderRepository

from app.services.gold_toilet_order_service import calculate_gold_toilet_order


def test_calculation_uses_loc_price_for_one_shared_quantity() -> None:
    result = calculate_gold_toilet_order(
        capital=Decimal("10000"),
        cash=Decimal("5000"),
        market_open=Decimal("48.25"),
        entry_percent=Decimal("1.49"),
        allocation_percent=Decimal("22.5"),
        loc_percent=Decimal("-9.34"),
    )

    assert result.breakout_buy_price == Decimal("48.97")
    assert result.loc_buy_price == Decimal("43.74")
    assert result.order_quantity == 51
    assert result.allocation_amount == Decimal("2250.00")
    assert result.required_reservation_cash == Decimal("4728.21")
    assert result.cash_warning is False


def test_calculation_warns_without_reducing_quantity_when_cash_is_short() -> None:
    result = calculate_gold_toilet_order(
        capital=Decimal("10000"),
        cash=Decimal("4000"),
        market_open=Decimal("48.25"),
        entry_percent=Decimal("1.49"),
        allocation_percent=Decimal("22.5"),
        loc_percent=Decimal("-9.34"),
    )

    assert result.order_quantity == 51
    assert result.required_reservation_cash == Decimal("4728.21")
    assert result.cash_warning is True


def test_calculation_returns_zero_quantity_when_allocation_cannot_buy_one_share() -> None:
    result = calculate_gold_toilet_order(
        capital=Decimal("100"),
        cash=Decimal("100"),
        market_open=Decimal("48.25"),
        entry_percent=Decimal("1.49"),
        allocation_percent=Decimal("1"),
        loc_percent=Decimal("-9.34"),
    )

    assert result.order_quantity == 0
    assert result.required_reservation_cash == Decimal("0.00")
    assert result.cash_warning is False


def test_calculation_uses_whichever_order_price_is_lower() -> None:
    result = calculate_gold_toilet_order(
        capital=Decimal("1000"),
        cash=Decimal("3000"),
        market_open=Decimal("10"),
        entry_percent=Decimal("-10"),
        allocation_percent=Decimal("100"),
        loc_percent=Decimal("10"),
    )

    assert result.breakout_buy_price == Decimal("9.00")
    assert result.loc_buy_price == Decimal("11.00")
    assert result.order_quantity == 111


def test_repository_keeps_account_and_sheet_isolated_by_owner() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                Owner(id="owner-a", name="Owner A"),
                Owner(id="owner-b", name="Owner B"),
            ]
        )
        repository = GoldToiletOrderRepository(session)
        repository.save_account("owner-a", Decimal("10000"), Decimal("5000"))
        repository.save_sheet(
            owner_id="owner-a",
            order_date=date(2026, 8, 4),
            entry_percent=Decimal("1.49"),
            allocation_percent=Decimal("22.50"),
            loc_percent=Decimal("-9.34"),
        )
        session.commit()

        account = repository.get_account("owner-a")
        sheet = repository.get_sheet("owner-a", date(2026, 8, 4))

        assert account is not None
        assert account.capital == Decimal("10000.000000")
        assert account.cash == Decimal("5000.000000")
        assert sheet is not None
        assert sheet.entry_percent == Decimal("1.490000")
        repository.snapshot_provider_open(
            sheet, Decimal("131.505"), datetime(2026, 8, 4, 13, 30)
        )
        repository.set_manual_open(
            sheet, Decimal("131.50"), datetime(2026, 8, 4, 13, 31)
        )
        assert sheet.provider_market_open == Decimal("131.505000")
        assert sheet.manual_market_open == Decimal("131.500000")
        repository.clear_manual_open(sheet)
        assert sheet.manual_market_open is None
        assert repository.get_account("owner-b") is None
        assert repository.get_sheet("owner-b", date(2026, 8, 4)) is None
