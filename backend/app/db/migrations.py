from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Connection, Engine, text


Migration = tuple[int, str, Callable[[Connection], None]]


def _column_names(connection: Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})"))}


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
        "strategy_config_id",
        "mode",
        "buy_price",
        "sell_threshold_percent",
        "sell_limit_price",
        "max_holding_days",
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


def _link_loc_orders_to_positions(connection: Connection) -> None:
    _add_column_if_missing(
        connection,
        "loc_orders",
        "position_id",
        "position_id INTEGER REFERENCES positions(id) ON DELETE SET NULL",
    )


def _backfill_legacy_radar_loc_order_positions(connection: Connection) -> None:
    required_loc_columns = {
        "strategy_config_id",
        "order_date",
        "limit_price",
        "recommended_quantity",
        "mode",
        "status",
        "position_id",
    }
    required_position_columns = {
        "id",
        "strategy_config_id",
        "buy_date",
        "limit_price",
        "quantity",
        "mode",
        "status",
        "radar_profile",
    }
    if not required_loc_columns <= _column_names(connection, "loc_orders"):
        return
    if not required_position_columns <= _column_names(connection, "positions"):
        return
    connection.execute(
        text(
            """
            UPDATE loc_orders AS orders
            SET position_id = (
                SELECT MIN(positions.id)
                FROM positions
                WHERE positions.strategy_config_id = orders.strategy_config_id
                  AND positions.buy_date = orders.order_date
                  AND positions.limit_price = orders.limit_price
                  AND positions.quantity = orders.recommended_quantity
                  AND positions.mode = orders.mode
                  AND positions.status = 'pending'
                  AND positions.radar_profile IS NOT NULL
            )
            WHERE orders.position_id IS NULL
              AND orders.status = 'pending'
              AND EXISTS (
                  SELECT 1 FROM strategy_configs
                  WHERE strategy_configs.id = orders.strategy_config_id
                    AND strategy_configs.strategy_type = 'radar0458_pro'
              )
              AND 1 = (
                  SELECT COUNT(*)
                  FROM positions
                  WHERE positions.strategy_config_id = orders.strategy_config_id
                    AND positions.buy_date = orders.order_date
                    AND positions.limit_price = orders.limit_price
                    AND positions.quantity = orders.recommended_quantity
                    AND positions.mode = orders.mode
                    AND positions.status = 'pending'
                    AND positions.radar_profile IS NOT NULL
              )
            """
        )
    )


def _add_radar_position_snapshots(connection: Connection) -> None:
    _add_column_if_missing(connection, "positions", "radar_tier", "radar_tier INTEGER")
    _add_column_if_missing(connection, "positions", "radar_profile", "radar_profile VARCHAR(16)")
    _add_column_if_missing(connection, "positions", "radar_cycle_id", "radar_cycle_id VARCHAR(64)")
    _add_column_if_missing(
        connection,
        "positions",
        "radar_cycle_capital",
        "radar_cycle_capital NUMERIC(18, 6)",
    )


def _add_radar_backtest_trade_snapshots(connection: Connection) -> None:
    _add_column_if_missing(connection, "backtest_trades", "radar_tier", "radar_tier INTEGER")
    _add_column_if_missing(
        connection,
        "backtest_trades",
        "radar_profile",
        "radar_profile VARCHAR(16)",
    )
    _add_column_if_missing(
        connection,
        "backtest_trades",
        "radar_cycle_capital",
        "radar_cycle_capital NUMERIC(18, 6)",
    )


def _add_active_radar_tier_index(connection: Connection) -> None:
    required = {
        "strategy_config_id",
        "radar_cycle_id",
        "radar_tier",
        "status",
    }
    if not required <= _column_names(connection, "positions"):
        return
    connection.execute(
        text(
            "WITH ranked AS ("
            "SELECT id, ROW_NUMBER() OVER ("
            "PARTITION BY strategy_config_id, radar_cycle_id, radar_tier ORDER BY id"
            ") AS duplicate_rank FROM positions "
            "WHERE radar_cycle_id IS NOT NULL AND radar_tier IS NOT NULL "
            "AND status IN ('pending', 'open')"
            ") UPDATE positions "
            "SET radar_cycle_id = radar_cycle_id || '-recovered-' || id "
            "WHERE id IN (SELECT id FROM ranked WHERE duplicate_rank > 1)"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_positions_active_radar_tier "
            "ON positions (strategy_config_id, radar_cycle_id, radar_tier) "
            "WHERE radar_cycle_id IS NOT NULL AND radar_tier IS NOT NULL "
            "AND status IN ('pending', 'open')"
        )
    )

def _add_integrated_order_preferences(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS integrated_order_preferences (
                strategy_config_id INTEGER PRIMARY KEY,
                included BOOLEAN NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
            )
            """
        )
    )


MIGRATIONS: tuple[Migration, ...] = (
    (1, "legacy_schema", _upgrade_legacy_schema),
    (2, "loc_orders_trade_fk_set_null", _rebuild_loc_orders_trade_foreign_key),
    (3, "snapshot_position_exit_policies", _snapshot_position_exit_policies),
    (4, "radar_position_snapshots", _add_radar_position_snapshots),
    (5, "link_loc_orders_to_positions", _link_loc_orders_to_positions),
    (6, "backfill_legacy_radar_loc_positions", _backfill_legacy_radar_loc_order_positions),
    (7, "radar_backtest_trade_snapshots", _add_radar_backtest_trade_snapshots),
    (8, "integrated_order_preferences", _add_integrated_order_preferences),
    (9, "active_radar_tier_index", _add_active_radar_tier_index),
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
