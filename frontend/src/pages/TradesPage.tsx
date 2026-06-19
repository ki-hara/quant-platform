import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { listStrategyConfigs } from "../api/strategies";
import { listPositions, listTrades } from "../api/trades";
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

export function TradesPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadConfigs() {
      try {
        const rows = await listStrategyConfigs();
        setConfigs(rows);
        setSelectedId(rows[0]?.id ?? null);
      } catch (caught) {
        setError(errorMessage(caught));
      }
    }
    loadConfigs();
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

  return (
    <div className="page-stack">
      <section className="toolbar">
        <label>
          전략 설정
          <select value={selectedId ?? ""} onChange={(event) => setSelectedId(Number(event.target.value) || null)}>
            {configs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.name} / {config.symbol}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => loadRows()} disabled={!selectedId || loading}>
          <RefreshCw aria-hidden="true" size={16} />
          새로고침
        </button>
      </section>

      {loading ? <div className="notice">불러오는 중</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}

      <div className="page-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>보유 포지션</h2>
              <span>전략 설정 기준</span>
            </div>
          </div>
          <Table columns={positionColumns} rows={positions} getRowKey={(row) => row.id} />
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>거래 수정</h2>
              <span>수동 보정</span>
            </div>
          </div>
          <form className="form-stack">
            <label>
              거래일
              <input type="date" defaultValue={todayIso()} disabled />
            </label>
            <label>
              구분
              <select disabled>
                <option>매수</option>
                <option>매도</option>
              </select>
            </label>
            <label>
              수량
              <input placeholder="0" disabled />
            </label>
            <label>
              가격
              <input placeholder="0" disabled />
            </label>
            <button type="button" disabled>
              수정
            </button>
            <p className="form-status">수동 거래 보정 API 지원이 아직 없어 제출은 비활성화되어 있습니다.</p>
          </form>
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>거래내역</h2>
            <span>체결 이력</span>
          </div>
        </div>
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
  { key: "fee", header: "수수료", align: "right", render: (row) => formatMoney(row.buy_fee) },
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
