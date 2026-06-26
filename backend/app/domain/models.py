from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import (
    BacktestStatus,
    ModeConfirmationSource,
    PositionStatus,
    StrategyMode,
    TradeSide,
    TradeSource,
    LocOrderStatus,
)


def enum_column(enum_type: type) -> Enum:
    return Enum(
        enum_type,
        native_enum=False,
        values_callable=lambda values: [item.value for item in values],
    )


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    strategy_configs: Mapped[list["StrategyConfig"]] = relationship(back_populates="owner")
    backtest_runs: Mapped[list["BacktestRun"]] = relationship(back_populates="owner")


class StrategyConfig(Base):
    __tablename__ = "strategy_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    slippage_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)

    owner: Mapped[Owner] = relationship(back_populates="strategy_configs")
    live_portfolio: Mapped["LivePortfolio"] = relationship(back_populates="strategy_config")
    positions: Mapped[list["Position"]] = relationship(back_populates="strategy_config")
    trades: Mapped[list["Trade"]] = relationship(back_populates="strategy_config")
    portfolio_adjustments: Mapped[list["PortfolioAdjustment"]] = relationship(back_populates="strategy_config")
    loc_orders: Mapped[list["LocOrder"]] = relationship(back_populates="strategy_config")
    mode_state: Mapped["StrategyModeState | None"] = relationship(
        back_populates="strategy_config",
        uselist=False,
    )
    mode_recommendations: Mapped[list["ModeRecommendation"]] = relationship(
        back_populates="strategy_config",
    )


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (
        UniqueConstraint("provider", "symbol", "date", "adjusted", name="uq_market_prices_quote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted: Mapped[bool] = mapped_column(default=False, nullable=False)


class StrategyModeState(Base):
    __tablename__ = "strategy_mode_states"

    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        primary_key=True,
    )
    confirmed_mode: Mapped[StrategyMode] = mapped_column(enum_column(StrategyMode), nullable=False)
    confirmed_source: Mapped[ModeConfirmationSource] = mapped_column(
        enum_column(ModeConfirmationSource),
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    recommended_mode: Mapped[StrategyMode | None] = mapped_column(
        enum_column(StrategyMode),
    )
    recommendation_effective_week: Mapped[date | None] = mapped_column(Date)
    recommendation_data_as_of: Mapped[date | None] = mapped_column(Date)
    recommendation_previous_rsi: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    recommendation_current_rsi: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    recommendation_rule_code: Mapped[str | None] = mapped_column(String(16))
    recommendation_calculated_at: Mapped[datetime | None] = mapped_column(DateTime)

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="mode_state")


class ModeRecommendation(Base):
    __tablename__ = "mode_recommendations"
    __table_args__ = (
        UniqueConstraint("strategy_config_id", "effective_week", name="uq_mode_recommendations_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        nullable=False,
        index=True,
    )
    effective_week: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    previous_rsi: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    current_rsi: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    recommended_mode: Mapped[StrategyMode] = mapped_column(enum_column(StrategyMode), nullable=False)
    rule_code: Mapped[str | None] = mapped_column(String(16))
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="mode_recommendations")


class LivePortfolio(Base):
    __tablename__ = "live_portfolios"

    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        primary_key=True,
    )
    capital: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cumulative_fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="live_portfolio")


class PortfolioAdjustment(Base):
    __tablename__ = "portfolio_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    capital_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="portfolio_adjustments")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        nullable=False,
        index=True,
    )
    buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    buy_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    buy_fee: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    mode: Mapped[StrategyMode] = mapped_column(enum_column(StrategyMode), nullable=False)
    status: Mapped[PositionStatus] = mapped_column(enum_column(PositionStatus), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="positions")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[TradeSide] = mapped_column(enum_column(TradeSide), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    sell_reason: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[TradeSource] = mapped_column(enum_column(TradeSource), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="trades")


class LocOrder(Base):
    __tablename__ = "loc_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_config_id: Mapped[int] = mapped_column(ForeignKey("strategy_configs.id"), nullable=False, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    limit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    recommended_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    mode: Mapped[StrategyMode] = mapped_column(enum_column(StrategyMode), nullable=False)
    status: Mapped[LocOrderStatus] = mapped_column(enum_column(LocOrderStatus), nullable=False)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"))
    memo: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="loc_orders")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    strategy_config_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[BacktestStatus] = mapped_column(enum_column(BacktestStatus), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000))
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    final_capital: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_return: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_trades: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    owner: Mapped[Owner] = relationship(back_populates="backtest_runs")
    daily_snapshots: Mapped[list["BacktestDailySnapshot"]] = relationship(
        back_populates="backtest_run",
    )
    trades: Mapped[list["BacktestTrade"]] = relationship(back_populates="backtest_run")


class BacktestDailySnapshot(Base):
    __tablename__ = "backtest_daily_snapshots"

    backtest_run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    capital: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    position_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_asset: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cumulative_fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    mode: Mapped[StrategyMode] = mapped_column(
        enum_column(StrategyMode),
        default=StrategyMode.SAFE,
        nullable=False,
    )
    mode_rule_code: Mapped[str | None] = mapped_column(String(32))

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="daily_snapshots")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[TradeSide] = mapped_column(enum_column(TradeSide), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    sell_reason: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[TradeSource] = mapped_column(enum_column(TradeSource), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="trades")
