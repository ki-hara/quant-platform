from functools import lru_cache

from app.core.config import settings
from app.infrastructure.market_data.cnbc_regular_open_provider import (
    CnbcRegularOpenProvider,
)
from app.infrastructure.market_data.finnhub_regular_open_provider import (
    FinnhubRegularOpenProvider,
)
from app.infrastructure.market_data.resilient_regular_open_provider import (
    ResilientRegularOpenProvider,
)


@lru_cache(maxsize=1)
def build_regular_open_provider() -> ResilientRegularOpenProvider:
    return ResilientRegularOpenProvider(
        CnbcRegularOpenProvider(),
        FinnhubRegularOpenProvider(settings.finnhub_api_key),
    )
