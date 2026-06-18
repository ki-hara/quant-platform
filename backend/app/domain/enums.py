from enum import StrEnum


class StrategyMode(StrEnum):
    SAFE = "safe"
    AGGRESSIVE = "aggressive"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TradeSource(StrEnum):
    SIGNAL_EXECUTION = "signal_execution"
    MANUAL = "manual"
    CORRECTION = "correction"


class BacktestStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
