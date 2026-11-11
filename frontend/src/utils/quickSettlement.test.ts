import { describe, it, expect } from 'vitest';
import { mergeCandidates } from './quickSettlement';

const candidate = {position_id:1,source_id:'sell:1',side:'sell' as const,buy_date:'2026-09-21',buy_price:'80',quantity:7,limit_price:'90',price:'100',selected:true,eligible:true,reason:'profit'};
describe('quick settlement inputs',()=>{
  it('automatically populates closing price and quantity',()=>{
    const [row]=mergeCandidates([candidate],[]);
    expect(row.priceInput).toBe('100');
    expect(row.quantityInput).toBe('7');
    expect(row.selected).toBe(true);
  });
  it('refresh does not overwrite manually edited price quantity or selection',()=>{
    const [row]=mergeCandidates([candidate],[]);
    const [updated]=mergeCandidates([{...candidate,price:'105'}],[{...row,priceInput:'99.5',quantityInput:'3',selected:false,touched:{priceInput:true,quantityInput:true,selected:true}}]);
    expect([updated.priceInput,updated.quantityInput,updated.selected]).toEqual(['99.5','3',false]);
  });
  it('missing close stays blank and unselected',()=>{
    const [row]=mergeCandidates([{...candidate,price:null,selected:false}],[]);
    expect(row.priceInput).toBe('');
    expect(row.selected).toBe(false);
  });
  it('adopts the confirmed close and selection when only quantity was edited',()=>{
    const [row]=mergeCandidates([{...candidate,price:null,selected:false}],[]);
    const [updated]=mergeCandidates([{...candidate,price:'56.06'}],[{...row,quantityInput:'2',touched:{quantityInput:true}}]);
    expect([updated.priceInput,updated.quantityInput,updated.selected]).toEqual(['56.06','2',true]);
    expect(mergeCandidates([], [updated])).toEqual([]);
  });
});
