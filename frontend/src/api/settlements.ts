import { apiGet, apiPost, apiPut } from "./client";
import type { SettlementSnapshot, SettlementDraft, SettlementRecord, SettlementPreview, SettlementContext } from "../types/settlements";
import type { QuickCandidate } from "../utils/quickSettlement";
const base = (id: number) => `/api/strategy-configs/${id}`;
export const listSnapshots = (id:number) => apiGet<SettlementSnapshot[]>(`${base(id)}/order-snapshots`);
export const saveSnapshot = (id:number, sizing_policy:string, cash_shortage_policy:string) => apiPost<SettlementSnapshot>(`${base(id)}/order-snapshots`, {sizing_policy,cash_shortage_policy});
export const listSettlements = (id:number, day:string) => apiGet<SettlementRecord[]>(`${base(id)}/settlements?trade_date=${day}`);
export const getSettlementContext = (id:number, day:string, snapshot:number|null) =>
  apiGet<SettlementContext>(`${base(id)}/settlement-context?trade_date=${day}${snapshot ? `&snapshot_id=${snapshot}` : ""}`);
export const saveDraft = (id:number, draft:SettlementDraft, record:SettlementRecord|null) =>
  record ? apiPut<SettlementRecord>(`${base(id)}/settlements/${record.id}/draft`, {draft, expected_revision:record.revision})
    : apiPost<SettlementRecord>(`${base(id)}/settlements`, draft);
export const previewSettlement = (id:number, record:number) => apiPost<SettlementPreview>(`${base(id)}/settlements/${record}/preview`);
export const confirmSettlement = (id:number, record:number, preview_hash:string, idempotency_key:string) =>
  apiPost(`${base(id)}/settlements/${record}/confirm`, {preview_hash, idempotency_key});
export const cancelSettlement = (id:number, record:number) => apiPost(`${base(id)}/settlements/${record}/cancel`);
export interface QuickCandidates {trade_date:string;close:string|null;state_hash:string;rows:QuickCandidate[]}
export interface QuickPreview {record:SettlementRecord;preview:SettlementPreview;actual_buy:number;actual_sell:number;offset_quantity:number}
export const getCandidates=(id:number,day:string)=>apiGet<QuickCandidates>(`${base(id)}/settlement-candidates?trade_date=${day}`);
export const prepareQuick=(id:number,body:{trade_date:string;state_hash:string;netting:boolean;selections:{position_id:number;quantity:number;price:string;fee:string|null}[]})=>
  apiPost<QuickPreview>(`${base(id)}/settlements/quick-preview`,body);
