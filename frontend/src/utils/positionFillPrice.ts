import type { PositionRow } from "../types/api";

export function positionFillPrice(position: PositionRow): string {
  if (position.status.toLowerCase() !== "pending") return Number(position.buy_price).toFixed(2);
  // Retain an explicitly saved price that differs from the original LOC price.
  if (position.limit_price != null && Number(position.buy_price) !== Number(position.limit_price)) {
    return Number(position.buy_price).toFixed(2);
  }
  return position.suggested_fill_price == null ? "" : Number(position.suggested_fill_price).toFixed(2);
}
