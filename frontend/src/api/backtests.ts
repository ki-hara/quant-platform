import { apiGet, apiPost, apiUrl } from "./client";
import type { BacktestCreateRequest, BacktestRun } from "../types/api";

export function createBacktest(request: BacktestCreateRequest): Promise<BacktestRun> {
  return apiPost<BacktestRun>("/api/backtests", request);
}

export function getBacktest(runId: number): Promise<BacktestRun> {
  return apiGet<BacktestRun>(`/api/backtests/${runId}`);
}

export function getBacktestDailyCsvUrl(runId: number): string {
  return apiUrl(`/api/backtests/${runId}/daily.csv`);
}

export function getBacktestTradesCsvUrl(runId: number): string {
  return apiUrl(`/api/backtests/${runId}/trades.csv`);
}

export function getBacktestSummaryCsvUrl(runId: number): string {
  return apiUrl(`/api/backtests/${runId}/summary.csv`);
}
