import { apiGet, apiPost, apiUrl } from "./client";
import type {
  ManualTradeRequest,
  ManualTradeResponse,
  PositionRow,
  SignalExecutionRequest,
  SignalExecutionResponse,
  TradeRow,
} from "../types/api";

export function listPositions(configId: number): Promise<PositionRow[]> {
  return apiGet<PositionRow[]>(`/api/strategy-configs/${configId}/positions`);
}

export function listTrades(configId: number): Promise<TradeRow[]> {
  return apiGet<TradeRow[]>(`/api/strategy-configs/${configId}/trades`);
}

export function executeSignal(
  configId: number,
  request: SignalExecutionRequest,
): Promise<SignalExecutionResponse> {
  return apiPost<SignalExecutionResponse>(
    `/api/strategy-configs/${configId}/signals/execute`,
    request,
  );
}

export function recordManualTrade(request: ManualTradeRequest): Promise<ManualTradeResponse> {
  return apiPost<ManualTradeResponse>("/api/trades/manual", request);
}

export async function deleteTrade(tradeId: number): Promise<void> {
  const response = await fetch(apiUrl(`/api/trades/${tradeId}`), { method: "DELETE" });
  if (!response.ok) throw new Error(await response.text());
}
