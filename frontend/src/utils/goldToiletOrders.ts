import type { GoldToiletCalculation } from "../api/goldToiletOrders";
import { marketDateIso } from "./format";

export const GOLD_TOILET_OPEN_POLL_INTERVAL_MS = 1_000;

export function shouldPollForOpen(
  orderDate: string,
  providerMarketOpen: string | null | undefined,
  now = new Date(),
): boolean {
  return !providerMarketOpen && orderDate === marketDateIso("SOXL", now);
}

export interface GoldToiletOrderResultItem {
  label: string;
  value: string;
  copyValue: string | number;
  kind: "price" | "quantity";
}

export function goldToiletOrderResultItems(
  calculation: GoldToiletCalculation | null,
): GoldToiletOrderResultItem[] {
  if (!calculation) return [];

  return [
    {
      label: "매수가",
      value: `$${Number(calculation.breakout_buy_price).toFixed(2)}`,
      copyValue: calculation.breakout_buy_price,
      kind: "price",
    },
    {
      label: "매수가 주문 수량",
      value: `${calculation.order_quantity.toLocaleString()}주`,
      copyValue: calculation.order_quantity,
      kind: "quantity",
    },
    {
      label: "LOC 매수가",
      value: `$${Number(calculation.loc_buy_price).toFixed(2)}`,
      copyValue: calculation.loc_buy_price,
      kind: "price",
    },
    {
      label: "LOC 주문 수량",
      value: `${calculation.order_quantity.toLocaleString()}주`,
      copyValue: calculation.order_quantity,
      kind: "quantity",
    },
  ];
}


export function orderCopyText(kind: "price" | "quantity", value: string | number): string {
  return kind === "quantity" ? String(Math.trunc(Number(value))) : Number(value).toFixed(2);
}
