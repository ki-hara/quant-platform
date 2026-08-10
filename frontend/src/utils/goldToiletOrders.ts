import type { GoldToiletOpenStatus } from "../api/goldToiletOrders";
import { marketDateIso } from "./format";

export const GOLD_TOILET_OPEN_POLL_INTERVAL_MS = 1_000;

export function shouldPollForOpen(
  orderDate: string,
  openStatus: GoldToiletOpenStatus,
  now = new Date(),
): boolean {
  return openStatus !== "ready" && orderDate === marketDateIso("SOXL", now);
}

export function canOverrideOpen(providerMarketOpen: string | null | undefined): boolean {
  return Boolean(providerMarketOpen);
}

export function orderCopyText(kind: "price" | "quantity", value: string | number): string {
  return kind === "quantity" ? String(Math.trunc(Number(value))) : Number(value).toFixed(2);
}
