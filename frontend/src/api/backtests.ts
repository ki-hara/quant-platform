import { apiGet, apiGetText, apiPost } from "./client";
import type {
  BacktestCreateRequest,
  BacktestDailySnapshot,
  BacktestRun,
  BacktestTrade,
} from "../types/api";

export function createBacktest(request: BacktestCreateRequest): Promise<BacktestRun> {
  return apiPost<BacktestRun>("/api/backtests", request);
}

export function getBacktest(runId: number): Promise<BacktestRun> {
  return apiGet<BacktestRun>(`/api/backtests/${runId}`);
}

export function getBacktestDailyCsvUrl(runId: number): string {
  return `/api/backtests/${runId}/daily.csv`;
}

export function getBacktestTradesCsvUrl(runId: number): string {
  return `/api/backtests/${runId}/trades.csv`;
}

export function getBacktestSummaryCsvUrl(runId: number): string {
  return `/api/backtests/${runId}/summary.csv`;
}

export async function getBacktestDailyCsv(runId: number): Promise<BacktestDailySnapshot[]> {
  const rows = await fetchCsv(getBacktestDailyCsvUrl(runId));
  return rows.map((row) => ({
    backtest_run_id: runId,
    date: row.date,
    capital: row.capital,
    cash: row.cash,
    position_value: row.position_value,
    total_asset: row.total_asset,
    drawdown: row.drawdown,
    cumulative_fees: row.cumulative_fees,
    mode: row.mode === "aggressive" ? "aggressive" : "safe",
    mode_rule_code: row.mode_rule_code || null,
  }));
}

export async function getBacktestTradesCsv(runId: number): Promise<BacktestTrade[]> {
  const rows = await fetchCsv(getBacktestTradesCsvUrl(runId));
  return rows.map((row, index) => ({
    id: index + 1,
    backtest_run_id: runId,
    date: row.date,
    side: row.side,
    quantity: row.quantity,
    price: row.price,
    fee: row.fee,
    realized_pnl: row.realized_pnl,
    sell_reason: row.sell_reason || null,
    holding_days: row.holding_days ? Number(row.holding_days) : null,
    open_position_count: row.open_position_count ? Number(row.open_position_count) : null,
    cash_after: row.cash_after || null,
    capital_after: row.capital_after || null,
    source: row.source,
    created_at: "",
    updated_at: "",
  }));
}

async function fetchCsv(url: string): Promise<Record<string, string>[]> {
  const text = await apiGetText(url);
  return parseCsv(text);
}

function parseCsv(text: string): Record<string, string>[] {
  const lines = text.trim().split(/\r?\n/);
  const [headerLine, ...body] = lines;
  if (!headerLine) return [];
  const headers = splitCsvLine(headerLine);
  return body.map((line) => {
    const cells = splitCsvLine(line);
    return headers.reduce<Record<string, string>>((row, header, index) => {
      row[header] = cells[index] ?? "";
      return row;
    }, {});
  });
}

function splitCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current);
  return cells;
}
