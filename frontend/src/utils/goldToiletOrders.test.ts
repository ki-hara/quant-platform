import { describe, expect, it } from "vitest";
import {
  goldToiletOrderResultItems,
  GOLD_TOILET_OPEN_POLL_INTERVAL_MS,
  orderCopyText,
  reconcileGoldToiletDraft,
  shouldPollForOpen,
  sourceLabel,
} from "./goldToiletOrders";

describe("gold toilet order helpers", () => {
  it("polls every two seconds until the automatic SOXL open is received", () => {
    const now = new Date("2026-08-04T15:00:00Z");
    expect(GOLD_TOILET_OPEN_POLL_INTERVAL_MS).toBe(2_000);
    expect(shouldPollForOpen("2026-08-04", null, now)).toBe(true);
    expect(shouldPollForOpen("2026-08-04", "131.505", now)).toBe(false);
    expect(shouldPollForOpen("2026-08-03", null, now)).toBe(false);
  });

  it("preserves account and order-sheet input while an open-price poll refreshes results", () => {
    const typedDraft = {
      capital: "10000",
      cash: "9876.54",
      entryPercent: "1.49",
      allocationPercent: "22.50",
      locPercent: "-9.34",
    };

    const refreshed = reconcileGoldToiletDraft(
      typedDraft,
      {
        account: { capital: "8000", cash: "1000" },
        sheet: {
          entry_percent: "1.20",
          allocation_percent: "20.00",
          loc_percent: "-8.00",
        },
      },
      true,
    );

    expect(refreshed).toEqual(typedDraft);
  });

  it("labels every automatic open source in Korean", () => {
    expect(sourceLabel("cnbc_us_quote")).toBe("CNBC 미국 실시간 시세");
    expect(sourceLabel("finnhub_us_quote")).toBe("Finnhub 미국 실시간 시세");
    expect(sourceLabel("yahoo_1d_regular_session")).toBe("Yahoo 당일 일봉 시가");
    expect(sourceLabel("manual")).toBe("직접 입력 강제 적용");
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
