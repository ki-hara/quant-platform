from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Owner


def seed_default_owner(session: Session, owner_id: str) -> None:
    owner = session.get(Owner, owner_id)
    if owner is None:
        try:
            session.add(Owner(id=owner_id, name="Default"))
            session.commit()
        except IntegrityError:
            session.rollback()
