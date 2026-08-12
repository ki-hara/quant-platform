from datetime import date

from app.infrastructure.market_data.cnbc_regular_open_provider import (
    parse_cnbc_regular_open,
)


def test_rejects_quote_without_cnbc_us_quote_provenance() -> None:
    payload = {
        "FormattedQuoteResult": {
            "FormattedQuote": [
                {
                    "symbol": "SOXL",
                    "open": "147.30",
                    "high": "147.70",
                    "low": "144.15",
                    "last_time": "2026-08-12T09:37:47.918-0400",
                    "curmktstatus": "REG_MKT",
                    "source": "Unverified consolidated cache",
                }
            ]
        }
    }

    result = parse_cnbc_regular_open(payload, "SOXL", date(2026, 8, 12))

    assert result.failure_reason == "cnbc_quote_source_untrusted"
