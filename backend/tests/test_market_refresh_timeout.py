import subprocess
from datetime import date
from unittest.mock import patch

import pytest

from app.core.errors import MarketDataError
from app.infrastructure.market_data.finance_data_reader_provider import FinanceDataReaderProvider


def test_fdr_worker_has_hard_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 15)) as run:
        with pytest.raises(MarketDataError, match="15"):
            FinanceDataReaderProvider().get_ohlcv("SOXL", date(2026, 9, 22), date(2026, 9, 23))
        assert run.call_args.kwargs["timeout"] == 15


def test_fdr_worker_error_is_provider_error():
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "error")):
        with pytest.raises(MarketDataError):
            FinanceDataReaderProvider().get_ohlcv("SOXL", date(2026, 9, 22), date(2026, 9, 23))
