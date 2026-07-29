import { describe, expect, it } from "vitest";
import { buildBacktestCreateRequest, buildBuyOrderPositionRequest, shouldLoadModeRecommendation } from "./strategyOperations";

describe("strategy operations boundaries", () => {
  it("sends only Radar concurrency snapshots from the daily plan", () => {
    expect(buildBuyOrderPositionRequest({ orderDate: "2026-07-28", quantity: "12", limitPrice: "21.50", mode: "safe", plan: { strategy_type: "radar0458_pro", radar_tier: 3, radar_profile: "pro2", radar_cycle_id: "cycle-1", radar_cycle_capital: "12000" } })).toEqual({ order_date: "2026-07-28", quantity: "12", limit_price: "21.50", mode: "safe", radar_tier: 3, radar_profile: "pro2", radar_cycle_id: "cycle-1", radar_cycle_capital: "12000" });
  });

  it("keeps Dynamic Wave buy requests free of Radar snapshots", () => {
    expect(buildBuyOrderPositionRequest({ orderDate: "2026-07-28", quantity: "12", limitPrice: "21.50", mode: "aggressive", plan: { strategy_type: "dynamic_wave" } })).toEqual({ order_date: "2026-07-28", quantity: "12", limit_price: "21.50", mode: "aggressive" });
  });

  it("never loads Dynamic Wave mode recommendations for Radar", () => {
    expect(shouldLoadModeRecommendation("radar0458_pro")).toBe(false);
    expect(shouldLoadModeRecommendation("dynamic_wave")).toBe(true);
  });

  it("sends a Radar backtest profile override without Dynamic policies", () => {
    expect(buildBacktestCreateRequest({ configId: 9, startDate: "2026-01-01", endDate: "2026-01-31", strategyType: "radar0458_pro", radarProfile: "pro3", modePolicy: "weekly_rsi", positionSizingPolicy: "fixed_quantity" })).toEqual({ config_id: 9, start_date: "2026-01-01", end_date: "2026-01-31", pro_profile: "pro3" });
  });
});
