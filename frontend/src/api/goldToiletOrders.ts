import { apiDelete, apiGet, apiPut } from "./client";

export interface GoldToiletAccount {
  capital: string;
  cash: string;
  updated_at: string;
}

export interface GoldToiletOrderSheet {
  order_date: string;
  entry_percent: string;
  allocation_percent: string;
  loc_percent: string;
  provider_market_open: string | null;
  provider_open_source: string | null;
  provider_open_observed_at: string | null;
  provider_open_last_checked_at: string | null;
  provider_open_failure_reason: string | null;
  manual_market_open: string | null;
  manual_open_observed_at: string | null;
  effective_market_open: string | null;
  effective_open_source: "yahoo_1m_regular_session" | "manual" | null;
  updated_at: string;
}

export interface GoldToiletCalculation {
  breakout_buy_price: string;
  order_quantity: number;
  loc_buy_price: string;
  allocation_amount: string;
  required_reservation_cash: string;
  cash_warning: boolean;
}

export type GoldToiletOpenStatus = "waiting" | "ready" | "failed";

export interface GoldToiletOrderResponse {
  symbol: "SOXL";
  account: GoldToiletAccount | null;
  sheet: GoldToiletOrderSheet | null;
  calculation: GoldToiletCalculation | null;
  open_status: GoldToiletOpenStatus;
  open_failure_reason: string | null;
}

export function getGoldToiletOrderSheet(orderDate: string, signal?: AbortSignal) {
  return apiGet<GoldToiletOrderResponse>(
    `/api/gold-toilet/order-sheet?order_date=${encodeURIComponent(orderDate)}`,
    signal,
  );
}

export function updateGoldToiletAccount(body: { capital: string; cash: string }) {
  return apiPut<GoldToiletOrderResponse>("/api/gold-toilet/account", body);
}

export function updateGoldToiletOrderSheet(
  orderDate: string,
  body: {
    entry_percent: string;
    allocation_percent: string;
    loc_percent: string;
  },
) {
  return apiPut<GoldToiletOrderResponse>(
    `/api/gold-toilet/order-sheet/${encodeURIComponent(orderDate)}`,
    body,
  );
}

export function setGoldToiletManualOpen(orderDate: string, marketOpen: string) {
  return apiPut<GoldToiletOrderResponse>(
    `/api/gold-toilet/order-sheet/${encodeURIComponent(orderDate)}/manual-open`,
    { market_open: marketOpen },
  );
}

export function clearGoldToiletManualOpen(orderDate: string) {
  return apiDelete<GoldToiletOrderResponse>(
    `/api/gold-toilet/order-sheet/${encodeURIComponent(orderDate)}/manual-open`,
  );
}
