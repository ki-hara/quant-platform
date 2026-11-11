export interface QuickCandidate {
  position_id:number; source_id:string; side:'buy'|'sell'; buy_date:string; buy_price:string;
  quantity:number; limit_price:string|null; price:string|null; selected:boolean; eligible:boolean; reason:string;
}
export interface QuickRow extends QuickCandidate {
  priceInput:string; quantityInput:string; feeInput:string; touched:Partial<Record<'priceInput'|'quantityInput'|'feeInput'|'selected',boolean>>;
}
export function mergeCandidates(candidates:QuickCandidate[], previous:QuickRow[]):QuickRow[] {
  return candidates.map(candidate=>{
    const old=previous.find(row=>row.position_id===candidate.position_id&&row.side===candidate.side);
    return {...candidate,
      priceInput:old?.touched.priceInput?old.priceInput:candidate.price??'',
      quantityInput:old?.touched.quantityInput?old.quantityInput:String(candidate.quantity),
      feeInput:old?.touched.feeInput?old.feeInput:'',
      selected:candidate.eligible && (old?.touched.selected?old.selected:candidate.selected),
      touched:old?.touched??{}};
  });
}
