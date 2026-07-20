import { describe, expect, it } from "vitest";

import { executableLocBuyOrders, locBuyBlockMessage } from "./executableLocOrders";

const order = {
  step: 1,
  limit_price: "145.630000",
  quantity: 10,
  cumulative_quantity: 10,
  cumulative_amount: "1456.300000",
  compressed: false,
};

describe("executable LOC buy orders", () => {
  it("returns no buy orders when the daily plan is blocked", () => {
    const plan = {
      buy_available: false,
      LOC: { orders: [order] },
    };

    expect(executableLocBuyOrders(plan)).toEqual([]);
  });

  it("returns planned orders when buying is available", () => {
    const plan = {
      buy_available: true,
      LOC: { orders: [order] },
    };

    expect(executableLocBuyOrders(plan)).toEqual([order]);
  });

  it("describes the reached split limit with the current position count", () => {
    expect(
      locBuyBlockMessage({
        open_position_count: 7,
        mode_split_count: 7,
        LOC: { blocking_reason: "split_limit_reached" },
      }),
    ).toBe("분할 매수 한도 도달 (보유 7 / 7)");
  });
});
