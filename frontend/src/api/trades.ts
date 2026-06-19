import { apiGet, apiPost } from "./client";
import type {
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
