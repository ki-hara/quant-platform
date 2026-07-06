import { Download, Play } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createBacktest,
  getBacktestDailyCsv,
  getBacktestDailyCsvUrl,
  getBacktestSummaryCsvUrl,
  getBacktestTradesCsv,
  getBacktestTradesCsvUrl,
} from "../api/backtests";
import { listStrategyConfigs } from "../api/strategies";
import { apiDownload } from "../api/client";
import { BacktestChart } from "../components/BacktestChart";
import { MetricStrip } from "../components/MetricStrip";
import { Table, type TableColumn } from "../components/Table";
import type { BacktestDailySnapshot, BacktestRun, BacktestTrade, StrategyConfig } from "../types/api";
import { formatMoney, formatPercent, todayIso, translateMode, translateReason, translateSide } from "../utils/format";
import { rememberStrategyConfigId, resolveRememberedStrategyConfigId } from "../utils/strategySelection";

type BacktestModePolicy = "fixed_safe" | "fixed_aggressive" | "weekly_rsi";
type BacktestPositionSizingPolicy = "fixed_quantity" | "full_allocation";
type TradeFilter = "all" | "buy" | "sell";
type ReasonFilter = "all" | "profit_target" | "max_holding_period";

const BACKTEST_PREFERENCES_KEY = "quant-platform:backtest-preferences";

export function BacktestPage() {
  const preferences = useMemo(loadBacktestPreferences, []);
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [configId, setConfigId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState(preferences.startDate);
  const [endDate, setEndDate] = useState(preferences.endDate);
  const [modePolicy, setModePolicy] = useState<BacktestModePolicy>(preferences.modePolicy);
  const [positionSizingPolicy, setPositionSizingPolicy] = useState<BacktestPositionSizingPolicy>(preferences.positionSizingPolicy);
  const [sideFilter, setSideFilter] = useState<TradeFilter>("all");
  const [reasonFilter, setReasonFilter] = useState<ReasonFilter>("all");
  const [run, setRun] = useState<BacktestRun | null>(null);
  const [dailyRows, setDailyRows] = useState<BacktestDailySnapshot[]>([]);
  const [tradeRows, setTradeRows] = useState<BacktestTrade[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadConfigs() {
      try {
        const rows = await listStrategyConfigs();
        setConfigs(rows);
        setConfigId(resolveRememberedStrategyConfigId(rows));
      } catch (caught) {
        setError(errorMessage(caught));
      }
    }
    loadConfigs();
  }, []);

  useEffect(() => {
    saveBacktestPreferences({
      startDate,
      endDate,
      modePolicy,
      positionSizingPolicy,
    });
  }, [endDate, modePolicy, positionSizingPolicy, startDate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configId) return;
    try {
      setLoading(true);
      setError("");
      const created = await createBacktest({
        config_id: configId,
        start_date: startDate,
        end_date: endDate,
        mode_policy: modePolicy,
        position_sizing_policy: positionSizingPolicy,
      });
      setRun(created);
      const [daily, trades] = await Promise.all([
        getBacktestDailyCsv(created.id),
        getBacktestTradesCsv(created.id),
      ]);
      setDailyRows(daily);
      setTradeRows(trades);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  const selectedConfig = configs.find((config) => config.id === configId) ?? null;
  const summary = useMemo(() => buildBacktestSummary(tradeRows, dailyRows), [dailyRows, tradeRows]);
  const filteredTrades = useMemo(
    () =>
      tradeRows.filter((row) => {
        const sideMatches = sideFilter === "all" || row.side.toLowerCase() === sideFilter;
        const reasonMatches = reasonFilter === "all" || row.sell_reason === reasonFilter;
        return sideMatches && reasonMatches;
      }),
    [reasonFilter, sideFilter, tradeRows],
  );
  const snapshot = run?.strategy_config_snapshot_json;
  const snapshotSettings = snapshot?.settings_json as Record<string, unknown> | undefined;

  const metrics = [
    { label: "초기 자본", value: formatMoney(run?.initial_capital), helper: "시작" },
    { label: "최종 자본", value: formatMoney(run?.final_capital), helper: "종료" },
    { label: "총수익률", value: formatPercent(run?.total_return), helper: "총 수익률" },
    { label: "MDD", value: formatPercent(run?.max_drawdown), helper: "최대 낙폭", tone: "negative" as const },
    { label: "승률", value: formatPercent(run?.win_rate), helper: "청산 거래 기준" },
    { label: "거래 수", value: String(run?.total_trades ?? "-"), helper: "총 체결" },
    { label: "평균 보유", value: summary.averageHoldingDays, helper: "매도 거래 기준" },
    { label: "누적 수수료", value: formatMoney(summary.cumulativeFees, selectedConfig?.symbol), helper: "거래 비용" },
    { label: "매수 / 매도", value: `${summary.buyCount} / ${summary.sellCount}`, helper: "체결 방향" },
    { label: "수익 / 손실", value: `${summary.winSellCount} / ${summary.lossSellCount}`, helper: "매도 손익" },
    { label: "최대 연속 손실", value: String(summary.maxConsecutiveLosses), helper: "매도 거래 기준", tone: summary.maxConsecutiveLosses > 0 ? "warning" as const : "neutral" as const },
    { label: "현재 낙폭", value: formatPercent(summary.currentDrawdown), helper: "마지막 거래일 기준", tone: Number(summary.currentDrawdown) < 0 ? "negative" as const : "neutral" as const },
  ];

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>백테스트 실행</h2>
            <span>전략 설정과 검증 기간을 선택하세요.</span>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            전략 설정
            <select
              value={configId ?? ""}
              onChange={(event) => {
                const nextId = Number(event.target.value) || null;
                rememberStrategyConfigId(nextId);
                setConfigId(nextId);
              }}
            >
              {configs.map((config) => (
                <option key={config.id} value={config.id}>
                  {config.name} / {config.symbol}
                </option>
              ))}
            </select>
          </label>
          <label>
            시작일
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required />
          </label>
          <label>
            종료일
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} required />
          </label>
          <label>
            모드 정책
            <select value={modePolicy} onChange={(event) => setModePolicy(event.target.value as BacktestModePolicy)}>
              <option value="fixed_safe">안전모드 고정</option>
              <option value="fixed_aggressive">공세모드 고정</option>
              <option value="weekly_rsi">주간 RSI 추천</option>
            </select>
          </label>
          <label>
            매수 수량 계산
            <select
              value={positionSizingPolicy}
              onChange={(event) => setPositionSizingPolicy(event.target.value as BacktestPositionSizingPolicy)}
            >
              <option value="fixed_quantity">정량매수</option>
              <option value="full_allocation">정액매수</option>
            </select>
          </label>
          <button type="submit" disabled={!configId || loading}>
            <Play aria-hidden="true" size={16} />
            {loading ? "실행 중" : "백테스트 실행"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>실행 설정</h2>
            <span>{run ? "백테스트 당시 설정 스냅샷" : "백테스트 실행 후 표시됩니다."}</span>
          </div>
        </div>
        {run ? (
          <div className="backtest-snapshot-grid">
            <SnapshotBlock
              title="기본"
              rows={[
                ["전략", textValue(snapshot?.name)],
                ["종목", textValue(snapshot?.symbol)],
                ["기간", `${run.start_date} - ${run.end_date}`],
                ["모드 정책", modePolicyLabel(textValue(snapshot?.mode_policy))],
                ["매수 수량 계산", positionSizingPolicyLabel(textValue(snapshot?.position_sizing_policy))],
                ["초기 투자금", formatMoney(snapshot?.initial_capital as string | undefined, textValue(snapshot?.symbol))],
                ["수수료율", `${textValue(snapshot?.fee_rate)}%`],
              ]}
            />
            <SnapshotBlock title="안전모드" rows={modeSettingRows(snapshotSettings?.safe)} />
            <SnapshotBlock title="공세모드" rows={modeSettingRows(snapshotSettings?.aggressive)} />
            <SnapshotBlock
              title="투자금 갱신"
              rows={[
                ["갱신 간격", `${nestedValue(snapshotSettings?.capital_update, "interval")}거래일`],
                ["이익복리율", `${textValue(snapshotSettings?.profit_compounding_rate)}%`],
                ["손실복리율", `${textValue(snapshotSettings?.loss_compounding_rate)}%`],
              ]}
            />
          </div>
        ) : (
          <div className="empty-state">실행된 백테스트가 없습니다.</div>
        )}
      </section>

      {error ? <div className="notice notice-error">{error}</div> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>성과 지표</h2>
            <span>{run ? `실행 ID ${run.id}` : "최근 실행 없음"}</span>
          </div>
        </div>
        <MetricStrip metrics={metrics} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>자산 곡선 / 낙폭</h2>
            <span>총자산과 낙폭 시계열</span>
          </div>
        </div>
        <BacktestChart rows={dailyRows} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>CSV 다운로드</h2>
            <span>일별/거래/요약</span>
          </div>
        </div>
        <div className="button-row">
          <CsvLink disabled={!run} href={run ? getBacktestDailyCsvUrl(run.id) : undefined} label="일별 CSV 다운로드" />
          <CsvLink disabled={!run} href={run ? getBacktestTradesCsvUrl(run.id) : undefined} label="거래 CSV 다운로드" />
          <CsvLink disabled={!run} href={run ? getBacktestSummaryCsvUrl(run.id) : undefined} label="요약 CSV 다운로드" />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>거래내역</h2>
            <span>백테스트 체결 결과 {filteredTrades.length}건 / 전체 {tradeRows.length}건</span>
          </div>
        </div>
        <div className="filter-row">
          <label>
            구분
            <select value={sideFilter} onChange={(event) => setSideFilter(event.target.value as TradeFilter)}>
              <option value="all">전체</option>
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
          </label>
          <label>
            매도 사유
            <select value={reasonFilter} onChange={(event) => setReasonFilter(event.target.value as ReasonFilter)}>
              <option value="all">전체</option>
              <option value="profit_target">목표 수익</option>
              <option value="max_holding_period">최대 보유 거래일</option>
            </select>
          </label>
        </div>
        <GroupedBacktestTrades
          columns={backtestTradeColumns(selectedConfig?.symbol)}
          dailyRows={dailyRows}
          rows={filteredTrades}
          symbol={selectedConfig?.symbol}
        />
      </section>
    </div>
  );
}

function CsvLink({ href, label, disabled }: { href?: string; label: string; disabled: boolean }) {
  async function handleClick() {
    if (!href) return;
    const parts = href.split("/");
    await apiDownload(href, parts[parts.length - 1] ?? "backtest.csv");
  }

  if (disabled || !href) {
    return (
      <button className="button-link" type="button" disabled>
        <Download aria-hidden="true" size={16} />
        {label}
      </button>
    );
  }

  return (
    <button className="button-link" type="button" onClick={handleClick}>
      <Download aria-hidden="true" size={16} />
      {label}
    </button>
  );
}

function SnapshotBlock({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <div className="snapshot-block">
      <h3>{title}</h3>
      <dl className="detail-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function backtestTradeColumns(symbol?: string | null): TableColumn<BacktestTrade>[] {
  return [
    { key: "date", header: "일자", render: (row) => row.date },
    {
      key: "side",
      header: "구분",
      render: (row) => (
        <span className={`state-badge ${row.side.toLowerCase() === "sell" ? "is-warning" : "is-success"}`}>
          {translateSide(row.side)}
        </span>
      ),
    },
    { key: "quantity", header: "수량", align: "right", render: (row) => wholeNumber(row.quantity) },
    { key: "price", header: "가격", align: "right", render: (row) => formatMoney(row.price, symbol) },
    {
      key: "trade_amount",
      header: "거래액",
      align: "right",
      render: (row) => (
        <div className="trade-amount-cell">
          <strong>{formatMoney(tradeAmount(row), symbol)}</strong>
          <small>{row.side.toLowerCase() === "sell" ? "매도금액" : "매수총금액"}</small>
        </div>
      ),
    },
    { key: "holding_days", header: "보유 거래일", align: "right", render: (row) => row.holding_days === null ? "-" : `${row.holding_days}일` },
    { key: "open_position_count", header: "포지션 수", align: "right", render: (row) => row.open_position_count ?? "-" },
    { key: "cash_after", header: "Cash", align: "right", render: (row) => formatMoney(row.cash_after, symbol) },
    { key: "reason", header: "사유", render: (row) => translateReason(row.sell_reason) },
  ];
}

function GroupedBacktestTrades({
  columns,
  dailyRows,
  rows,
  symbol,
}: {
  columns: TableColumn<BacktestTrade>[];
  dailyRows: BacktestDailySnapshot[];
  rows: BacktestTrade[];
  symbol?: string | null;
}) {
  const groups = groupTradesByDate(rows);
  if (groups.length === 0) return <div className="empty-state">표시할 거래내역이 없습니다.</div>;

  return (
    <div className="trade-group-list">
      {groups.map((group) => {
        const realizedPnl = group.rows.reduce((sum, row) => sum + Number(row.realized_pnl || 0), 0);
        const fee = group.rows.reduce((sum, row) => sum + Number(row.fee || 0), 0);
        const last = group.rows[group.rows.length - 1];
        const mode = dailyRows.find((row) => row.date === group.date)?.mode ?? null;
        return (
          <div className="trade-date-group" key={group.date}>
            <div className="trade-date-header">
              <strong>{group.date}</strong>
              <div className="trade-date-summary">
                <span>포지션 {last.open_position_count ?? "-"}</span>
                <span>실현손익 {formatMoney(String(realizedPnl), symbol)}</span>
                <span>Capital {formatMoney(last.capital_after, symbol)}</span>
                <span>수수료 {formatMoney(String(fee), symbol)}</span>
                <span>모드 {translateMode(mode)}</span>
              </div>
            </div>
            <Table columns={columns} rows={group.rows} getRowKey={(row, index) => `${row.date}-${row.side}-${index}`} />
          </div>
        );
      })}
    </div>
  );
}

function groupTradesByDate(rows: BacktestTrade[]): Array<{ date: string; rows: BacktestTrade[] }> {
  const groups: Array<{ date: string; rows: BacktestTrade[] }> = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    if (last?.date === row.date) {
      last.rows.push(row);
    } else {
      groups.push({ date: row.date, rows: [row] });
    }
  }
  return groups;
}

function tradeAmount(row: BacktestTrade): string {
  return String(Number(row.price || 0) * Number(row.quantity || 0));
}

function buildBacktestSummary(trades: BacktestTrade[], dailyRows: BacktestDailySnapshot[]) {
  const sells = trades.filter((row) => row.side.toLowerCase() === "sell");
  const lastDailyRow = dailyRows.length > 0 ? dailyRows[dailyRows.length - 1] : null;
  const holdingDays = sells
    .map((row) => row.holding_days)
    .filter((value): value is number => typeof value === "number");
  let maxConsecutiveLosses = 0;
  let currentLosses = 0;
  for (const trade of sells) {
    if (Number(trade.realized_pnl) < 0) {
      currentLosses += 1;
      maxConsecutiveLosses = Math.max(maxConsecutiveLosses, currentLosses);
    } else {
      currentLosses = 0;
    }
  }
  return {
    buyCount: trades.filter((row) => row.side.toLowerCase() === "buy").length,
    sellCount: sells.length,
    winSellCount: sells.filter((row) => Number(row.realized_pnl) > 0).length,
    lossSellCount: sells.filter((row) => Number(row.realized_pnl) < 0).length,
    maxConsecutiveLosses,
    averageHoldingDays: holdingDays.length
      ? `${(holdingDays.reduce((sum, value) => sum + value, 0) / holdingDays.length).toFixed(1)}일`
      : "-",
    cumulativeFees: lastDailyRow?.cumulative_fees ?? null,
    currentDrawdown: lastDailyRow?.drawdown ?? null,
  };
}

function modePolicyLabel(value: string): string {
  return {
    fixed_safe: "안전모드 고정",
    fixed_aggressive: "공세모드 고정",
    weekly_rsi: "주간 RSI 추천",
  }[value] ?? value;
}

function positionSizingPolicyLabel(value: string): string {
  return {
    fixed_quantity: "정량매수",
    full_allocation: "정액매수",
  }[value] ?? value;
}

function modeSettingRows(value: unknown): Array<[string, string]> {
  return [
    ["분할수", String(nestedValue(value, "split_count"))],
    ["최대 보유", `${nestedValue(value, "max_holding_days")}거래일`],
    ["매수조건", `${nestedValue(value, "buy_threshold_percent")}%`],
    ["매도조건", `${nestedValue(value, "sell_threshold_percent")}%`],
  ];
}

function nestedValue(value: unknown, key: string): string {
  if (!value || typeof value !== "object") return "-";
  const next = (value as Record<string, unknown>)[key];
  return textValue(next);
}

function textValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function wholeNumber(value: string | number | null | undefined): string {
  const number = Math.trunc(Number(value ?? 0));
  return Number.isFinite(number) ? String(number) : "-";
}

function loadBacktestPreferences(): {
  startDate: string;
  endDate: string;
  modePolicy: BacktestModePolicy;
  positionSizingPolicy: BacktestPositionSizingPolicy;
} {
  const defaults = {
    startDate: "2025-01-01",
    endDate: todayIso(),
    modePolicy: "weekly_rsi" as BacktestModePolicy,
    positionSizingPolicy: "fixed_quantity" as BacktestPositionSizingPolicy,
  };
  try {
    const raw = window.localStorage.getItem(BACKTEST_PREFERENCES_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<typeof defaults>;
    return {
      startDate: isDateInputValue(parsed.startDate) ? parsed.startDate : defaults.startDate,
      endDate: isDateInputValue(parsed.endDate) ? parsed.endDate : defaults.endDate,
      modePolicy: isBacktestModePolicy(parsed.modePolicy) ? parsed.modePolicy : defaults.modePolicy,
      positionSizingPolicy: isPositionSizingPolicy(parsed.positionSizingPolicy)
        ? parsed.positionSizingPolicy
        : defaults.positionSizingPolicy,
    };
  } catch {
    return defaults;
  }
}

function saveBacktestPreferences(preferences: {
  startDate: string;
  endDate: string;
  modePolicy: BacktestModePolicy;
  positionSizingPolicy: BacktestPositionSizingPolicy;
}): void {
  window.localStorage.setItem(BACKTEST_PREFERENCES_KEY, JSON.stringify(preferences));
}

function isDateInputValue(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function isBacktestModePolicy(value: unknown): value is BacktestModePolicy {
  return value === "fixed_safe" || value === "fixed_aggressive" || value === "weekly_rsi";
}

function isPositionSizingPolicy(value: unknown): value is BacktestPositionSizingPolicy {
  return value === "fixed_quantity" || value === "full_allocation";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
