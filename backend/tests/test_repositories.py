from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import create_engine_kwargs
from app.domain.models import Owner


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
