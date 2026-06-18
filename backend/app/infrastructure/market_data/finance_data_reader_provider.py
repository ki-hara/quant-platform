from datetime import date
from decimal import Decimal
from typing import Any

from app.core.errors import MarketDataError
from app.dto.market_data import OhlcvDto


class FinanceDataReaderProvider:
    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
        try:
            import FinanceDataReader as fdr

            frame = fdr.DataReader(symbol, start_date, end_date)
            return self._normalize_frame(symbol, frame)
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError("market_data_provider_failed", str(exc)) from exc

    def _normalize_frame(self, symbol: str, frame: Any) -> list[OhlcvDto]:
        columns = {str(column).lower(): column for column in frame.columns}
        required_columns = {
            "open": self._column_for(columns, "open"),
            "high": self._column_for(columns, "high"),
            "low": self._column_for(columns, "low"),
            "close": self._column_for(columns, "close"),
            "volume": self._column_for(columns, "volume", "vol"),
        }

        if any(column is None for column in required_columns.values()):
            missing = [
                name for name, column in required_columns.items() if column is None
            ]
            raise MarketDataError(
                "market_data_provider_failed",
                f"missing required columns: {', '.join(missing)}",
            )

        rows: list[OhlcvDto] = []
        for index, row in frame.iterrows():
            quote_date = index.date() if hasattr(index, "date") else index
            rows.append(
                OhlcvDto(
                    symbol=symbol,
                    date=quote_date,
                    open=Decimal(str(row[required_columns["open"]])),
                    high=Decimal(str(row[required_columns["high"]])),
                    low=Decimal(str(row[required_columns["low"]])),
                    close=Decimal(str(row[required_columns["close"]])),
                    volume=int(row[required_columns["volume"]]),
                    adjusted=True,
                )
            )
        return sorted(rows, key=lambda price: price.date)

    def _column_for(self, columns: dict[str, Any], *names: str) -> Any | None:
        for name in names:
            if name in columns:
                return columns[name]
        return None
