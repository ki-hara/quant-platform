from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import routes_auth
from app.core.config import settings, validate_production_settings
from app.core.security import create_owner_token
from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import get_session
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_login_failures() -> Generator[None, None, None]:
    routes_auth._login_failures.clear()
    yield
    routes_auth._login_failures.clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as seed_session:
        seed_default_owner(seed_session, "default")

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app = create_app(database_engine=engine, session_factory=lambda: Session(engine))
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_owner_list_requires_login(client: TestClient) -> None:
    response = client.get("/api/auth/owners")

    assert response.status_code == 401


def test_query_string_token_is_not_accepted(client: TestClient) -> None:
    token = create_owner_token("default")

    response = client.get(f"/api/auth/me?access_token={token}")

    assert response.status_code == 401


def test_login_locks_after_repeated_failures(client: TestClient) -> None:
    for _ in range(routes_auth.MAX_LOGIN_FAILURES):
        response = client.post("/api/auth/login", json={"owner_id": "default", "pin": "9999"})
        assert response.status_code == 401

    locked = client.post("/api/auth/login", json={"owner_id": "default", "pin": "0000"})

    assert locked.status_code == 429


def test_production_rejects_default_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "default_owner_pin", "0000")
    monkeypatch.setattr(settings, "auth_secret", "change-this-on-server")

    with pytest.raises(RuntimeError, match="QUANT_DEFAULT_OWNER_PIN"):
        validate_production_settings()


def test_production_accepts_non_default_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "default_owner_pin", "4829")
    monkeypatch.setattr(settings, "auth_secret", "a-production-secret-with-more-than-32-characters")

    validate_production_settings()
