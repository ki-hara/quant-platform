import { Download, Play } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import {
  createBacktest,
  getBacktestDailyCsv,
  getBacktestDailyCsvUrl,
  getBacktestSummaryCsvUrl,
  getBacktestTradesCsv,
  getBacktestTradesCsvUrl,
} from "../api/backtests";
import { listStrategyConfigs } from "../api/strategies";
import { BacktestChart } from "../components/BacktestChart";
import { MetricStrip } from "../components/MetricStrip";
import { Table, type TableColumn } from "../components/Table";
import type { BacktestDailySnapshot, BacktestRun, BacktestTrade, StrategyConfig } from "../types/api";
import { formatMoney, formatPercent, todayIso, translateReason, translateSide } from "../utils/format";

export function BacktestPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [configId, setConfigId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState(todayIso());
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
        setConfigId(rows[0]?.id ?? null);
      } catch (caught) {
        setError(errorMessage(caught));
      }
    }
    loadConfigs();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configId) return;
    try {
      setLoading(true);
      setError("");
      const created = await createBacktest({ config_id: configId, start_date: startDate, end_date: endDate });
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

  const metrics = [
    { label: "초기 자본", value: formatMoney(run?.initial_capital), helper: "시작" },
    { label: "최종 자본", value: formatMoney(run?.final_capital), helper: "종료" },
    { label: "총수익률", value: formatPercent(run?.total_return), helper: "총 수익률" },
    { label: "MDD", value: formatPercent(run?.max_drawdown), helper: "최대 낙폭", tone: "negative" as const },
    { label: "승률", value: formatPercent(run?.win_rate), helper: "청산 거래 기준" },
    { label: "거래 수", value: String(run?.total_trades ?? "-"), helper: "총 체결" },
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
            <select value={configId ?? ""} onChange={(event) => setConfigId(Number(event.target.value) || null)}>
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
          <button type="submit" disabled={!configId || loading}>
            <Play aria-hidden="true" size={16} />
            {loading ? "실행 중" : "백테스트 실행"}
          </button>
        </form>
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
            <span>백테스트 체결 결과</span>
          </div>
        </div>
        <Table columns={backtestTradeColumns} rows={tradeRows} getRowKey={(row, index) => `${row.date}-${index}`} />
      </section>
    </div>
  );
}

function CsvLink({ href, label, disabled }: { href?: string; label: string; disabled: boolean }) {
  if (disabled || !href) {
    return (
      <button className="button-link" type="button" disabled>
        <Download aria-hidden="true" size={16} />
        {label}
      </button>
    );
  }

  return (
    <a className="button-link" href={href}>
      <Download aria-hidden="true" size={16} />
      {label}
    </a>
  );
}

const backtestTradeColumns: TableColumn<BacktestTrade>[] = [
  { key: "date", header: "일자", render: (row) => row.date },
  { key: "side", header: "구분", render: (row) => translateSide(row.side) },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "price", header: "가격", align: "right", render: (row) => formatMoney(row.price) },
  { key: "fee", header: "수수료", align: "right", render: (row) => formatMoney(row.fee) },
  { key: "pnl", header: "실현 손익", align: "right", render: (row) => formatMoney(row.realized_pnl) },
  { key: "reason", header: "사유", render: (row) => translateReason(row.sell_reason) },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
