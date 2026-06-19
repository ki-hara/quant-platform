export type DecimalString = string;
export type ISODate = string;
export type ISODateTime = string;

export interface StrategyInfo {
  type: string;
  name: string;
}

export interface StrategySchema {
  strategy_type: string;
  schema: Record<string, unknown>;
}

export interface StrategyConfig {
  id: number;
  owner_id: string;
  name: string;
  strategy_type: string;
  symbol: string;
  initial_capital: DecimalString;
  fee_rate: DecimalString;
  slippage_rate: DecimalString;
  settings_json: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface StrategyConfigCreateRequest {
  name: string;
  strategy_type: string;
  symbol: string;
  initial_capital: DecimalString;
  fee_rate: DecimalString;
  slippage_rate: DecimalString;
  settings_json: Record<string, unknown>;
}

export interface PortfolioRow {
  strategy_config_id: number;
  capital: DecimalString;
  cash: DecimalString;
  realized_pnl: DecimalString;
  cumulative_fees: DecimalString;
}

export interface PositionRow {
  id: number;
  strategy_config_id: number;
  buy_date: ISODate;
  buy_price: DecimalString;
  buy_fee: DecimalString;
  quantity: DecimalString;
  mode: string;
  status: string;
}

export interface MarketPriceRow {
  symbol: string;
  date: ISODate;
  open: DecimalString;
  high: DecimalString;
  low: DecimalString;
  close: DecimalString;
  volume: DecimalString;
  adjusted: boolean;
}

export interface DashboardSignal {
  available: boolean;
  should_buy: boolean;
  buy_reason: string | null;
  sell_signals: Array<Record<string, unknown>> | null;
  reason: string | null;
}

export interface DashboardResponse {
  config: StrategyConfig;
  portfolio: PortfolioRow | null;
  open_positions: PositionRow[];
  latest_price: MarketPriceRow | null;
  total_asset: DecimalString | null;
  signals: DashboardSignal;
}

export interface TradeRow {
  id: number;
  strategy_config_id: number;
  date: ISODate;
  side: string;
  quantity: DecimalString;
  price: DecimalString;
  fee: DecimalString;
  realized_pnl: DecimalString;
  sell_reason: string | null;
  source: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface SignalExecutionRequest {
  side: "buy" | "sell";
  trade_date: ISODate;
  quantity: DecimalString;
  price: DecimalString;
  fee: DecimalString;
  source?: string;
  mode?: string;
  position_id?: number | null;
  sell_reason?: string | null;
}

export interface SignalExecutionResponse {
  trade: TradeRow;
  cash: DecimalString;
  realized_pnl: DecimalString;
}

export interface BacktestRun {
  id: number;
  owner_id: string;
  strategy_config_snapshot_json: Record<string, unknown>;
  start_date: ISODate;
  end_date: ISODate;
  status: string;
  error_message: string | null;
  initial_capital: DecimalString;
  final_capital: DecimalString;
  total_return: DecimalString;
  max_drawdown: DecimalString;
  win_rate: DecimalString;
  total_trades: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface BacktestCreateRequest {
  config_id: number;
  start_date: ISODate;
  end_date: ISODate;
}

export interface BacktestDailySnapshot {
  backtest_run_id: number;
  date: ISODate;
  capital: DecimalString;
  cash: DecimalString;
  position_value: DecimalString;
  total_asset: DecimalString;
  drawdown: DecimalString;
  cumulative_fees: DecimalString;
}

export interface BacktestTrade {
  id: number;
  backtest_run_id: number;
  date: ISODate;
  side: string;
  quantity: DecimalString;
  price: DecimalString;
  fee: DecimalString;
  realized_pnl: DecimalString;
  sell_reason: string | null;
  source: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}
