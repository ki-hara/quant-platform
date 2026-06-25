from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import get_session
from app.dto.market_data import OhlcvDto
from app.infrastructure.market_data.base import MarketDataProvider
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.main import create_app
from app.services.market_refresh_service import get_market_data_provider
from app.services.strategy_config_service import StrategyConfigCreateRequest, StrategyConfigService
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
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

    app = create_app()
    app.state.test_engine = engine
    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


def create_config(api_client: TestClient) -> int:
    response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Trading Plan Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def seed_weekly_prices(
    api_client: TestClient,
    closes: list[str],
    *,
    symbol: str = "QQQ",
    first_week_ending: date = date(2026, 2, 27),
) -> None:
    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [
                OhlcvDto(
                    symbol=symbol,
                    date=first_week_ending + timedelta(days=7 * index),
                    open=Decimal(close),
                    high=Decimal(close),
                    low=Decimal(close),
                    close=Decimal(close),
                    volume=1000,
                )
                for index, close in enumerate(closes)
            ],
        )


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date]] = []

    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
        self.calls.append((symbol, start_date, end_date))
        return [
            OhlcvDto(
                symbol=symbol,
                date=start_date + timedelta(days=index),
                open=Decimal(str(100 + index)),
                high=Decimal(str(101 + index)),
                low=Decimal(str(99 + index)),
                close=Decimal(str(100 + index)),
                volume=1000 + index,
            )
            for index in range((end_date - start_date).days + 1)
        ]
        session.commit()


def test_get_mode_recommendation_returns_differs_and_preserves_confirmed_mode(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)
    seed_weekly_prices(
        api_client,
        [
            "99",
            "100",
            "101",
            "102",
            "103",
            "104",
            "105",
            "106",
            "107",
            "108",
            "109",
            "110",
            "111",
            "112",
            "113",
            "114",
            "113",
            "112",
        ],
    )

    api_client.put(
        f"/api/strategy-configs/{config_id}/confirmed-mode",
        json={"action": "set", "mode": "aggressive"},
    )

    response = api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendation?as_of=2026-06-19")

    assert response.status_code == 200
    body = response.json()
    assert body["confirmed_mode"] == "aggressive"
    assert body["confirmed_source"] == "manual"
    assert body["recommended_mode"] == "safe"
    assert body["differs"] is True
    assert body["effective_week"] == "2026-06-22"
    assert body["data_as_of"] == "2026-06-19"
    assert body["rule_code"] == "S1"


def test_put_confirmed_mode_set_updates_confirmed_mode_and_source(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)

    response = api_client.put(
        f"/api/strategy-configs/{config_id}/confirmed-mode",
        json={"action": "set", "mode": "aggressive"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmed_mode"] == "aggressive"
    assert body["confirmed_source"] == "manual"


def test_put_confirmed_mode_apply_recommendation_copies_current_recommendation(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)
    seed_weekly_prices(
        api_client,
        [
            "99",
            "100",
            "101",
            "102",
            "103",
            "104",
            "105",
            "106",
            "107",
            "108",
            "109",
            "110",
            "111",
            "112",
            "113",
            "114",
            "113",
            "112",
        ],
    )

    api_client.put(
        f"/api/strategy-configs/{config_id}/confirmed-mode",
        json={"action": "set", "mode": "aggressive"},
    )
    api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendation")

    response = api_client.put(
        f"/api/strategy-configs/{config_id}/confirmed-mode",
        json={"action": "apply_recommendation"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmed_mode"] == "safe"
    assert body["confirmed_source"] == "recommendation_applied"


def test_put_confirmed_mode_apply_without_recommendation_returns_422(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)

    response = api_client.put(
        f"/api/strategy-configs/{config_id}/confirmed-mode",
        json={"action": "apply_recommendation"},
    )

    assert response.status_code == 422


def test_get_mode_recommendation_requires_sixteen_completed_weekly_closes(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)
    seed_weekly_prices(
        api_client,
        [
            "100",
            "101",
            "102",
            "103",
            "104",
            "105",
            "106",
            "107",
            "108",
            "109",
            "110",
            "111",
            "112",
            "113",
            "114",
        ],
    )

    response = api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendation")

    assert response.status_code == 422


def test_get_mode_recommendations_returns_newest_history_first(api_client: TestClient) -> None:
    config_id = create_config(api_client)
    seed_weekly_prices(
        api_client,
        [
            "100",
            "101",
            "102",
            "103",
            "104",
            "105",
            "106",
            "107",
            "108",
            "109",
            "110",
            "111",
            "112",
            "113",
            "114",
            "113",
            "112",
            "111",
        ],
    )

    api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendation?as_of=2026-06-19")
    api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendation?as_of=2026-06-26")

    response = api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendations")

    assert response.status_code == 200
    body = response.json()
    assert [item["effective_week"] for item in body] == ["2026-06-29", "2026-06-22"]


def test_mode_recommendation_missing_config_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/strategy-configs/999/mode-recommendation")

    assert response.status_code == 404


def test_get_daily_plan_returns_loc_and_mode_state(api_client: TestClient) -> None:
    config_id = create_config(api_client)
    seed_weekly_prices(
        api_client,
        [
            "99",
            "100",
            "101",
            "102",
            "103",
            "104",
            "105",
            "106",
            "107",
            "108",
            "109",
            "110",
            "111",
            "112",
            "113",
            "114",
            "113",
            "112",
        ],
    )
    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [
                OhlcvDto(
                    symbol="TEST",
                    date=date(2026, 6, 18),
                    open=Decimal("99"),
                    high=Decimal("99"),
                    low=Decimal("99"),
                    close=Decimal("99"),
                    volume=1000,
                ),
                OhlcvDto(
                    symbol="TEST",
                    date=date(2026, 6, 19),
                    open=Decimal("100"),
                    high=Decimal("100"),
                    low=Decimal("100"),
                    close=Decimal("100"),
                    volume=1000,
                ),
            ],
        )
        session.commit()

    api_client.get(f"/api/strategy-configs/{config_id}/mode-recommendation?as_of=2026-06-19")
    response = api_client.get(f"/api/strategy-configs/{config_id}/daily-plan?today=2026-06-19")

    assert response.status_code == 200
    body = response.json()
    assert body["market_data_as_of"] == "2026-06-19"
    assert body["confirmed_mode"] == "safe"
    assert body["LOC"]["limit_price"] == "103.000000"
    assert body["LOC"]["quantity"] == 1


@pytest.mark.parametrize("range_key", ["1m", "3m", "6m", "1y"])
def test_get_chart_returns_markers_and_guide_lines(api_client: TestClient, range_key: str) -> None:
    config_id = create_config(api_client)
    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [
                OhlcvDto(
                    symbol="TEST",
                    date=date(2025, 6, 20) + timedelta(days=index),
                    open=Decimal(str(100 + index)),
                    high=Decimal(str(101 + index)),
                    low=Decimal(str(99 + index)),
                    close=Decimal(str(100 + index)),
                    volume=1000 + index,
                )
                for index in range(500)
            ][::-1],
        )
        session.commit()
    response = api_client.get(f"/api/strategy-configs/{config_id}/chart?range={range_key}")

    assert response.status_code == 200
    body = response.json()
    assert body["LOC"]["value"]
    assert body["rsi"]["guides"] == ["35.000000", "40.000000", "50.000000", "60.000000", "65.000000"]
    assert body["candles"][0]["date"] <= body["candles"][-1]["date"]


def test_post_refresh_fetches_both_symbols_and_preserves_confirmed_mode(api_client: TestClient) -> None:
    config_id = create_config(api_client)
    provider = FakeProvider()
    api_client.app.dependency_overrides[get_market_data_provider] = lambda: provider

    try:
        api_client.put(
            f"/api/strategy-configs/{config_id}/confirmed-mode",
            json={"action": "set", "mode": "aggressive"},
        )
        response = api_client.post(f"/api/strategy-configs/{config_id}/market-data/refresh")
    finally:
        api_client.app.dependency_overrides.pop(get_market_data_provider, None)

    assert response.status_code == 200
    body = response.json()
    assert len(provider.calls) == 2
    assert {call[0] for call in provider.calls} == {"TEST", "QQQ"}
    assert body["confirmed_mode"] == "aggressive"
    assert body["investment_data_as_of"]
    assert body["rsi_data_as_of"]
