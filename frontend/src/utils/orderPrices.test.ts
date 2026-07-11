import { describe, expect, it } from "vitest";


async function loadOrderPrices() {
  try {
    return await import("./orderPrices");
  } catch {
    throw new Error("Order price helpers are missing");
  }
}


describe("order price helpers", () => {
  it("formats a LOC buy recommendation to two decimal places", async () => {
    const { recommendedBuyPrice } = await loadOrderPrices();

    expect(recommendedBuyPrice("187.932553")).toBe("187.93");
  });

  it("uses the previous close for a sell execution price", async () => {
    const { recommendedSellPrice } = await loadOrderPrices();

    expect(
      recommendedSellPrice({
        previousClose: "219.725500",
        locBasisClose: "218.111111",
        latestClose: "217.222222",
        buyPrice: "194.650000",
      }),
    ).toBe("219.73");
  });

  it("falls back through LOC basis, latest close, and buy price", async () => {
    const { recommendedSellPrice } = await loadOrderPrices();

    expect(recommendedSellPrice({ locBasisClose: "218.111111", buyPrice: "194.650000" })).toBe("218.11");
    expect(recommendedSellPrice({ latestClose: "217.222222", buyPrice: "194.650000" })).toBe("217.22");
    expect(recommendedSellPrice({ buyPrice: "194.650000" })).toBe("194.65");
  });
});
