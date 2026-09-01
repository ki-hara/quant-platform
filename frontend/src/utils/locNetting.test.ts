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
      { side: "sell", execution: "loc", limitPrice: 70.01, quantity: 10 },
      { side: "buy", execution: "loc", limitPrice: 64.99, quantity: 10 },
      { side: "sell", execution: "loc", limitPrice: 65, quantity: 5 },
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

  it("nets a market close sell against a LOC buy without overlapping orders", () => {
    const orders = netLocOrders(
      [
        { side: "sell", execution: "market_on_close", limitPrice: null, quantity: 7 },
        { side: "buy", execution: "loc", limitPrice: 117.3, quantity: 12 },
      ],
      0.01,
    );

    expect(orders).toEqual([
      { side: "buy", execution: "loc", limitPrice: 117.3, quantity: 5 },
      { side: "sell", execution: "loc", limitPrice: 117.31, quantity: 7 },
    ]);
    expect(
      hasCrossedLocOrders([
        { side: "sell", execution: "market_on_close", limitPrice: null, quantity: 7 },
        { side: "buy", execution: "loc", limitPrice: 117.3, quantity: 12 },
      ]),
    ).toBe(true);
  });
});
