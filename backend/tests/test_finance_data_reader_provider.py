from datetime import date
from decimal import Decimal

import pandas as pd

from app.infrastructure.market_data.finance_data_reader_provider import (
    FinanceDataReaderProvider,
)


def test_normalize_frame_skips_incomplete_rows() -> None:
    frame = pd.DataFrame(
        {
            "Open": ["123.40", float("nan")],
            "High": ["124.88", float("nan")],
            "Low": ["117.69", float("nan")],
            "Close": ["123.05", float("nan")],
            "Volume": [55_965_600, float("nan")],
        },
        index=pd.to_datetime(["2026-08-27", "2026-08-28"]),
    )

    prices = FinanceDataReaderProvider()._normalize_frame("SOXL", frame)

    assert [price.date for price in prices] == [date(2026, 8, 27)]
    assert prices[0].close == Decimal("123.05")
