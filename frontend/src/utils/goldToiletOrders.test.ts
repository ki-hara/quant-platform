import { describe, expect, it } from "vitest";
import {
  goldToiletOrderResultItems,
  GOLD_TOILET_OPEN_POLL_INTERVAL_MS,
  orderCopyText,
  shouldPollForOpen,
} from "./goldToiletOrders";

describe("gold toilet order helpers", () => {
  it("polls every second until the automatic SOXL open is received", () => {
    const now = new Date("2026-08-04T15:00:00Z");
    expect(GOLD_TOILET_OPEN_POLL_INTERVAL_MS).toBe(1_000);
    expect(shouldPollForOpen("2026-08-04", null, now)).toBe(true);
    expect(shouldPollForOpen("2026-08-04", "131.505", now)).toBe(false);
    expect(shouldPollForOpen("2026-08-03", null, now)).toBe(false);
  });


  it("builds separate regular and LOC quantity cards", () => {
    const items = goldToiletOrderResultItems({
      breakout_buy_price: "48.97",
      order_quantity: 51,
      loc_buy_price: "43.74",
      allocation_amount: "2250.00",
      required_reservation_cash: "4728.21",
      cash_warning: false,
    });

    expect(items.map((item) => item.label)).toEqual([
      "매수가",
      "매수가 주문 수량",
      "LOC 매수가",
      "LOC 주문 수량",
    ]);
    expect(items[1].copyValue).toBe(51);
    expect(items[3].copyValue).toBe(51);
  });

  it("copies broker-ready raw values", () => {
    expect(orderCopyText("price", "48.97")).toBe("48.97");
    expect(orderCopyText("quantity", 51)).toBe("51");
  });
});
