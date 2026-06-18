from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import create_engine_kwargs
from app.dto.market_data import OhlcvDto
from app.domain.models import Owner
from app.infrastructure.repositories.market_data import MarketPriceRepository


def test_create_engine_kwargs_adds_sqlite_thread_check_override() -> None:
    assert create_engine_kwargs("sqlite:///./quant_platform.db") == {
        "connect_args": {"check_same_thread": False}
    }


def test_create_engine_kwargs_omits_sqlite_args_for_postgresql() -> None:
    assert create_engine_kwargs("postgresql+psycopg://user:pass@example.com/app") == {}


def test_seed_default_owner_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_default_owner(session, "default")
        seed_default_owner(session, "default")
        owners = session.scalars(select(Owner)).all()

    assert len(owners) == 1
    assert owners[0].id == "default"


def test_market_price_repository_upserts_and_lists_prices_by_symbol_and_range() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MarketPriceRepository(session)
        repository.upsert_prices(
            "test-provider",
            [
                OhlcvDto(
                    symbol="005930",
                    date=date(2024, 1, 3),
                    open=Decimal("100"),
                    high=Decimal("110"),
                    low=Decimal("95"),
                    close=Decimal("105"),
                    volume=1000,
                ),
                OhlcvDto(
                    symbol="005930",
                    date=date(2024, 1, 2),
                    open=Decimal("90"),
                    high=Decimal("108"),
                    low=Decimal("89"),
                    close=Decimal("100"),
                    volume=900,
                ),
            ],
        )

        prices = repository.list_prices(
            "test-provider",
            "005930",
            date(2024, 1, 2),
            date(2024, 1, 3),
        )

    assert [price.date for price in prices] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [price.symbol for price in prices] == ["005930", "005930"]
    assert [price.close for price in prices] == [Decimal("100.000000"), Decimal("105.000000")]
    assert [int(price.volume) for price in prices] == [900, 1000]
