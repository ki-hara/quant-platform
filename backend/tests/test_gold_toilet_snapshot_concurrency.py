from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.domain.models import Owner
from app.infrastructure.repositories.gold_toilet_orders import GoldToiletOrderRepository


def test_first_provider_snapshot_wins_across_concurrent_sessions() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        setup.add(Owner(id="default", name="Default"))
        GoldToiletOrderRepository(setup).save_sheet(
            owner_id="default",
            order_date=date(2026, 8, 12),
            entry_percent=Decimal("1.49"),
            allocation_percent=Decimal("22.5"),
            loc_percent=Decimal("-9.34"),
        )
        setup.commit()

    with Session(engine) as first, Session(engine) as second:
        first_repo = GoldToiletOrderRepository(first)
        second_repo = GoldToiletOrderRepository(second)
        first_sheet = first_repo.get_sheet("default", date(2026, 8, 12))
        second_sheet = second_repo.get_sheet("default", date(2026, 8, 12))
        assert first_sheet is not None and second_sheet is not None

        first_repo.snapshot_provider_open(
            first_sheet,
            Decimal("147.30"),
            "cnbc_us_quote",
            datetime(2026, 8, 12, 13, 30),
        )
        first.commit()
        second_repo.snapshot_provider_open(
            second_sheet,
            Decimal("146.62"),
            "finnhub_us_quote",
            datetime(2026, 8, 12, 13, 30, 1),
        )
        second.commit()

    with Session(engine) as check:
        saved = GoldToiletOrderRepository(check).get_sheet(
            "default", date(2026, 8, 12)
        )
        assert saved is not None
        assert saved.provider_market_open == Decimal("147.300000")
        assert saved.provider_open_source == "cnbc_us_quote"
