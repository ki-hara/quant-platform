from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.models import Owner


def test_seed_default_owner_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_default_owner(session, "default")
        seed_default_owner(session, "default")
        owners = session.scalars(select(Owner)).all()

    assert len(owners) == 1
    assert owners[0].id == "default"
