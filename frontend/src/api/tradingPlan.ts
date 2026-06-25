import { apiGet, apiPost, apiPut } from "./client";
import type {
  ChartRange,
  ConfirmedModeUpdateRequest,
  DailyPlan,
  MarketRefreshResponse,
  ModeRecommendation,
  TradingChart,
} from "../types/api";

export function getDailyPlan(configId: number): Promise<DailyPlan> {
  return apiGet<DailyPlan>(`/api/strategy-configs/${configId}/daily-plan`);
}

export function getChart(configId: number, range: ChartRange): Promise<TradingChart> {
  return apiGet<TradingChart>(`/api/strategy-configs/${configId}/chart?range=${range}`);
}

export function getModeRecommendation(configId: number): Promise<ModeRecommendation> {
  return apiGet<ModeRecommendation>(`/api/strategy-configs/${configId}/mode-recommendation`);
}

export function setConfirmedMode(
  configId: number,
  request: ConfirmedModeUpdateRequest,
): Promise<ModeRecommendation> {
  return apiPut<ModeRecommendation>(`/api/strategy-configs/${configId}/confirmed-mode`, request);
}

export function refreshMarketData(configId: number): Promise<MarketRefreshResponse> {
  return apiPost<MarketRefreshResponse>(`/api/strategy-configs/${configId}/market-data/refresh`);
}
