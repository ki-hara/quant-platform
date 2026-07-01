from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_pin
from app.domain.models import Owner


def seed_default_owner(session: Session, owner_id: str) -> None:
    owner = session.get(Owner, owner_id)
    if owner is None:
        try:
            session.add(
                Owner(
                    id=owner_id,
                    name="Default",
                    pin_hash=hash_pin(settings.default_owner_pin),
                    is_active=True,
                    is_admin=True,
                )
            )
            session.commit()
        except IntegrityError:
            session.rollback()
    else:
        changed = False
        if not owner.pin_hash:
            owner.pin_hash = hash_pin(settings.default_owner_pin)
            changed = True
        if not owner.is_active:
            owner.is_active = True
            changed = True
        if not owner.is_admin:
            owner.is_admin = True
            changed = True
        if changed:
            session.add(owner)
            session.commit()

    guest = session.get(Owner, "guest")
    if guest is None:
        try:
            session.add(
                Owner(
                    id="guest",
                    name="Guest",
                    pin_hash=hash_pin(settings.default_owner_pin),
                    is_active=True,
                    is_admin=False,
                )
            )
            session.commit()
        except IntegrityError:
            session.rollback()
    elif not guest.pin_hash:
        guest.pin_hash = hash_pin(settings.default_owner_pin)
        guest.is_active = True
        guest.is_admin = False
        session.add(guest)
        session.commit()
