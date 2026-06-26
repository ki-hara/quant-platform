export type DecimalString = string;
export type ISODate = string;
export type ISODateTime = string;
export type StrategyMode = "safe" | "aggressive";
export type LocOrderStatus = "pending" | "filled" | "unfilled";
export type ModeConfirmationSource = "manual" | "recommendation_applied";
export type ChartRange = "1m" | "3m" | "6m" | "1y";

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
  archived_at: ISODateTime | null;
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

export type StrategyConfigUpdateRequest = Partial<StrategyConfigCreateRequest>;

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
  limit_price: DecimalString | null;
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
  limit_price: DecimalString | null;
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
  limit_price?: DecimalString | null;
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

export interface ManualTradeRequest {
  config_id: number;
  trade_date: ISODate;
  side: "buy" | "sell";
  quantity: DecimalString;
  limit_price?: DecimalString | null;
  price: DecimalString;
  fee: DecimalString;
  sell_reason?: string | null;
  source: "manual" | "correction";
  mode?: string;
  position_id?: number | null;
}

export interface ManualTradeResponse {
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
  mode_policy?: "weekly_rsi" | "fixed_safe" | "fixed_aggressive";
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
  mode: StrategyMode;
  mode_rule_code: string | null;
}

export interface BacktestTrade {
  id: number;
  backtest_run_id: number;
  date: ISODate;
  side: string;
  quantity: DecimalString;
  limit_price?: DecimalString | null;
  price: DecimalString;
  fee: DecimalString;
  realized_pnl: DecimalString;
  sell_reason: string | null;
  source: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface ModeRecommendation {
  confirmed_mode: StrategyMode;
  confirmed_source: ModeConfirmationSource;
  recommended_mode: StrategyMode | null;
  differs: boolean;
  effective_week: ISODate | null;
  data_as_of: ISODate | null;
  previous_rsi: DecimalString | null;
  current_rsi: DecimalString | null;
  rule_code: string | null;
}

export interface ConfirmedModeUpdateRequest {
  action: "set" | "apply_recommendation";
  mode?: StrategyMode | null;
}

export interface LocPlan {
  limit_price: DecimalString;
  allocation: DecimalString;
  quantity: number;
  estimated_fee: DecimalString;
  required_cash: DecimalString;
  available: DecimalString;
  blocking_reason: string | null;
  orders: LocOrder[];
}

export interface LocOrder {
  step: number;
  limit_price: DecimalString;
  quantity: number;
  cumulative_quantity: number;
  cumulative_amount: DecimalString;
  compressed: boolean;
}

export interface DailyPlan {
  plan_date: ISODate;
  market_data_as_of: ISODate | null;
  symbol: string;
  confirmed_mode: StrategyMode;
  confirmed_source: ModeConfirmationSource;
  recommended_mode: StrategyMode | null;
  differs: boolean;
  effective_week: ISODate | null;
  data_as_of: ISODate | null;
  previous_rsi: DecimalString | null;
  current_rsi: DecimalString | null;
  rule_code: string | null;
  previous_close: DecimalString | null;
  loc_basis_date: ISODate | null;
  loc_basis_close: DecimalString | null;
  loc_formula: string | null;
  mode_buy_threshold_percent: DecimalString | null;
  capital: DecimalString | null;
  cash: DecimalString | null;
  mode_split_count: number | null;
  open_position_count: number;
  buy_available: boolean;
  LOC: LocPlan;
}

export interface PortfolioAdjustment {
  id: number;
  strategy_config_id: number;
  date: ISODate;
  cash_delta: DecimalString;
  capital_delta: DecimalString;
  memo: string | null;
  created_at: ISODateTime;
}

export interface PortfolioAdjustmentCreateRequest {
  date: ISODate;
  cash_delta: DecimalString;
  capital_delta: DecimalString;
  memo?: string | null;
}

export interface LocOrderRow {
  id: number;
  strategy_config_id: number;
  order_date: ISODate;
  symbol: string;
  limit_price: DecimalString;
  recommended_quantity: DecimalString;
  mode: StrategyMode;
  status: LocOrderStatus;
  trade_id: number | null;
  memo: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface LocOrderFillRequest {
  quantity: DecimalString;
  price: DecimalString;
  fee?: DecimalString;
  memo?: string | null;
}

export interface ChartCandle {
  date: ISODate;
  open: DecimalString;
  high: DecimalString;
  low: DecimalString;
  close: DecimalString;
  volume: DecimalString | number;
}

export interface ChartLine {
  value: DecimalString;
  as_of: ISODate | null;
}

export interface TradeMarker {
  date: ISODate;
  kind: "buy" | "sell";
  price: DecimalString;
  quantity: DecimalString;
  source: string;
  sell_reason: string | null;
}

export interface RsiPoint {
  date: ISODate;
  value: DecimalString;
}

export interface RsiSeries {
  guides: DecimalString[];
  points: RsiPoint[];
}

export interface ModeMarker {
  date: ISODate;
  mode: StrategyMode;
  rule_code: string | null;
}

export interface TradingChart {
  candles: ChartCandle[];
  LOC: ChartLine;
  trade_markers: TradeMarker[];
  rsi: RsiSeries;
  mode_markers: ModeMarker[];
}

export interface MarketRefreshResponse {
  confirmed_mode: StrategyMode;
  confirmed_source: ModeConfirmationSource;
  recommended_mode: StrategyMode | null;
  differs: boolean;
  investment_data_as_of: ISODate | null;
  rsi_data_as_of: ISODate | null;
}
