import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  StrategyConfigSnapshot,
  StrategyConfigSnapshotCreateRequest,
  StrategyConfig,
  StrategyConfigCreateRequest,
  StrategyConfigUpdateRequest,
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

export function updateStrategyConfig(
  configId: number,
  request: StrategyConfigUpdateRequest,
): Promise<StrategyConfig> {
  return apiPut<StrategyConfig>(`/api/strategy-configs/${configId}`, request);
}

export function deleteStrategyConfig(configId: number): Promise<void> {
  return apiDelete(`/api/strategy-configs/${configId}`);
}

export function listStrategyConfigSnapshots(configId: number): Promise<StrategyConfigSnapshot[]> {
  return apiGet<StrategyConfigSnapshot[]>(`/api/strategy-configs/${configId}/snapshots`);
}

export function createStrategyConfigSnapshot(
  configId: number,
  request: StrategyConfigSnapshotCreateRequest,
): Promise<StrategyConfigSnapshot> {
  return apiPost<StrategyConfigSnapshot>(`/api/strategy-configs/${configId}/snapshots`, request);
}

export function applyStrategyConfigSnapshot(configId: number, snapshotId: number): Promise<StrategyConfig> {
  return apiPost<StrategyConfig>(`/api/strategy-configs/${configId}/snapshots/${snapshotId}/apply`);
}

export function deleteStrategyConfigSnapshot(configId: number, snapshotId: number): Promise<void> {
  return apiDelete(`/api/strategy-configs/${configId}/snapshots/${snapshotId}`);
}
