export type Side = "buy" | "sell";
export interface SettlementFill { id: string; side: Side; quantity: string | number; price: string; fee: string }
export interface SettlementSource {
  id: string; side: Side; quantity: number; position_id: number | null;
  limit_price: string | null; execution: string; buy_date?: string; buy_price?: string;
}
export interface SettlementAllocation {
  source_id: string; side: Side; quantity: string | number; kind: "actual" | "offset";
  fill_id: string | null; position_id: number | null; change_reason: string;
}
export interface SettlementDraft {
  snapshot_id: number | null; trade_date: string; fills: SettlementFill[];
  allocations: SettlementAllocation[];
  manual_buy_settings: { mode: "safe" | "aggressive"; sell_threshold_percent: string; max_holding_days: number } | null;
}
export interface SettlementSnapshot {
  id: number; trade_date: string; created_at: string;
  payload_json: {sources: SettlementSource[]; netted: {side: Side; quantity: number; limit_price: string | null}[]};
}
export interface SettlementRecord {
  id: number; status: string; revision: number; trade_date: string; draft: SettlementDraft;
}
export interface SettlementContext {
  sources: SettlementSource[]; close: string | null;
  positions: {id:number; buy_date:string; quantity:string; status:string; buy_price:string}[];
}
export interface SettlementPreview {
  rows: {source_id:string; position_id:number|null; side:Side; quantity:number; price:string; fee:string; kind:string; realized_pnl:string}[];
  blocking_errors:string[]; warnings:string[]; preview_hash:string;
  cash_delta:string; total_fee:string; realized_pnl:string;
}
