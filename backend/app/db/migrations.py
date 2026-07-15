from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Connection, Engine, text


Migration = tuple[int, str, Callable[[Connection], None]]


def _column_names(connection: Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
    }


def _add_column_if_missing(
    connection: Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    if column_name not in _column_names(connection, table_name):
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {definition}"))


def _upgrade_legacy_schema(connection: Connection) -> None:
    _add_column_if_missing(connection, "strategy_configs", "archived_at", "archived_at DATETIME")
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS strategy_config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_config_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                memo VARCHAR(500),
                strategy_type VARCHAR(100) NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                fee_rate NUMERIC(18, 6) NOT NULL,
                slippage_rate NUMERIC(18, 6) NOT NULL,
                settings_json JSON NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
            )
            """
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_strategy_config_snapshots_strategy_config_id "
            "ON strategy_config_snapshots (strategy_config_id)"
        )
    )

    _add_column_if_missing(
        connection,
        "backtest_daily_snapshots",
        "mode",
        "mode VARCHAR(10) NOT NULL DEFAULT 'safe'",
    )
    _add_column_if_missing(
        connection,
        "backtest_daily_snapshots",
        "mode_rule_code",
        "mode_rule_code VARCHAR(32)",
    )
    _add_column_if_missing(connection, "positions", "limit_price", "limit_price NUMERIC(18, 6)")
    _add_column_if_missing(connection, "trades", "limit_price", "limit_price NUMERIC(18, 6)")
    _add_column_if_missing(connection, "trades", "position_id", "position_id INTEGER")
    _add_column_if_missing(connection, "trades", "entry_date", "entry_date DATE")
    _add_column_if_missing(connection, "trades", "entry_price", "entry_price NUMERIC(18, 6)")
    _add_column_if_missing(connection, "backtest_trades", "holding_days", "holding_days INTEGER")
    _add_column_if_missing(
        connection,
        "backtest_trades",
        "open_position_count",
        "open_position_count INTEGER",
    )
    _add_column_if_missing(
        connection,
        "backtest_trades",
        "cash_after",
        "cash_after NUMERIC(18, 6)",
    )
    _add_column_if_missing(
        connection,
        "backtest_trades",
        "capital_after",
        "capital_after NUMERIC(18, 6)",
    )

    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS portfolio_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_config_id INTEGER NOT NULL,
                date DATE NOT NULL,
                cash_delta NUMERIC(18, 6) NOT NULL,
                capital_delta NUMERIC(18, 6) NOT NULL,
                memo VARCHAR(500),
                created_at DATETIME NOT NULL,
                FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
            )
            """
        )
    )
    _add_column_if_missing(
        connection,
        "portfolio_adjustments",
        "source",
        "source VARCHAR(64) NOT NULL DEFAULT 'manual'",
    )
    _add_column_if_missing(
        connection,
        "portfolio_adjustments",
        "period_start_date",
        "period_start_date DATE",
    )
    _add_column_if_missing(
        connection,
        "portfolio_adjustments",
        "period_end_date",
        "period_end_date DATE",
    )
    _add_column_if_missing(connection, "owners", "pin_hash", "pin_hash VARCHAR(255)")
    _add_column_if_missing(
        connection,
        "owners",
        "is_active",
        "is_active BOOLEAN NOT NULL DEFAULT 1",
    )
    _add_column_if_missing(
        connection,
        "owners",
        "is_admin",
        "is_admin BOOLEAN NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(connection, "owners", "created_at", "created_at DATETIME")

    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS loc_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_config_id INTEGER NOT NULL,
                order_date DATE NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                limit_price NUMERIC(18, 6) NOT NULL,
                recommended_quantity NUMERIC(18, 6) NOT NULL,
                mode VARCHAR(10) NOT NULL,
                status VARCHAR(10) NOT NULL,
                trade_id INTEGER,
                memo VARCHAR(500),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id),
                FOREIGN KEY(trade_id) REFERENCES trades (id) ON DELETE SET NULL
            )
            """
        )
    )
    connection.execute(
        text(
            "UPDATE loc_orders SET trade_id = NULL "
            "WHERE trade_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM trades WHERE trades.id = loc_orders.trade_id)"
        )
    )

def _has_loc_order_trade_set_null_foreign_key(connection: Connection) -> bool:
    foreign_keys = connection.execute(text("PRAGMA foreign_key_list(loc_orders)"))
    return any(row[2] == "trades" and row[6] == "SET NULL" for row in foreign_keys)


def _rebuild_loc_orders_trade_foreign_key(connection: Connection) -> None:
    if _has_loc_order_trade_set_null_foreign_key(connection):
        return

    connection.execute(
        text(
            """
            CREATE TABLE loc_orders_replacement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_config_id INTEGER NOT NULL,
                order_date DATE NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                limit_price NUMERIC(18, 6) NOT NULL,
                recommended_quantity NUMERIC(18, 6) NOT NULL,
                mode VARCHAR(10) NOT NULL,
                status VARCHAR(10) NOT NULL,
                trade_id INTEGER,
                memo VARCHAR(500),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id),
                FOREIGN KEY(trade_id) REFERENCES trades (id) ON DELETE SET NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO loc_orders_replacement (
                id, strategy_config_id, order_date, symbol, limit_price,
                recommended_quantity, mode, status, trade_id, memo, created_at, updated_at
            )
            SELECT
                id, strategy_config_id, order_date, symbol, limit_price,
                recommended_quantity, mode, status, trade_id, memo, created_at, updated_at
            FROM loc_orders
            """
        )
    )
    connection.execute(text("DROP TABLE loc_orders"))
    connection.execute(text("ALTER TABLE loc_orders_replacement RENAME TO loc_orders"))
    connection.execute(
        text("CREATE INDEX ix_loc_orders_strategy_config_id ON loc_orders (strategy_config_id)")
    )
    connection.execute(text("CREATE INDEX ix_loc_orders_order_date ON loc_orders (order_date)"))


def _snapshot_position_exit_policies(connection: Connection) -> None:
    _add_column_if_missing(
        connection,
        "positions",
        "sell_threshold_percent",
        "sell_threshold_percent NUMERIC(18, 6)",
    )
    _add_column_if_missing(
        connection,
        "positions",
        "sell_limit_price",
        "sell_limit_price NUMERIC(18, 6)",
    )
    _add_column_if_missing(
        connection,
        "positions",
        "max_holding_days",
        "max_holding_days INTEGER",
    )

    required_position_columns = {
        "strategy_config_id", "mode", "buy_price", "sell_threshold_percent",
        "sell_limit_price", "max_holding_days",
    }
    required_config_columns = {"id", "settings_json"}
    if not required_position_columns <= _column_names(connection, "positions"):
        return
    if not required_config_columns <= _column_names(connection, "strategy_configs"):
        return

    connection.execute(
        text(
            """
            UPDATE positions
            SET
                sell_threshold_percent = CAST(json_extract(
                    (SELECT settings_json FROM strategy_configs WHERE id = positions.strategy_config_id),
                    '$.' || positions.mode || '.sell_threshold_percent'
                ) AS NUMERIC),
                sell_limit_price = positions.buy_price * (1 + CAST(json_extract(
                    (SELECT settings_json FROM strategy_configs WHERE id = positions.strategy_config_id),
                    '$.' || positions.mode || '.sell_threshold_percent'
                ) AS NUMERIC) / 100),
                max_holding_days = CAST(json_extract(
                    (SELECT settings_json FROM strategy_configs WHERE id = positions.strategy_config_id),
                    '$.' || positions.mode || '.max_holding_days'
                ) AS INTEGER)
            WHERE sell_threshold_percent IS NULL
               OR sell_limit_price IS NULL
               OR max_holding_days IS NULL
            """
        )
    )

MIGRATIONS: tuple[Migration, ...] = (
    (1, "legacy_schema", _upgrade_legacy_schema),
    (2, "loc_orders_trade_fk_set_null", _rebuild_loc_orders_trade_foreign_key),
    (3, "snapshot_position_exit_policies", _snapshot_position_exit_policies),
)
LATEST_SCHEMA_VERSION = MIGRATIONS[-1][0]


def run_sqlite_migrations(database_engine: Engine) -> None:
    if database_engine.dialect.name != "sqlite":
        return

    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    applied_at DATETIME NOT NULL
                )
                """
            )
        )

    for version, name, migrate in MIGRATIONS:
        with database_engine.begin() as connection:
            applied = connection.scalar(
                text("SELECT 1 FROM schema_migrations WHERE version = :version"),
                {"version": version},
            )
            if applied:
                continue
            migrate(connection)
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (version, name, applied_at) "
                    "VALUES (:version, :name, :applied_at)"
                ),
                {
                    "version": version,
                    "name": name,
                    "applied_at": datetime.now(UTC).isoformat(),
                },
            )
