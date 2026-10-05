import { describe, it, expect } from "vitest";
import { proposeAllocations, createSettlementId } from "./settlementDraft";

describe("settlement proposal", () => {
  it("creates identifiers without secure-context randomUUID", () => {
    expect(createSettlementId()).not.toBe(createSettlementId());
    expect(createSettlementId()).toMatch(/^[0-9a-f]{32}$/);
  });
  const sources = [
    {id:"s", side:"sell" as const, quantity:20, position_id:1, limit_price:"90", execution:"loc"},
    {id:"b", side:"buy" as const, quantity:12, position_id:null, limit_price:"120", execution:"loc"},
  ];
  it("matches actual net fills and offsets without confirming", () => {
    const rows = proposeAllocations(sources, [{id:"f", side:"sell", quantity:"8", price:"110", fee:"0.8"}], "100");
    expect(rows.filter(r => r.kind === "offset").map(r => r.quantity)).toEqual([12,12]);
    expect(rows.find(r => r.kind === "actual")?.quantity).toBe(8);
  });
  it("does not guess mismatched broker quantity", () => {
    expect(proposeAllocations(sources, [{id:"f", side:"sell", quantity:"7", price:"110", fee:"0"}], "100")).toEqual([]);
  });
  it("does not fabricate close or fill price", () => {
    expect(proposeAllocations(sources, [], null)).toEqual([]);
    expect(proposeAllocations(sources, [{id:"f", side:"sell", quantity:"8", price:"", fee:"0"}], "100")).toEqual([]);
  });
});
