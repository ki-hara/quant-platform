export interface LocBuyOrderPlan<T> {
  buy_available: boolean;
  strategy_type?: string | null;
  radar_tier?: number | null;
  LOC: { orders: T[]; limit_price?: string; quantity?: number };
}

export function executableLocBuyOrders<T>(plan: LocBuyOrderPlan<T> | null): T[] {
  if (!plan?.buy_available) return [];
  if (plan.LOC.orders.length > 0) return plan.LOC.orders;
  if (plan.strategy_type !== "radar0458_pro" || plan.radar_tier == null || !plan.LOC.limit_price || !plan.LOC.quantity) return [];
  return [{ step: plan.radar_tier, limit_price: plan.LOC.limit_price, quantity: plan.LOC.quantity, cumulative_quantity: plan.LOC.quantity, cumulative_amount: String(Number(plan.LOC.limit_price) * plan.LOC.quantity), compressed: false } as T];
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