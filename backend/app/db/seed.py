from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_pin
from app.domain.models import Owner


def seed_default_owner(session: Session, owner_id: str) -> None:
    owner = session.get(Owner, owner_id)
    if owner is None:
        try:
            session.add(Owner(id=owner_id, name="Default", pin_hash=hash_pin(settings.default_owner_pin)))
            session.commit()
        except IntegrityError:
            session.rollback()
    elif not owner.pin_hash:
        owner.pin_hash = hash_pin(settings.default_owner_pin)
        owner.is_active = True
        session.add(owner)
        session.commit()
