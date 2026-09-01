export type LocOrderSide = "buy" | "sell";
export type LocOrderExecution = "loc" | "market_on_close";

export interface LocOrderInput {
  side: LocOrderSide;
  execution?: LocOrderExecution;
  limitPrice: number | null;
  quantity: number;
}

export interface NettedLocOrder extends LocOrderInput {
  execution: LocOrderExecution;
}

export function netLocOrders(orders: LocOrderInput[], tickSize: number): NettedLocOrder[] {
  if (tickSize <= 0) return [];

  const buyByPrice = new Map<number, number>();
  const sellByPrice = new Map<number, number>();
  const tickUnits = priceToUnits(tickSize, tickSize);
  let marketCloseSellQuantity = 0;

  for (const order of orders) {
    if (order.quantity <= 0) continue;
    if (order.execution === "market_on_close") {
      if (order.side === "sell") marketCloseSellQuantity += Math.trunc(order.quantity);
      continue;
    }
    if (order.limitPrice === null || order.limitPrice <= 0) continue;
    const priceUnits = priceToUnits(order.limitPrice, tickSize);
    const target = order.side === "buy" ? buyByPrice : sellByPrice;
    target.set(priceUnits, (target.get(priceUnits) ?? 0) + Math.trunc(order.quantity));
  }

  const prices = [...new Set([...buyByPrice.keys(), ...sellByPrice.keys()])].sort((left, right) => right - left);
  let netQuantity = -sumQuantities(sellByPrice) - marketCloseSellQuantity;
  const result: NettedLocOrder[] = [];

  for (const priceUnits of prices) {
    const buyQuantity = buyByPrice.get(priceUnits) ?? 0;
    if (buyQuantity > 0) {
      const nextNetQuantity = netQuantity + buyQuantity;
      appendTransitionOrders(result, {
        before: netQuantity,
        after: nextNetQuantity,
        sellPriceUnits: priceUnits + tickUnits,
        buyPriceUnits: priceUnits,
        tickSize,
      });
      netQuantity = nextNetQuantity;
    }

    const sellQuantity = sellByPrice.get(priceUnits) ?? 0;
    if (sellQuantity > 0) {
      const nextNetQuantity = netQuantity + sellQuantity;
      appendTransitionOrders(result, {
        before: netQuantity,
        after: nextNetQuantity,
        sellPriceUnits: priceUnits,
        buyPriceUnits: priceUnits - tickUnits,
        tickSize,
      });
      netQuantity = nextNetQuantity;
    }
  }

  if (netQuantity < 0) {
    result.push({
      side: "sell",
      execution: "market_on_close",
      limitPrice: null,
      quantity: -netQuantity,
    });
  }
  return result.filter((order) => order.quantity > 0);
}

export function hasCrossedLocOrders(orders: LocOrderInput[]): boolean {
  const buys = orders.filter(
    (order) => order.side === "buy" && order.quantity > 0 && order.limitPrice !== null,
  );
  const sells = orders.filter((order) => order.side === "sell" && order.quantity > 0);
  return buys.some((buy) =>
    sells.some(
      (sell) =>
        sell.execution === "market_on_close" ||
        (sell.limitPrice !== null && sell.limitPrice <= (buy.limitPrice as number)),
    ),
  );
}

export function tickSizeForSymbol(symbol: string | null | undefined): number {
  const compact = (symbol ?? "").trim().toUpperCase();
  if (compact.endsWith(".KS") || compact.endsWith(".KQ") || /^[0-9A-Z]{6}$/.test(compact)) return 1;
  return 0.01;
}

function appendTransitionOrders(
  result: NettedLocOrder[],
  params: {
    before: number;
    after: number;
    sellPriceUnits: number;
    buyPriceUnits: number;
    tickSize: number;
  },
) {
  const { before, after, sellPriceUnits, buyPriceUnits, tickSize } = params;
  if (after === before) return;
  if (before < 0 && after > 0) {
    result.push({ side: "buy", execution: "loc", limitPrice: unitsToPrice(buyPriceUnits, tickSize), quantity: Math.min(after, after - before) });
    result.push({ side: "sell", execution: "loc", limitPrice: unitsToPrice(sellPriceUnits, tickSize), quantity: Math.min(-before, after - before) });
    return;
  }
  if (before < 0) {
    result.push({ side: "sell", execution: "loc", limitPrice: unitsToPrice(sellPriceUnits, tickSize), quantity: Math.min(-before, after - before) });
  }
  if (after > 0) {
    result.push({ side: "buy", execution: "loc", limitPrice: unitsToPrice(buyPriceUnits, tickSize), quantity: Math.min(after, after - before) });
  }
}

function priceToUnits(price: number, tickSize: number): number {
  return Math.round(price / tickSize);
}

function unitsToPrice(units: number, tickSize: number): number {
  return Number((units * tickSize).toFixed(tickSize >= 1 ? 0 : 2));
}

function sumQuantities(map: Map<number, number>): number {
  return [...map.values()].reduce((sum, quantity) => sum + quantity, 0);
}
