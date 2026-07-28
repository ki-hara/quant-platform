import type { BacktestCreateRequest, BuyOrderPositionCreateRequest, RadarProfile, StrategyMode } from "../types/api";

type RadarPlanSnapshots = { strategy_type?: string | null; radar_tier?: number | null; radar_profile?: RadarProfile | null; radar_cycle_id?: string | null; radar_cycle_capital?: string | null; radar_sell_threshold_percent?: string | null; radar_sell_limit_price?: string | null; radar_max_holding_days?: number | null };

export function buildBuyOrderPositionRequest(input: { orderDate: string; quantity: string; limitPrice: string; mode: StrategyMode; plan: RadarPlanSnapshots }): BuyOrderPositionCreateRequest {
  const base = { order_date: input.orderDate, quantity: input.quantity, limit_price: input.limitPrice, mode: input.mode };
  if (input.plan.strategy_type !== "radar0458_pro") return base;
  return { ...base, radar_tier: input.plan.radar_tier, radar_profile: input.plan.radar_profile, radar_cycle_id: input.plan.radar_cycle_id, radar_cycle_capital: input.plan.radar_cycle_capital, sell_threshold_percent: input.plan.radar_sell_threshold_percent, sell_limit_price: input.plan.radar_sell_limit_price, max_holding_days: input.plan.radar_max_holding_days };
}

export function shouldLoadModeRecommendation(strategyType: string | null | undefined): boolean { return strategyType === "dynamic_wave"; }

export function buildBacktestCreateRequest(input: { configId: number; startDate: string; endDate: string; strategyType: string; radarProfile: RadarProfile; modePolicy: "weekly_rsi" | "fixed_safe" | "fixed_aggressive"; positionSizingPolicy: "fixed_quantity" | "full_allocation" }): BacktestCreateRequest {
  const base = { config_id: input.configId, start_date: input.startDate, end_date: input.endDate };
  return input.strategyType === "radar0458_pro" ? { ...base, pro_profile: input.radarProfile } : { ...base, mode_policy: input.modePolicy, position_sizing_policy: input.positionSizingPolicy };
}
