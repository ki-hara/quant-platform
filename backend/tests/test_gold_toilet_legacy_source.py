from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.domain.models import Owner
from app.infrastructure.market_data.regular_open import RegularOpenLookup
from app.infrastructure.repositories.gold_toilet_orders import GoldToiletOrderRepository
from app.services.gold_toilet_order_interpreter import GoldToiletOrderInterpreter


class UnusedProvider:
    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        raise AssertionError("historical saved rows must not call a provider")


def test_historical_yahoo_source_remains_api_compatible() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Owner(id="default", name="Default"))
        repository = GoldToiletOrderRepository(session)
        sheet = repository.save_sheet(
            owner_id="default",
            order_date=date(2026, 8, 4),
            entry_percent=Decimal("1.49"),
            allocation_percent=Decimal("22.5"),
            loc_percent=Decimal("-9.34"),
        )
        sheet.provider_market_open = Decimal("131.505")
        sheet.provider_open_source = "yahoo_1d_regular_session"
        session.commit()

        response = GoldToiletOrderInterpreter(session, UnusedProvider()).get(
            "default", date(2026, 8, 4)
        )

        assert response.sheet is not None
        assert response.sheet.effective_open_source == "yahoo_1d_regular_session"
