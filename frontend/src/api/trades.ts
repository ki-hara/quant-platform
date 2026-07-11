import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  ManualTradeRequest,
  ManualTradeResponse,
  LocOrderFillRequest,
  LocOrderRow,
  PositionHistoryRow,
  PositionRow,
  SignalExecutionRequest,
  SignalExecutionResponse,
  TradeRow,
} from "../types/api";

export function listPositions(configId: number, signal?: AbortSignal): Promise<PositionRow[]> {
  return apiGet<PositionRow[]>(`/api/strategy-configs/${configId}/positions`, signal);
}

export function updatePosition(
  positionId: number,
  request: Partial<Pick<PositionRow, "quantity" | "buy_price" | "status">>,
): Promise<PositionRow> {
  return apiPut<PositionRow>(`/api/positions/${positionId}`, request);
}

export function createBuyOrderPosition(
  configId: number,
  request: { order_date: string; quantity: string; limit_price: string; mode: string },
): Promise<PositionRow> {
  return apiPost<PositionRow>(`/api/strategy-configs/${configId}/positions/buy-order`, request);
}

export function listTrades(configId: number): Promise<TradeRow[]> {
  return apiGet<TradeRow[]>(`/api/strategy-configs/${configId}/trades`);
}

export function listPositionHistory(configId: number, signal?: AbortSignal): Promise<PositionHistoryRow[]> {
  return apiGet<PositionHistoryRow[]>(`/api/strategy-configs/${configId}/position-history`, signal);
}

export function listLocOrders(configId: number): Promise<LocOrderRow[]> {
  return apiGet<LocOrderRow[]>(`/api/strategy-configs/${configId}/loc-orders`);
}

export function createLocOrder(configId: number): Promise<LocOrderRow> {
  return apiPost<LocOrderRow>(`/api/strategy-configs/${configId}/loc-orders`, {});
}

export function fillLocOrder(orderId: number, request: LocOrderFillRequest): Promise<LocOrderRow> {
  return apiPost<LocOrderRow>(`/api/loc-orders/${orderId}/fill`, request);
}

export function markLocOrderUnfilled(orderId: number): Promise<LocOrderRow> {
  return apiPost<LocOrderRow>(`/api/loc-orders/${orderId}/unfilled`);
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
  await apiDelete(`/api/trades/${tradeId}`);
}
