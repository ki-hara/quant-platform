import { describe, it, expect } from "vitest";
import { positionFillPrice } from "./positionFillPrice";
import type { PositionRow } from "../types/api";

const row = { status: "pending", buy_price: "100", limit_price: "100", suggested_fill_price: "98.123" } as PositionRow;
describe("position fill price", () => {
  it("suggests the matching closing price", () => expect(positionFillPrice(row)).toBe("98.12"));
  it("waits if no confirmed quote exists", () => expect(positionFillPrice({ ...row, suggested_fill_price: null })).toBe(""));
  it("preserves filled prices", () => expect(positionFillPrice({ ...row, status: "open" })).toBe("100.00"));
  it("preserves saved custom prices", () => expect(positionFillPrice({ ...row, buy_price: "97" })).toBe("97.00"));
});
