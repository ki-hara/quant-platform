import { describe, expect, it } from "vitest";

import { hasCrossedLocOrders, netLocOrders, tickSizeForSymbol } from "./locNetting";


describe("LOC netting", () => {
  it("converts crossed buy and sell orders without duplicate prices", () => {
    const orders = netLocOrders(
      [
        { side: "sell", limitPrice: 65, quantity: 15 },
        { side: "buy", limitPrice: 70, quantity: 10 },
      ],
      0.01,
    );

    expect(orders).toEqual([
      { side: "sell", limitPrice: 70.01, quantity: 10 },
      { side: "buy", limitPrice: 64.99, quantity: 10 },
      { side: "sell", limitPrice: 65, quantity: 5 },
    ]);
  });

  it("detects crossed prices and selects the market tick size", () => {
    expect(
      hasCrossedLocOrders([
        { side: "sell", limitPrice: 65, quantity: 1 },
        { side: "buy", limitPrice: 70, quantity: 1 },
      ]),
    ).toBe(true);
    expect(tickSizeForSymbol("SOXL")).toBe(0.01);
    expect(tickSizeForSymbol("0193T0")).toBe(1);
  });
});
