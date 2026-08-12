from app.infrastructure.market_data.regular_open_factory import (
    build_regular_open_provider,
)


def test_factory_reuses_composite_across_collector_and_api_requests() -> None:
    assert build_regular_open_provider() is build_regular_open_provider()
