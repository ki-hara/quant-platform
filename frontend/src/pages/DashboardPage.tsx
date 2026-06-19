import { RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDashboard } from "../api/dashboard";
import { listStrategyConfigs } from "../api/strategies";
import { listTrades, executeSignal } from "../api/trades";
import { MetricStrip } from "../components/MetricStrip";
import { SignalPanel } from "../components/SignalPanel";
import { Table, type TableColumn } from "../components/Table";
import type {
  DashboardResponse,
  PositionRow,
  SignalExecutionRequest,
  StrategyConfig,
  TradeRow,
} from "../types/api";
import { formatMoney, translateSide, translateStatus } from "../utils/format";

export function DashboardPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [recentTrades, setRecentTrades] = useState<TradeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadConfigs() {
      try {
        setLoading(true);
        const rows = await listStrategyConfigs();
        if (!active) return;
        setConfigs(rows);
        setSelectedId((current) => current ?? rows[0]?.id ?? null);
      } catch (caught) {
        if (active) setError(errorMessage(caught));
      } finally {
        if (active) setLoading(false);
      }
    }
    loadConfigs();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    void loadDashboard(selectedId);
  }, [selectedId]);

  async function loadDashboard(configId = selectedId) {
    if (!configId) return;
    try {
      setLoading(true);
      setError("");
      const [dashboardData, trades] = await Promise.all([getDashboard(configId), listTrades(configId)]);
      setDashboard(dashboardData);
      setRecentTrades(trades.slice(0, 8));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute(request: SignalExecutionRequest) {
    if (!selectedId) return;
    try {
      setExecuting(true);
      setMessage("");
      setError("");
      await executeSignal(selectedId, request);
      setMessage("신호 실행이 저장되었습니다.");
      await loadDashboard(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setExecuting(false);
    }
  }

  const metrics = useMemo(() => {
    const portfolio = dashboard?.portfolio;
    return [
      { label: "총자산", value: formatMoney(dashboard?.total_asset), helper: dashboard?.config.symbol },
      { label: "현금", value: formatMoney(portfolio?.cash), helper: "매수 가능 현금" },
      { label: "실현 손익", value: formatMoney(portfolio?.realized_pnl), helper: "누적 기준" },
      { label: "보유 포지션", value: String(dashboard?.open_positions.length ?? 0), helper: "미청산" },
    ];
  }, [dashboard]);

  return (
    <div className="page-stack">
      <section className="toolbar">
        <label>
          전략 설정
          <select
            value={selectedId ?? ""}
            onChange={(event) => setSelectedId(Number(event.target.value) || null)}
          >
            {configs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.name} / {config.symbol}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => loadDashboard()} disabled={!selectedId || loading}>
          <RefreshCw aria-hidden="true" size={16} />
          새로고침
        </button>
      </section>

      {loading ? <div className="notice">불러오는 중</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice notice-success">{message}</div> : null}
      {!loading && configs.length === 0 ? <div className="empty-state">전략 설정 데이터 없음</div> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>계좌 요약</h2>
            <span>{dashboard?.latest_price ? `최근 종가 ${formatMoney(dashboard.latest_price.close)}` : "시장 데이터 대기"}</span>
          </div>
        </div>
        <MetricStrip metrics={metrics} />
      </section>

      <div className="page-grid">
        <SignalPanel dashboard={dashboard} onExecute={handleExecute} executing={executing} />
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>보유 포지션</h2>
              <span>현재 미청산 포지션</span>
            </div>
          </div>
          <Table columns={positionColumns} rows={dashboard?.open_positions ?? []} getRowKey={(row) => row.id} />
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>최근 거래내역</h2>
            <span>최대 8건</span>
          </div>
        </div>
        <Table columns={tradeColumns} rows={recentTrades} getRowKey={(row) => row.id} />
      </section>
    </div>
  );
}

const positionColumns: TableColumn<PositionRow>[] = [
  { key: "id", header: "ID", render: (row) => row.id },
  { key: "buy_date", header: "매수일", render: (row) => row.buy_date },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "매수가", align: "right", render: (row) => formatMoney(row.buy_price) },
  { key: "mode", header: "모드", render: (row) => row.mode },
  { key: "status", header: "상태", render: (row) => translateStatus(row.status) },
];

const tradeColumns: TableColumn<TradeRow>[] = [
  { key: "date", header: "일자", render: (row) => row.date },
  { key: "side", header: "구분", render: (row) => translateSide(row.side) },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "가격", align: "right", render: (row) => formatMoney(row.price) },
  { key: "pnl", header: "실현 손익", align: "right", render: (row) => formatMoney(row.realized_pnl) },
  { key: "source", header: "출처", render: (row) => row.source },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
