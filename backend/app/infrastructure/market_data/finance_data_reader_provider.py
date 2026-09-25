import logging
import json
import subprocess
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.errors import MarketDataError
from app.dto.market_data import OhlcvDto


logger = logging.getLogger(__name__)


class FinanceDataReaderProvider:
    def get_ohlcv(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
        # Kill and reap the worker on timeout; an abandoned thread cannot bound FDR I/O.
        try:
            result = subprocess.run(
                [sys.executable, "-m", "app.infrastructure.market_data.finance_data_reader_provider",
                 symbol, start_date.isoformat(), end_date.isoformat()],
                cwd=Path(__file__).resolve().parents[3],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            if result.returncode != 0:
                raise MarketDataError("market_data_provider_failed", "주 시세 공급자 조회에 실패했습니다.")
            return [OhlcvDto.model_validate(row) for row in json.loads(result.stdout)]
        except subprocess.TimeoutExpired as exc:
            raise MarketDataError("market_data_timeout", "주 시세 공급자 응답 시간 초과(15초)") from exc
        except (ValueError, OSError) as exc:
            raise MarketDataError("market_data_provider_failed", "주 시세 공급자 응답을 처리하지 못했습니다.") from exc

    def _read(self, symbol: str, start_date: date, end_date: date) -> list[OhlcvDto]:
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
            try:
                values = {
                    name: Decimal(str(row[column]))
                    for name, column in required_columns.items()
                }
                if any(not value.is_finite() for value in values.values()):
                    raise ValueError("non-finite OHLCV value")
                rows.append(
                    OhlcvDto(
                        symbol=symbol,
                        date=quote_date,
                        open=values["open"],
                        high=values["high"],
                        low=values["low"],
                        close=values["close"],
                        volume=int(values["volume"]),
                        adjusted=True,
                    )
                )
            except (InvalidOperation, TypeError, ValueError):
                logger.warning(
                    "Skipping incomplete market data row: symbol=%s date=%s",
                    symbol,
                    quote_date,
                )
        return sorted(rows, key=lambda price: price.date)

    def _column_for(self, columns: dict[str, Any], *names: str) -> Any | None:
        for name in names:
            if name in columns:
                return columns[name]
        return None


if __name__ == "__main__":
    from contextlib import redirect_stdout
    with redirect_stdout(sys.stderr):
        rows = FinanceDataReaderProvider()._read(sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]))
    print(json.dumps([row.model_dump(mode="json") for row in rows]))
