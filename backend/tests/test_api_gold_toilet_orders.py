from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes_gold_toilet_orders import get_gold_toilet_market_provider
from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import get_session
from app.infrastructure.market_data.yahoo_regular_open_provider import (
    RegularOpenLookup,
    RegularSessionOpen,
)
from app.main import create_app
from app.services.gold_toilet_order_interpreter import classify_open_status


class FakeRegularOpenProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.lookup = RegularOpenLookup(
            RegularSessionOpen(
                symbol="SOXL",
                session_date=date(2026, 8, 4),
                price=Decimal("48.25"),
                high=Decimal("49"),
                low=Decimal("48"),
                bar_time=datetime(2026, 8, 4, 9, 30),
            )
        )

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        self.calls += 1
        return self.lookup


@pytest.fixture
def gold_toilet_client() -> Generator[tuple[TestClient, FakeRegularOpenProvider], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    provider = FakeRegularOpenProvider()
    app = create_app(database_engine=engine, session_factory=lambda: Session(engine))
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_gold_toilet_market_provider] = lambda: provider
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"owner_id": "default", "pin": "0000"})
    client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
    yield client, provider
    client.close()


def _save_account_and_sheet(client: TestClient) -> None:
    assert (
        client.put(
            "/api/gold-toilet/account", json={"capital": "10000", "cash": "5000"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/gold-toilet/order-sheet/2026-08-04",
            json={
                "entry_percent": "1.49",
                "allocation_percent": "22.5",
                "loc_percent": "-9.34",
            },
        ).status_code
        == 200
    )


def test_manual_override_returns_three_outputs_and_preserves_provider_open(
    gold_toilet_client,
) -> None:
    client, _ = gold_toilet_client
    _save_account_and_sheet(client)

    response = client.put(
        "/api/gold-toilet/order-sheet/2026-08-04/manual-open",
        json={"market_open": "48.25"},
    )

    assert response.status_code == 200
    sheet = response.json()["sheet"]
    calculation = response.json()["calculation"]
    assert sheet["provider_market_open"] == "48.250000"
    assert sheet["manual_market_open"] == "48.250000"
    assert sheet["effective_market_open"] == "48.250000"
    assert sheet["effective_open_source"] == "manual"
    assert calculation["breakout_buy_price"] == "48.97"
    assert calculation["order_quantity"] == 51
    assert calculation["loc_buy_price"] == "43.74"


def test_provider_open_is_snapshotted_only_once(gold_toilet_client) -> None:
    client, provider = gold_toilet_client
    _save_account_and_sheet(client)
    provider.lookup = RegularOpenLookup(
        RegularSessionOpen(
            symbol="SOXL",
            session_date=date(2026, 8, 4),
            price=Decimal("49"),
            high=Decimal("49"),
            low=Decimal("49"),
            bar_time=datetime(2026, 8, 4, 9, 30),
        )
    )

    first = client.get("/api/gold-toilet/order-sheet", params={"order_date": "2026-08-04"})
    second = client.get("/api/gold-toilet/order-sheet", params={"order_date": "2026-08-04"})

    assert first.json()["sheet"]["provider_market_open"] == "48.250000"
    assert second.json()["sheet"]["provider_market_open"] == "48.250000"
    assert second.json()["sheet"]["provider_open_source"] == "yahoo_1d_regular_session"
    assert provider.calls == 1


def test_sheet_save_rejects_embedded_manual_open(gold_toilet_client) -> None:
    client, _ = gold_toilet_client
    response = client.put(
        "/api/gold-toilet/order-sheet/2026-08-04",
        json={
            "entry_percent": "1.49",
            "allocation_percent": "22.5",
            "loc_percent": "-9.34",
            "market_open": "131.5",
        },
    )
    assert response.status_code == 422


def test_allocation_amount_is_returned_before_market_open(gold_toilet_client) -> None:
    client, provider = gold_toilet_client
    provider.lookup = RegularOpenLookup(None, "opening_bar_not_available")
    _save_account_and_sheet(client)

    response = client.get("/api/gold-toilet/order-sheet", params={"order_date": "2026-08-04"})

    assert response.status_code == 200
    assert response.json()["allocation_amount"] == "2250.00"
    assert response.json()["calculation"] is None


def test_manual_open_is_rejected_until_provider_open_exists(gold_toilet_client) -> None:
    client, provider = gold_toilet_client
    provider.lookup = RegularOpenLookup(None, "opening_bar_not_available")
    _save_account_and_sheet(client)

    response = client.put(
        "/api/gold-toilet/order-sheet/2026-08-04/manual-open",
        json={"market_open": "131.5"},
    )

    assert response.status_code == 409
    waiting = client.get("/api/gold-toilet/order-sheet", params={"order_date": "2026-08-04"}).json()
    assert waiting["calculation"] is None
    assert waiting["open_failure_reason"] == "opening_bar_not_available"


def test_manual_open_can_be_cleared_back_to_provider_value(gold_toilet_client) -> None:
    client, _ = gold_toilet_client
    _save_account_and_sheet(client)
    client.put(
        "/api/gold-toilet/order-sheet/2026-08-04/manual-open",
        json={"market_open": "47.00"},
    )

    response = client.delete("/api/gold-toilet/order-sheet/2026-08-04/manual-open")

    assert response.status_code == 200
    sheet = response.json()["sheet"]
    assert sheet["manual_market_open"] is None
    assert sheet["effective_market_open"] == "48.250000"
    assert sheet["effective_open_source"] == "yahoo_1d_regular_session"


def test_status_becomes_failed_five_minutes_after_open() -> None:
    assert (
        classify_open_status(
            date(2026, 8, 4),
            False,
            datetime(2026, 8, 4, 13, 34, tzinfo=UTC),
        )
        == "waiting"
    )
    assert (
        classify_open_status(
            date(2026, 8, 4),
            False,
            datetime(2026, 8, 4, 13, 35, tzinfo=UTC),
        )
        == "failed"
    )
