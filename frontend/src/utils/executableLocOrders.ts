export interface LocBuyOrderPlan<T> {
  buy_available: boolean;
  LOC: { orders: T[] };
}

export function executableLocBuyOrders<T>(plan: LocBuyOrderPlan<T> | null): T[] {
  return plan?.buy_available ? plan.LOC.orders : [];
}
export interface LocBuyBlockInfo {
  open_position_count: number;
  mode_split_count: number | null;
  LOC: { blocking_reason: string | null };
}

export function locBuyBlockMessage(plan: LocBuyBlockInfo | null): string | null {
  if (plan?.LOC.blocking_reason !== "split_limit_reached" || plan.mode_split_count === null) return null;
  return `분할 매수 한도 도달 (보유 ${plan.open_position_count} / ${plan.mode_split_count})`;
}