import { useEffect, useRef, useState } from "react";
import { Check, Plus, Save, Trash2, Undo2, Wand2 } from "lucide-react";
import * as api from "../api/settlements";
import type { SettlementContext, SettlementDraft, SettlementPreview, SettlementRecord, SettlementSnapshot } from "../types/settlements";
import { proposeAllocations, createSettlementId } from "../utils/settlementDraft";
import { SettlementAllocationTable } from "./SettlementAllocationTable";
import "./tradeSettlement.css";

function previousDay() {
  const d=new Date(); d.setDate(d.getDate()-1);
  while (d.getDay()===0||d.getDay()===6) d.setDate(d.getDate()-1);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
const empty=(day:string):SettlementDraft=>({trade_date:day,snapshot_id:null,fills:[],allocations:[],manual_buy_settings:null});
const money=(v:string)=>Number(v).toLocaleString("en-US",{maximumFractionDigits:6});
const errorText=(e:unknown)=>e instanceof Error?e.message:"요청에 실패했습니다.";

export function TradeSettlementPanel({configId,sizingPolicy,cashShortagePolicy="defer",onCommitted,onDirtyChange}:{
  configId:number; sizingPolicy:string; cashShortagePolicy?:string; onCommitted:()=>void; onDirtyChange:(dirty:boolean)=>void;
}) {
  const [draft,setDraft]=useState<SettlementDraft>(()=>empty(previousDay()));
  const [snapshots,setSnapshots]=useState<SettlementSnapshot[]>([]);
  const [records,setRecords]=useState<SettlementRecord[]>([]);
  const [record,setRecord]=useState<SettlementRecord|null>(null);
  const [context,setContext]=useState<SettlementContext|null>(null);
  const [preview,setPreview]=useState<SettlementPreview|null>(null);
  const [busy,setBusy]=useState(false);
  const [dirty,setDirty]=useState(false);
  const [approved,setApproved]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const alive=useRef(true);
  const requestKey=useRef("");
  const contextEpoch=useRef(0);
  useEffect(()=>{onDirtyChange(dirty);return ()=>onDirtyChange(false);},[dirty,onDirtyChange]);
  useEffect(()=>{ alive.current=true; return ()=>{alive.current=false;}; },[]);
  useEffect(()=>{
    let active=true;
    api.listSnapshots(configId).then(v=>{if(active)setSnapshots(v);}).catch(e=>{if(active)setError(errorText(e));});
    return ()=>{active=false;};
  },[configId]);
  useEffect(()=>{
    const epoch=++contextEpoch.current;
    setContext(null);
    Promise.all([api.getSettlementContext(configId,draft.trade_date,draft.snapshot_id),api.listSettlements(configId,draft.trade_date)])
      .then(([ctx,rows])=>{if(alive.current&&epoch===contextEpoch.current){setContext(ctx);setRecords(rows);}})
      .catch(e=>{if(alive.current&&epoch===contextEpoch.current)setError(errorText(e));});
    return ()=>{contextEpoch.current++;};
  },[configId,draft.trade_date,draft.snapshot_id]);
  useEffect(()=>{
    const warn=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue="";}};
    window.addEventListener("beforeunload",warn);
    return ()=>window.removeEventListener("beforeunload",warn);
  },[dirty]);
  function edit(next:SettlementDraft) {setDraft(next);setDirty(true);setPreview(null);setApproved(false);setMessage("");}
  function switchDraft(next:SettlementDraft, saved:SettlementRecord|null=null) {
    if(dirty&&!window.confirm("저장하지 않은 정산 입력을 바꿀까요?"))return;
    setDraft(next);setRecord(saved);setPreview(null);setApproved(false);setDirty(false);setError("");setMessage("");
  }
  async function run(action:()=>Promise<void>) {
    setBusy(true);setError("");
    try {await action();} catch(e){if(alive.current)setError(errorText(e));}
    finally {if(alive.current)setBusy(false);}
  }
  async function persist(showPreview:boolean) {
    const saved=await api.saveDraft(configId,draft,record);
    if(!alive.current)return;
    setRecord(saved);setDirty(false);
    const savedRecords=await api.listSettlements(configId,draft.trade_date);
    if(!alive.current)return;
    setRecords(savedRecords);
    if(showPreview){
      const result=await api.previewSettlement(configId,saved.id);
      if(!alive.current)return;
      setPreview(result);setApproved(false);requestKey.current=createSettlementId();
    } else setMessage("초안을 저장했습니다.");
  }
  const locked=record?.status==="confirmed"||record?.status==="cancelled";
  return <section className="panel settlement-panel">
    <div className="panel-header"><h2>체결 정산</h2>
      <button type="button" disabled={busy} onClick={()=>run(async()=>{
        const saved=await api.saveSnapshot(configId,sizingPolicy,cashShortagePolicy);
        if(!alive.current)return;
        const updated=await api.listSnapshots(configId);
        if(!alive.current)return;
        setSnapshots(updated);
        setMessage(`${saved.trade_date} 주문표 #${saved.id} 저장 완료`);
      })}><Save size={16}/> 정산용 주문표 저장</button>
    </div>
    {error&&<div className="notice notice-error" role="alert">{error}</div>}
    {message&&<div className="notice" role="status">{message}</div>}
    <fieldset disabled={busy} className="settlement-fields">
      <div className="settlement-toolbar">
        <label>거래일<input type="date" value={draft.trade_date} onChange={e=>{if(e.target.value)switchDraft(empty(e.target.value));}}/></label>
        <label>주문표 저장본<select value={draft.snapshot_id??""} onChange={e=>switchDraft({...empty(draft.trade_date),snapshot_id:e.target.value?Number(e.target.value):null})}>
          <option value="">저장본 없음 · 수동 배분</option>
          {snapshots.filter(s=>s.trade_date===draft.trade_date).map(s=><option key={s.id} value={s.id}>#{s.id} · {s.created_at.replace("T"," ").slice(0,19)}</option>)}
        </select></label>
        <label>저장된 정산<select value={record?.id??""} onChange={e=>{
          const saved=records.find(r=>r.id===Number(e.target.value));switchDraft(saved?.draft??empty(draft.trade_date),saved??null);
        }}><option value="">새 정산</option>{records.map(r=><option key={r.id} value={r.id}>#{r.id} · {r.status==="draft"?"초안":r.status==="confirmed"?"확정":"취소"}</option>)}</select></label>
        <span className="settlement-close">상계 종가 <strong>{context?.close?money(context.close):"미확인"}</strong></span>
      </div>
      {draft.snapshot_id&&<details><summary>당시 원주문 / 퉁치기 주문</summary>
        <div className="settlement-reference">{["sources","netted"].map(key=>{
          const sheet=snapshots.find(s=>s.id===draft.snapshot_id)?.payload_json;
          const rows=key==="sources"?sheet?.sources:sheet?.netted;
          return <div key={key}><h3>{key==="sources"?"원주문":"퉁치기 주문"}</h3>{rows?.map((r,i)=><div key={i}>{r.side==="buy"?"매수":"매도"} {r.quantity}주 · {r.limit_price??"종가"}</div>)}</div>;
        })}</div></details>}
      <fieldset disabled={Boolean(locked)} className="settlement-fields">
        <div className="settlement-heading"><h3>증권사 실제 체결</h3>
          <button type="button" title="체결 추가" onClick={()=>edit({...draft,fills:[...draft.fills,{id:createSettlementId(),side:"sell",quantity:"",price:"",fee:"0"}]})}><Plus size={16}/> 체결 추가</button></div>
        <div className="settlement-scroll"><table className="settlement-table fills-table"><thead><tr><th>번호</th><th>방향</th><th>수량</th><th>실제 체결가</th><th>실제 수수료</th><th/></tr></thead>
          <tbody>{draft.fills.map((fill,i)=><tr key={fill.id}><td>{i+1}</td>
            <td><select aria-label={`체결 ${i+1} 방향`} value={fill.side} onChange={e=>edit({...draft,fills:draft.fills.map((f,n)=>n===i?{...f,side:e.target.value as "buy"|"sell"}:f)})}><option value="sell">매도</option><option value="buy">매수</option></select></td>
            {(["quantity","price","fee"] as const).map((key,k)=><td key={key}><input aria-label={`체결 ${i+1} ${["수량","가격","수수료"][k]}`} inputMode={key==="quantity"?"numeric":"decimal"} value={fill[key]} onChange={e=>edit({...draft,fills:draft.fills.map((f,n)=>n===i?{...f,[key]:e.target.value}:f)})}/></td>)}
            <td><button type="button" title="체결 삭제" aria-label={`체결 ${i+1} 삭제`} onClick={()=>edit({...draft,fills:draft.fills.filter((_,n)=>n!==i)})}><Trash2 size={16}/></button></td>
          </tr>)}</tbody></table></div>
        {!draft.snapshot_id&&<div className="settlement-toolbar">
          <label><span>수동 매수 설정</span><input type="checkbox" checked={!!draft.manual_buy_settings} onChange={e=>edit({...draft,manual_buy_settings:e.target.checked?{mode:"safe",sell_threshold_percent:"",max_holding_days:1}:null})}/></label>
          {draft.manual_buy_settings&&<>
            <label>당시 모드<select value={draft.manual_buy_settings.mode} onChange={e=>edit({...draft,manual_buy_settings:{...draft.manual_buy_settings!,mode:e.target.value as "safe"|"aggressive"}})}><option value="safe">안전</option><option value="aggressive">공세</option></select></label>
            <label>익절률 (%)<input inputMode="decimal" value={draft.manual_buy_settings.sell_threshold_percent} onChange={e=>edit({...draft,manual_buy_settings:{...draft.manual_buy_settings!,sell_threshold_percent:e.target.value}})}/></label>
            <label>최대 보유 거래일<input type="number" min={1} value={draft.manual_buy_settings.max_holding_days} onChange={e=>edit({...draft,manual_buy_settings:{...draft.manual_buy_settings!,max_holding_days:Number(e.target.value)}})}/></label>
          </>}
        </div>}
        <div className="settlement-heading"><h3>포지션 배분</h3><div className="settlement-actions">
          <button type="button" disabled={!context||!draft.snapshot_id} onClick={()=>{
            const rows=proposeAllocations(context!.sources,draft.fills,context!.close);
            if(!rows.length){setError("주문표와 실제 수량이 다르거나 종가가 없습니다. 배분을 직접 확인해 주세요.");return;}
            edit({...draft,allocations:rows});
          }}><Wand2 size={16}/> 배분 후보</button>
          <button type="button" disabled={!context?.sources.length} onClick={()=>{
            const s=context!.sources[0];
            edit({...draft,allocations:[...draft.allocations,{source_id:s.id,side:s.side,quantity:"",kind:"offset",fill_id:null,position_id:s.position_id,change_reason:""}]});
          }}><Plus size={16}/> 배분 추가</button>
        </div></div>
        {context&&<SettlementAllocationTable rows={draft.allocations} fills={draft.fills} context={context} onChange={rows=>edit({...draft,allocations:rows})}/>}
        <div className="settlement-actions">
          <button type="button" onClick={()=>run(()=>persist(false))}><Save size={16}/> 초안 저장</button>
          <button type="button" disabled={!draft.allocations.length} onClick={()=>run(()=>persist(true))}><Check size={16}/> 배분 검산</button>
        </div>
      </fieldset>
      {preview&&<div className="settlement-preview">
        {preview.blocking_errors.map((e,i)=><div className="notice notice-error" key={i}>{e}</div>)}
        <div className="settlement-scroll"><table className="settlement-table"><thead><tr><th>포지션</th><th>구분</th><th>수량</th><th>적용 가격</th><th>수수료</th><th>예상 손익</th><th>정산 후 잔량</th></tr></thead>
          <tbody>{preview.rows.map((r,i)=>{
            const position=context?.positions.find(p=>p.id===r.position_id);
            const allocated=preview.rows.filter(v=>v.position_id===r.position_id&&v.side===r.side).reduce((sum,v)=>sum+v.quantity,0);
            return <tr key={i}><td>{position?`${position.buy_date} · #${position.id}`:"신규 매수"}</td><td>{r.side==="buy"?"매수":"매도"} · {r.kind==="offset"?"종가 상계":"실제 체결"}</td><td>{r.quantity}주</td><td>{money(r.price)}</td><td>{money(r.fee)}</td><td>{money(r.realized_pnl)}</td><td>{position?`${Number(position.quantity)-allocated}주${r.side==="buy"?" 대기":""}`:"-"}</td></tr>;
          })}</tbody></table></div>
        <div className="settlement-totals"><span>현금 증감 <strong>{money(preview.cash_delta)}</strong></span><span>수수료 <strong>{money(preview.total_fee)}</strong></span><span>전략 실현손익 <strong>{money(preview.realized_pnl)}</strong></span></div>
        <label className="settlement-approval"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/> 실제 체결과 포지션별 상계 배분을 확인했습니다.</label>
        <button type="button" disabled={!approved||!!preview.blocking_errors.length||!!locked||dirty} onClick={()=>run(async()=>{
          if(!record||!window.confirm("확인한 배분으로 매수·매도를 함께 기록할까요?"))return;
          await api.confirmSettlement(configId,record.id,preview.preview_hash,requestKey.current);
          if(!alive.current)return;
          setRecord({...record,status:"confirmed"});setPreview(null);setDirty(false);setMessage("정산을 확정했습니다.");
          const updated=await api.listSettlements(configId,draft.trade_date);
          if(!alive.current)return;
          setRecords(updated);onCommitted();
        })}><Check size={16}/> 정산 일괄 확정</button>
      </div>}
      {record?.status==="confirmed"&&<button type="button" onClick={()=>run(async()=>{
        if(!window.confirm("이 정산 전체를 취소할까요? 후속 변경이 있으면 취소할 수 없습니다."))return;
        await api.cancelSettlement(configId,record.id);
        if(!alive.current)return;
        setRecord({...record,status:"cancelled"});setMessage("정산을 취소했습니다.");
        const updated=await api.listSettlements(configId,draft.trade_date);
        if(!alive.current)return;
        setRecords(updated);onCommitted();
      })}><Undo2 size={16}/> 정산 취소</button>}
    </fieldset>
  </section>;
}
