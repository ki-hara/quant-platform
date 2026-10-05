import { Trash2 } from "lucide-react";
import type { SettlementAllocation, SettlementContext, SettlementFill } from "../types/settlements";

export function SettlementAllocationTable({rows,context,fills,onChange}: {
  rows:SettlementAllocation[]; context:SettlementContext; fills:SettlementFill[];
  onChange:(rows:SettlementAllocation[])=>void;
}) {
  const change=(i:number,patch:Partial<SettlementAllocation>)=>onChange(rows.map((r,n)=>n===i?{...r,...patch}:r));
  return <div className="settlement-scroll"><table className="settlement-table">
    <thead><tr><th>원주문 / 포지션</th><th>체결 연결</th><th>수량</th><th>대기 매수 연결</th><th>주문 변경 사유</th><th /></tr></thead>
    <tbody>{rows.map((row,i)=><tr key={i}>
      <td><select aria-label={`배분 ${i+1} 원주문`} value={row.source_id} onChange={e=>{
        const s=context.sources.find(s=>s.id===e.target.value)!;
        change(i,{source_id:s.id,side:s.side,position_id:s.side==="sell"?s.position_id:null,fill_id:null,kind:"offset"});
      }}>{context.sources.map(s=><option key={s.id} value={s.id}>
        {s.side==="buy"?"매수":"매도"} {s.buy_date??s.id} · {s.quantity===100000000?"수동":`${s.quantity}주`} {s.limit_price?`/ 목표 ${s.limit_price}`:""}
      </option>)}</select>
        {row.side==="sell"&&(()=>{
          const source=context.sources.find(s=>s.id===row.source_id);
          const position=context.positions.find(p=>p.id===source?.position_id);
          return position&&<div className="settlement-position-detail">매수가 {Number(position.buy_price).toLocaleString("en-US")} · 가용 {Number(position.quantity)}주</div>;
        })()}
      </td>
      <td><select aria-label={`배분 ${i+1} 체결`} value={row.fill_id??""} onChange={e=>change(i,{fill_id:e.target.value||null,kind:e.target.value?"actual":"offset"})}>
        <option value="">종가 상계 ({context.close??"종가 없음"})</option>
        {fills.filter(f=>f.side===row.side).map(f=><option key={f.id} value={f.id}>체결 {fills.indexOf(f)+1} · {f.quantity}주 / {f.price}</option>)}
      </select></td>
      <td><input aria-label={`배분 ${i+1} 수량`} inputMode="numeric" value={row.quantity} onChange={e=>change(i,{quantity:e.target.value})}/></td>
      <td>{row.side==="buy"?<select aria-label={`배분 ${i+1} 대기 포지션`} value={row.position_id??""} onChange={e=>change(i,{position_id:e.target.value?Number(e.target.value):null})}>
        <option value="">신규 생성</option>{context.positions.filter(p=>p.status==="pending").map(p=><option key={p.id} value={p.id}>{p.buy_date} · {p.quantity}주 · #{p.id}</option>)}
      </select>:<span>-</span>}</td>
      <td><input aria-label={`배분 ${i+1} 변경 사유`} value={row.change_reason} onChange={e=>change(i,{change_reason:e.target.value})}/></td>
      <td><button type="button" title="배분 삭제" aria-label={`배분 ${i+1} 삭제`} onClick={()=>onChange(rows.filter((_,n)=>n!==i))}><Trash2 size={16}/></button></td>
    </tr>)}</tbody>
  </table></div>;
}
