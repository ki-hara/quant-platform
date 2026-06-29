from enum import StrEnum


class StrategyMode(StrEnum):
    SAFE = "safe"
    AGGRESSIVE = "aggressive"


class ModeConfirmationSource(StrEnum):
    MANUAL = "manual"
    RECOMMENDATION_APPLIED = "recommendation_applied"


class BacktestModePolicy(StrEnum):
    WEEKLY_RSI = "weekly_rsi"
    FIXED_SAFE = "fixed_safe"
    FIXED_AGGRESSIVE = "fixed_aggressive"


class BacktestPositionSizingPolicy(StrEnum):
    FIXED_QUANTITY = "fixed_quantity"
    FULL_ALLOCATION = "full_allocation"


class PositionStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TradeSource(StrEnum):
    SIGNAL_EXECUTION = "signal_execution"
    MANUAL = "manual"
    CORRECTION = "correction"


class LocOrderStatus(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    UNFILLED = "unfilled"


class BacktestStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
