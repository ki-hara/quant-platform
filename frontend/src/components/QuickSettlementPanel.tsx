import { useEffect, useRef, useState } from 'react';
import { Check, RefreshCw, Undo2 } from 'lucide-react';
import * as api from '../api/settlements';
import { createSettlementId } from '../utils/settlementDraft';
import { mergeCandidates, type QuickRow } from '../utils/quickSettlement';
import { TradeSettlementPanel } from './TradeSettlementPanel';
import './tradeSettlement.css';

const money=(value:string)=>Number(value).toLocaleString('en-US',{maximumFractionDigits:6});
const reasons:Record<string,string>={profit:'익절 후보',maturity:'보유기간 만료',buy:'매수 후보',holding:'조건 미충족',policy_missing:'매수 설정 확인 필요'};
function previousDay(){const d=new Date();d.setDate(d.getDate()-1);while(!d.getDay()||d.getDay()===6)d.setDate(d.getDate()-1);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}

export function QuickSettlementPanel(props:{configId:number;sizingPolicy:string;cashShortagePolicy?:string;onCommitted:()=>void;onDirtyChange:(dirty:boolean)=>void}) {
  const [day,setDay]=useState(previousDay);
  const [data,setData]=useState<api.QuickCandidates|null>(null);
  const [rows,setRows]=useState<QuickRow[]>([]);
  const [netting,setNetting]=useState(true);
  const [busy,setBusy]=useState(false);
  const [dirty,setDirty]=useState(false);
  const [detailDirty,setDetailDirty]=useState(false);
  const [detail,setDetail]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [confirmed,setConfirmed]=useState<number|null>(null);
  const [pending,setPending]=useState<{result:api.QuickPreview;key:string}|null>(null);
  const epoch=useRef(0);
  const alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;};},[]);
  useEffect(()=>{props.onDirtyChange(dirty||detailDirty);return()=>props.onDirtyChange(false);},[dirty,detailDirty,props.onDirtyChange]);
  useEffect(()=>{
    const warn=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};
    window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);
  },[dirty]);
  async function reload(preserve=true){
    const request=++epoch.current;
    setBusy(true);setError('');setPending(null);
    try{const next=await api.getCandidates(props.configId,day);if(!alive.current||request!==epoch.current)return;
      setData(next);setRows(old=>mergeCandidates(next.rows,preserve?old:[]));
    }catch(e){if(alive.current&&request===epoch.current)setError(e instanceof Error?e.message:'조회에 실패했습니다.');}
    finally{if(alive.current&&request===epoch.current)setBusy(false);}
  }
  useEffect(()=>{setData(null);setRows([]);void reload(false);},[props.configId,day]);
  function edit(id:number,patch:Partial<QuickRow>){setRows(old=>old.map(row=>row.position_id===id?{...row,...patch,touched:true}:row));setDirty(true);setPending(null);setMessage('');}
  async function submit(){
    if(!data)return;
    setBusy(true);setError('');
    try{
      let prepared=pending;
      if(!prepared){
        const result=await api.prepareQuick(props.configId,{trade_date:day,state_hash:data.state_hash,netting,
          selections:rows.filter(r=>r.selected).map(r=>({position_id:r.position_id,quantity:Number(r.quantityInput),price:r.priceInput,fee:r.feeInput||null}))});
        if(!alive.current)return;
        prepared={result,key:createSettlementId()};setPending(prepared);
      }
      const {result,key}=prepared;
      if(result.preview.blocking_errors.length){setError(result.preview.blocking_errors.join('\n'));return;}
      const selected=rows.filter(r=>r.selected);
      const sum=(side:string)=>selected.filter(r=>r.side===side).reduce((a,r)=>a+Number(r.quantityInput),0);
      if(!window.confirm(`${day}\n매도 ${sum('sell')}주 · 매수 ${sum('buy')}주\n증권사 실제 체결: 매도 ${result.actual_sell}주 · 매수 ${result.actual_buy}주\n종가 상계: ${result.offset_quantity}주\n현금 증감 ${money(result.preview.cash_delta)} · 수수료 ${money(result.preview.total_fee)}\n\n실제 체결 내역과 일치하면 반영합니다.`))return;
      await api.confirmSettlement(props.configId,result.record.id,result.preview.preview_hash,key);
      if(!alive.current)return;
      setConfirmed(result.record.id);setPending(null);setDirty(false);setMessage('선택한 체결을 일괄 반영했습니다.');
      props.onCommitted();await reload(false);
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:'반영에 실패했습니다.');}
    finally{if(alive.current)setBusy(false);}
  }
  return <>
    <section className="panel settlement-panel quick-settlement">
      <div className="panel-header"><h2>체결 일괄 반영</h2><button type="button" title="후보 다시 조회" disabled={busy} onClick={()=>void reload()}><RefreshCw size={16}/></button></div>
      {error&&<div className="notice notice-error" role="alert" style={{whiteSpace:'pre-line'}}>{error}</div>}
      {message&&<div className="notice" role="status">{message}</div>}
      <fieldset className="settlement-fields" disabled={busy}>
        <div className="settlement-toolbar">
          <label>거래일<input type="date" value={day} onChange={e=>{
            if(!e.target.value||(dirty&&!window.confirm('수정한 입력을 비우고 거래일을 바꿀까요?')))return;
            setDay(e.target.value);setDirty(false);setPending(null);setMessage('');setConfirmed(null);
          }}/></label>
          <span>확정 종가 <strong>{data?.close?money(data.close):'미확인'}</strong></span>
          <label className="quick-toggle"><input type="checkbox" checked={netting} onChange={e=>{setNetting(e.target.checked);setPending(null);setDirty(true);}}/> 퉁치기 체결</label>
        </div>
        <div className="settlement-scroll"><table className="settlement-table quick-table"><thead><tr>
          <th>선택</th><th>매수일</th><th>구분</th><th>매수가</th><th>주문 기준</th><th>수량</th><th>체결가</th><th>실제 수수료</th><th>판정</th>
        </tr></thead><tbody>{rows.map(row=><tr key={row.position_id}>
          <td><input type="checkbox" aria-label={`포지션 ${row.position_id} 선택`} checked={row.selected} disabled={!row.eligible} onChange={e=>edit(row.position_id,{selected:e.target.checked})}/></td>
          <td>{row.buy_date}</td><td>{row.side==='sell'?'매도':'매수'}</td><td>{money(row.buy_price)}</td>
          <td>{row.reason==='maturity'?'종가':row.limit_price?money(row.limit_price):'-'}</td>
          <td><input aria-label={`포지션 ${row.position_id} 수량`} inputMode="numeric" value={row.quantityInput} onChange={e=>edit(row.position_id,{quantityInput:e.target.value})}/><small className="settlement-position-detail"> / {row.quantity}주</small></td>
          <td><input aria-label={`포지션 ${row.position_id} 체결가`} inputMode="decimal" placeholder="직접 입력" value={row.priceInput} onChange={e=>edit(row.position_id,{priceInput:e.target.value})}/></td>
          <td><input aria-label={`포지션 ${row.position_id} 수수료`} inputMode="decimal" placeholder="자동 계산" value={row.feeInput} onChange={e=>edit(row.position_id,{feeInput:e.target.value})}/></td>
          <td>{reasons[row.reason]}</td>
        </tr>)}</tbody></table></div>
        {!busy&&!rows.length&&<p>반영할 보유 포지션이 없습니다.</p>}
        <div className="settlement-actions">
          <button type="button" disabled={!data||!rows.some(r=>r.selected)||rows.some(r=>r.selected&&(!Number(r.priceInput)||!Number.isInteger(Number(r.quantityInput))||Number(r.quantityInput)<=0))} onClick={()=>void submit()}><Check size={16}/> 선택한 체결 일괄 반영</button>
          {confirmed&&<button type="button" onClick={async()=>{
            if(!window.confirm('방금 반영한 체결 전체를 취소할까요?'))return;
            setBusy(true);setError('');try{await api.cancelSettlement(props.configId,confirmed);if(!alive.current)return;
              setConfirmed(null);setDirty(false);setMessage('일괄 반영을 취소했습니다.');props.onCommitted();await reload(false);
            }catch(e){if(alive.current)setError(e instanceof Error?e.message:'취소에 실패했습니다.');}finally{if(alive.current)setBusy(false);}
          }}><Undo2 size={16}/> 방금 반영 취소</button>}
        </div>
      </fieldset>
    </section>
    <details className="settlement-advanced" onToggle={e=>setDetail(e.currentTarget.open)}><summary>상세 정산 / 저장 내역</summary>
      {detail&&<TradeSettlementPanel {...props} onDirtyChange={setDetailDirty} onCommitted={()=>{props.onCommitted();void reload();}}/>}
    </details>
  </>;
}
