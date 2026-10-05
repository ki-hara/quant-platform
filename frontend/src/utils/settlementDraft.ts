import type { SettlementSource, SettlementFill, SettlementAllocation, Side } from "../types/settlements";

export function createSettlementId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), n=>n.toString(16).padStart(2,"0")).join("");
}

export function proposeAllocations(sources: SettlementSource[], fills: SettlementFill[], close: string|null): SettlementAllocation[] {
  if (!close || Number(close)<=0 || fills.some(f=>!Number(f.price)||!Number.isInteger(Number(f.quantity))||Number(f.quantity)<=0)) return [];
  const eligible = sources.filter(s=>s.execution==="market_on_close" ||
    (s.limit_price!==null && (s.side==="buy"?Number(close)<=Number(s.limit_price):Number(close)>=Number(s.limit_price))))
    .map(s=>({...s,remaining:s.quantity}));
  const total = (side:Side)=>eligible.filter(s=>s.side===side).reduce((a,s)=>a+s.quantity,0);
  const offset = Math.min(total("buy"),total("sell"));
  for (const side of ["buy","sell"] as const) {
    if (fills.filter(f=>f.side===side).reduce((a,f)=>a+Number(f.quantity),0)!==total(side)-offset) return [];
  }
  const result:SettlementAllocation[]=[];
  function take(side:Side,quantity:number,fill_id:string|null) {
    for (const source of eligible.filter(s=>s.side===side)) {
      const count=Math.min(source.remaining,quantity);
      if (!count) continue;
      result.push({source_id:source.id,side,quantity:count,kind:fill_id?"actual":"offset",fill_id,
        position_id:side==="sell"?source.position_id:null,change_reason:""});
      source.remaining-=count; quantity-=count;
    }
  }
  take("sell",offset,null); take("buy",offset,null);
  for (const fill of fills) take(fill.side,Number(fill.quantity),fill.id);
  return result;
}
