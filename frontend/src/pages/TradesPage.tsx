import { RefreshCw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { listStrategyConfigs } from "../api/strategies";
import { listPositions, listTrades, recordManualTrade } from "../api/trades";
import { Table, type TableColumn } from "../components/Table";
import type { PositionRow, StrategyConfig, TradeRow } from "../types/api";
import {
  formatMoney,
  todayIso,
  translateMode,
  translateReason,
  translateSide,
  translateSource,
  translateStatus,
} from "../utils/format";

const initialManualForm = {
  trade_date: todayIso(),
  side: "buy" as "buy" | "sell",
  quantity: "",
  price: "",
  fee: "0",
  source: "manual" as "manual" | "correction",
  position_id: "",
  sell_reason: "",
};

export function TradesPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [manualForm, setManualForm] = useState(initialManualForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const openPositions = useMemo(
    () => positions.filter((position) => position.status.toLowerCase() === "open"),
    [positions],
  );

  useEffect(() => {
    listStrategyConfigs()
      .then((rows) => {
        setConfigs(rows);
        setSelectedId(rows[0]?.id ?? null);
      })
      .catch((caught) => setError(errorMessage(caught)));
  }, []);

  useEffect(() => {
    if (selectedId) void loadRows(selectedId);
  }, [selectedId]);

  async function loadRows(configId = selectedId) {
    if (!configId) return;
    try {
      setLoading(true);
      setError("");
      const [positionRows, tradeRows] = await Promise.all([listPositions(configId), listTrades(configId)]);
      setPositions(positionRows);
      setTrades(tradeRows);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function handleManualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId) return;
    if (manualForm.side === "sell" && !manualForm.position_id) {
      setError("매도할 열린 포지션을 선택해 주세요.");
      return;
    }
    try {
      setSaving(true);
      setError("");
      setMessage("");
      await recordManualTrade({
        config_id: selectedId,
        trade_date: manualForm.trade_date,
        side: manualForm.side,
        quantity: manualForm.quantity,
        price: manualForm.price,
        fee: manualForm.fee,
        sell_reason: manualForm.sell_reason.trim() || null,
        source: manualForm.source,
        position_id: manualForm.side === "sell" ? Number(manualForm.position_id) : null,
      });
      setMessage("수동 거래가 저장되었습니다.");
      setManualForm({ ...initialManualForm, trade_date: todayIso() });
      await loadRows(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="toolbar">
        <label>
          전략 설정
          <select value={selectedId ?? ""} onChange={(event) => setSelectedId(Number(event.target.value) || null)}>
            {configs.map((config) => (
              <option key={config.id} value={config.id}>{config.name} / {config.symbol}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => loadRows()} disabled={!selectedId || loading}>
          <RefreshCw aria-hidden="true" size={16} /> 새로고침
        </button>
      </section>

      {loading ? <div className="notice">불러오는 중</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice notice-success">{message}</div> : null}

      <div className="page-grid">
        <section className="panel">
          <div className="panel-header"><div><h2>보유 포지션</h2><span>선택한 전략 기준</span></div></div>
          <Table columns={positionColumns} rows={positions} getRowKey={(row) => row.id} />
        </section>

        <section className="panel">
          <div className="panel-header"><div><h2>거래 수정</h2><span>실제 체결 내역 수동 반영</span></div></div>
          <form className="form-stack" onSubmit={handleManualSubmit}>
            <label>
              거래일
              <input type="date" value={manualForm.trade_date} onChange={(event) =>
                setManualForm((current) => ({ ...current, trade_date: event.target.value }))} required />
            </label>
            <label>
              구분
              <select value={manualForm.side} onChange={(event) =>
                setManualForm((current) => ({
                  ...current,
                  side: event.target.value as "buy" | "sell",
                  position_id: "",
                }))}>
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </label>
            <label>
              출처
              <select value={manualForm.source} onChange={(event) =>
                setManualForm((current) => ({ ...current, source: event.target.value as "manual" | "correction" }))}>
                <option value="manual">수동 입력</option>
                <option value="correction">체결 보정</option>
              </select>
            </label>
            {manualForm.side === "sell" ? (
              <label>
                매도할 포지션
                <select
                  value={manualForm.position_id}
                  onChange={(event) => setManualForm((current) => ({ ...current, position_id: event.target.value }))}
                  required
                >
                  <option value="">포지션 선택</option>
                  {openPositions.map((position) => (
                    <option key={position.id} value={position.id}>
                      #{position.id} / {position.buy_date} / {formatMoney(position.quantity)}주 / {formatMoney(position.buy_price)}원
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              수량
              <input value={manualForm.quantity} onChange={(event) =>
                setManualForm((current) => ({ ...current, quantity: event.target.value }))}
                placeholder="0" inputMode="decimal" required />
            </label>
            <label>
              체결 가격
              <input value={manualForm.price} onChange={(event) =>
                setManualForm((current) => ({ ...current, price: event.target.value }))}
                placeholder="0" inputMode="decimal" required />
            </label>
            <label>
              수수료
              <input value={manualForm.fee} onChange={(event) =>
                setManualForm((current) => ({ ...current, fee: event.target.value }))}
                placeholder="0" inputMode="decimal" required />
            </label>
            {manualForm.side === "sell" ? (
              <label>
                매도 사유
                <input value={manualForm.sell_reason} onChange={(event) =>
                  setManualForm((current) => ({ ...current, sell_reason: event.target.value }))}
                  placeholder="예: 증권사 체결 보정" />
              </label>
            ) : null}
            <button type="submit" disabled={!selectedId || saving}>
              <Save aria-hidden="true" size={16} /> {saving ? "저장 중" : "거래 저장"}
            </button>
            <p className="form-status">부분 매도 시 남은 수량과 매수 수수료가 비례 조정됩니다.</p>
          </form>
        </section>
      </div>

      <section className="panel">
        <div className="panel-header"><div><h2>거래내역</h2><span>체결 이력</span></div></div>
        <Table columns={tradeColumns} rows={trades} getRowKey={(row) => row.id} />
      </section>
    </div>
  );
}

const positionColumns: TableColumn<PositionRow>[] = [
  { key: "id", header: "ID", render: (row) => row.id },
  { key: "buy_date", header: "매수일", render: (row) => row.buy_date },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "매수가", align: "right", render: (row) => formatMoney(row.buy_price) },
  { key: "fee", header: "매수 수수료", align: "right", render: (row) => formatMoney(row.buy_fee) },
  { key: "mode", header: "모드", render: (row) => translateMode(row.mode) },
  { key: "status", header: "상태", render: (row) => translateStatus(row.status) },
];

const tradeColumns: TableColumn<TradeRow>[] = [
  { key: "date", header: "일자", render: (row) => row.date },
  { key: "side", header: "구분", render: (row) => translateSide(row.side) },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "가격", align: "right", render: (row) => formatMoney(row.price) },
  { key: "fee", header: "수수료", align: "right", render: (row) => formatMoney(row.fee) },
  { key: "pnl", header: "실현 손익", align: "right", render: (row) => formatMoney(row.realized_pnl) },
  { key: "reason", header: "사유", render: (row) => translateReason(row.sell_reason) },
  { key: "source", header: "출처", render: (row) => translateSource(row.source) },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
