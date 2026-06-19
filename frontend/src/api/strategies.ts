import { apiGet, apiPost } from "./client";
import type {
  StrategyConfig,
  StrategyConfigCreateRequest,
  StrategyInfo,
  StrategySchema,
} from "../types/api";

export function listStrategies(): Promise<StrategyInfo[]> {
  return apiGet<StrategyInfo[]>("/api/strategies");
}

export function getStrategySchema(strategyType: string): Promise<StrategySchema> {
  return apiGet<StrategySchema>(`/api/strategies/${strategyType}/schema`);
}

export function listStrategyConfigs(): Promise<StrategyConfig[]> {
  return apiGet<StrategyConfig[]>("/api/strategy-configs");
}

export function createStrategyConfig(
  request: StrategyConfigCreateRequest,
): Promise<StrategyConfig> {
  return apiPost<StrategyConfig>("/api/strategy-configs", request);
}

export function getStrategyConfig(configId: number): Promise<StrategyConfig> {
  return apiGet<StrategyConfig>(`/api/strategy-configs/${configId}`);
}
