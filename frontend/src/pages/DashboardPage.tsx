import { Download, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getSqliteBackupUrl } from "../api/admin";
import { getDashboard } from "../api/dashboard";
import { listStrategyConfigs } from "../api/strategies";
import { listTrades } from "../api/trades";
import {
  getChart,
  getDailyPlan,
  getModeRecommendation,
  refreshMarketData,
  setConfirmedMode,
} from "../api/tradingPlan";
import { DailyPlanPanel } from "../components/DailyPlanPanel";
import { MarketChart } from "../components/MarketChart";
import { MetricStrip } from "../components/MetricStrip";
import { ModeControl } from "../components/ModeControl";
import { RsiChart } from "../components/RsiChart";
import { Table, type TableColumn } from "../components/Table";
import type {
  ChartRange,
  DailyPlan,
  CapitalUpdateStatus,
  DashboardResponse,
  ModeRecommendation,
  PositionRow,
  StrategyConfig,
  StrategyMode,
  TradeRow,
  TradingChart,
} from "../types/api";
import {
  formatMoney,
  translateMode,
  translateReason,
  translateSide,
  translateSource,
  translateStatus,
} from "../utils/format";
import { rememberStrategyConfigId, resolveRememberedStrategyConfigId } from "../utils/strategySelection";

export function DashboardPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [mode, setMode] = useState<ModeRecommendation | null>(null);
  const [chart, setChart] = useState<TradingChart | null>(null);
  const [recentTrades, setRecentTrades] = useState<TradeRow[]>([]);
  const [range, setRange] = useState<ChartRange>("1m");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
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
        setSelectedId((current) => current ?? resolveRememberedStrategyConfigId(rows));
      } catch (caught) {
        if (active) setError(errorMessage(caught));
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadConfigs();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    void loadOperationalData(selectedId, range);
  }, [selectedId, range]);

  async function loadOperationalData(configId = selectedId, chartRange = range) {
    if (!configId) return;
    try {
      setLoading(true);
      setError("");
      const [dashboardData, planData, modeData, chartData, trades] = await Promise.all([
        getDashboard(configId),
        getDailyPlan(configId),
        getModeRecommendation(configId),
        getChart(configId, chartRange),
        listTrades(configId),
      ]);
      setDashboard(dashboardData);
      setPlan(planData);
      setMode(modeData);
      setChart(chartData);
      setRecentTrades(trades.slice(0, 8));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    if (!selectedId) return;
    try {
      setWorking(true);
      setMessage("");
      setError("");
      const result = await refreshMarketData(selectedId);
      setMessage(
        `시장 데이터 갱신 완료: 투자종목 ${result.investment_data_as_of ?? "-"}, RSI ${result.rsi_data_as_of ?? "-"}`,
      );
      await loadOperationalData(selectedId, range);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function handleSetMode(nextMode: StrategyMode) {
    if (!selectedId) return;
    try {
      setWorking(true);
      setMessage("");
      setError("");
      const next = await setConfirmedMode(selectedId, { action: "set", mode: nextMode });
      setMode(next);
      await loadOperationalData(selectedId, range);
      setMessage(`${translateMode(nextMode)} 모드로 확정했습니다.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function handleApplyRecommendation() {
    if (!selectedId) return;
    try {
      setWorking(true);
      setMessage("");
      setError("");
      const next = await setConfirmedMode(selectedId, { action: "apply_recommendation" });
      setMode(next);
      await loadOperationalData(selectedId, range);
      setMessage("추천 모드를 확정 모드로 적용했습니다.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  const metrics = useMemo(() => {
    const portfolio = dashboard?.portfolio;
    const symbol = dashboard?.config.symbol;
    return [
      { label: "총 평가금액", value: formatMoney(dashboard?.total_asset, symbol), helper: dashboard?.config.symbol },
      { label: "Capital", value: formatMoney(portfolio?.capital, symbol), helper: "전략 기준 투자금" },
      { label: "Cash", value: formatMoney(portfolio?.cash, symbol), helper: "매수 가능 현금" },
      { label: "실현손익", value: formatMoney(portfolio?.realized_pnl, symbol), helper: "누적 기준" },
      { label: "누적 수수료", value: formatMoney(portfolio?.cumulative_fees, symbol), helper: "매수/매도 반영" },
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
            onChange={(event) => {
              const nextId = Number(event.target.value) || null;
              rememberStrategyConfigId(nextId);
              setSelectedId(nextId);
            }}
          >
            {configs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.name} / {config.symbol}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={handleRefresh} disabled={!selectedId || loading || working}>
          <RefreshCw aria-hidden="true" size={16} />
          시장 데이터 갱신
        </button>
        <a className="button-link" href={getSqliteBackupUrl()}>
          <Download aria-hidden="true" size={16} />
          DB 백업
        </a>
      </section>

      {loading ? <div className="notice">불러오는 중입니다.</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice notice-success">{message}</div> : null}
      {!loading && configs.length === 0 ? <div className="empty-state">전략 설정 데이터 없음</div> : null}

      <MetricStrip metrics={metrics} />

      <div className="dashboard-top-grid">
        <DailyPlanPanel plan={plan} />
        <ModeControl
          mode={mode}
          loading={working}
          onSetMode={handleSetMode}
          onApplyRecommendation={handleApplyRecommendation}
        />
        <CapitalUpdatePanel status={dashboard?.capital_update ?? null} symbol={dashboard?.config.symbol} />
      </div>

      <MarketChart chart={chart} range={range} onRangeChange={setRange} />
      <RsiChart chart={chart} />

      <div className="page-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>보유 포지션</h2>
              <span>현재 미청산 포지션</span>
            </div>
          </div>
          <Table columns={positionColumns} rows={dashboard?.open_positions ?? []} getRowKey={(row) => row.id} />
        </section>

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
    </div>
  );
}

function CapitalUpdatePanel({
  status,
  symbol,
}: {
  status: CapitalUpdateStatus | null;
  symbol?: string | null;
}) {
  const tone = status?.applied ? "is-ok" : status?.status === "waiting" ? "is-muted" : "is-blocked";
  const title = status?.applied ? "자동 갱신됨" : status?.status === "waiting" ? "대기" : "확인 필요";
  return (
    <section className="panel capital-update-panel">
      <div className="panel-header">
        <div>
          <h2>Capital 갱신</h2>
          <span>{status?.message ?? "거래 기록 기준 자동 갱신"}</span>
        </div>
        <span className={`status-pill compact ${tone}`}>{title}</span>
      </div>

      <dl className="detail-grid">
        <div>
          <dt>경과 거래일</dt>
          <dd>{status ? `${status.elapsed_trading_days} / ${status.interval}` : "-"}</dd>
        </div>
        <div>
          <dt>다음 갱신일</dt>
          <dd>{status?.next_update_date ?? (status?.applied ? "계산 대기" : "-")}</dd>
        </div>
        <div>
          <dt>반영 기간</dt>
          <dd>
            {status?.period_start_date && status?.period_end_date
              ? `${status.period_start_date} ~ ${status.period_end_date}`
              : "-"}
          </dd>
        </div>
        <div>
          <dt>누적 실현손익</dt>
          <dd className={signedValueClass(status?.realized_pnl)}>{formatMoney(status?.realized_pnl, symbol)}</dd>
        </div>
        <div>
          <dt>Capital 변화</dt>
          <dd className={signedValueClass(status?.capital_delta)}>{formatMoney(status?.capital_delta, symbol)}</dd>
        </div>
        <div>
          <dt>예상 Capital</dt>
          <dd>{formatMoney(status?.projected_capital, symbol)}</dd>
        </div>
      </dl>
    </section>
  );
}

function signedValueClass(value: string | number | null | undefined): string | undefined {
  const number = Number(value ?? 0);
  if (number > 0) return "value-positive";
  if (number < 0) return "value-negative";
  return undefined;
}

const positionColumns: TableColumn<PositionRow>[] = [
  { key: "id", header: "ID", render: (row) => row.id },
  { key: "buy_date", header: "매수일", render: (row) => row.buy_date },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "매수가", align: "right", render: (row) => formatMoney(row.buy_price) },
  { key: "mode", header: "모드", render: (row) => translateMode(row.mode) },
  { key: "status", header: "상태", render: (row) => translateStatus(row.status) },
];

const tradeColumns: TableColumn<TradeRow>[] = [
  { key: "date", header: "일자", render: (row) => row.date },
  { key: "side", header: "구분", render: (row) => translateSide(row.side) },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "가격", align: "right", render: (row) => formatMoney(row.price) },
  { key: "pnl", header: "실현손익", align: "right", render: (row) => formatMoney(row.realized_pnl) },
  { key: "reason", header: "사유", render: (row) => translateReason(row.sell_reason) },
  { key: "source", header: "출처", render: (row) => translateSource(row.source) },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
