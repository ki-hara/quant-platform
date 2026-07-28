from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_pin
from app.domain.models import LivePortfolio, Owner, Position, StrategyConfig, Trade
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def test_integrated_orders_requires_login(test_client: TestClient) -> None:
    assert test_client.get("/api/integrated-orders").status_code == 401


def test_preferences_are_owner_scoped_and_get_lists_only_owned_configs(test_client: TestClient):
    test_client.post("/api/auth/owners", json={"id": "default", "name": "Default", "pin": "0000"})
    login = test_client.post("/api/auth/login", json={"owner_id": "default", "pin": "0000"})
    test_client.headers["Authorization"] = f"Bearer {login.json()['token']}"
    owned = test_client.post(
        "/api/strategy-configs",
        json={
            "name": "Owned",
            "strategy_type": "dynamic_wave",
            "symbol": "SOXL",
            "initial_capital": "1000",
            "fee_rate": "0",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    ).json()
    with test_client.app.state.session_factory() as session:
        session.add(Owner(id="other", name="Other", pin_hash=hash_pin("1234"), is_active=True))
        other = StrategyConfig(
            owner_id="other",
            name="Other strategy",
            strategy_type="dynamic_wave",
            symbol="SOXL",
            initial_capital=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            settings_json=DynamicWaveStrategy.default_settings(),
        )
        session.add(other)
        session.commit()
        other_id = other.id
    with test_client.app.state.session_factory() as session:
        config = session.get(StrategyConfig, owned["id"])
        portfolio = session.get(LivePortfolio, owned["id"])
        before = (
            dict(config.settings_json),
            portfolio.capital,
            portfolio.cash,
            session.scalar(select(func.count()).select_from(Position)),
            session.scalar(select(func.count()).select_from(Trade)),
        )
    assert (
        test_client.put(
            f"/api/integrated-orders/preferences/{other_id}", json={"included": True}
        ).status_code
        == 404
    )
    update = test_client.put(
        f"/api/integrated-orders/preferences/{owned['id']}", json={"included": True}
    )
    assert update.status_code == 200
    assert update.json()["included"] is True
    with test_client.app.state.session_factory() as session:
        config = session.get(StrategyConfig, owned["id"])
        portfolio = session.get(LivePortfolio, owned["id"])
        after = (
            dict(config.settings_json),
            portfolio.capital,
            portfolio.cash,
            session.scalar(select(func.count()).select_from(Position)),
            session.scalar(select(func.count()).select_from(Trade)),
        )
    assert after == before
    response = test_client.get("/api/integrated-orders")
    assert response.status_code == 200
    assert [row["strategy_config_id"] for row in response.json()["preferences"]] == [owned["id"]]
