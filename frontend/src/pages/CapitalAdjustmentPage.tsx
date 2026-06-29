import { Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { createPortfolioAdjustment, listPortfolioAdjustments } from "../api/portfolios";
import { listStrategyConfigs } from "../api/strategies";
import { Table, type TableColumn } from "../components/Table";
import type { PortfolioAdjustment, StrategyConfig } from "../types/api";
import { formatMoney, todayIso } from "../utils/format";
import { rememberStrategyConfigId, resolveRememberedStrategyConfigId } from "../utils/strategySelection";

export function CapitalAdjustmentPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [adjustments, setAdjustments] = useState<PortfolioAdjustment[]>([]);
  const [adjustBoth, setAdjustBoth] = useState(true);
  const [adjustmentForm, setAdjustmentForm] = useState({
    date: todayIso(),
    amount: "",
    cash_delta: "",
    capital_delta: "",
    memo: "",
  });
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listStrategyConfigs()
      .then((rows) => {
        setConfigs(rows);
        setSelectedId(resolveRememberedStrategyConfigId(rows));
      })
      .catch((caught) => setError(errorMessage(caught)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    void loadAdjustments(selectedId);
  }, [selectedId]);

  async function loadAdjustments(configId = selectedId) {
    if (!configId) return;
    try {
      setLoading(true);
      setError("");
      setAdjustments(await listPortfolioAdjustments(configId));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function handleAdjustmentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId) return;
    const cashDelta = adjustBoth ? adjustmentForm.amount : adjustmentForm.cash_delta;
    const capitalDelta = adjustBoth ? adjustmentForm.amount : adjustmentForm.capital_delta;
    try {
      setWorking(true);
      setError("");
      setMessage("");
      await createPortfolioAdjustment(selectedId, {
        date: adjustmentForm.date,
        cash_delta: cashDelta || "0",
        capital_delta: capitalDelta || "0",
        memo: adjustmentForm.memo.trim() || null,
      });
      setMessage("자본 조정을 저장했습니다.");
      setAdjustmentForm({ date: todayIso(), amount: "", cash_delta: "", capital_delta: "", memo: "" });
      await loadAdjustments(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

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
      </section>

      {loading ? <div className="notice">불러오는 중입니다.</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice notice-success">{message}</div> : null}
      {!loading && configs.length === 0 ? <div className="empty-state">전략 설정 데이터 없음</div> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>자본 조정</h2>
            <span>현금 입출금과 전략 기준금 조정을 기록합니다.</span>
          </div>
        </div>
        <form className="form-stack adjustment-form" onSubmit={handleAdjustmentSubmit}>
          <label>
            날짜
            <input
              type="date"
              value={adjustmentForm.date}
              onChange={(event) => setAdjustmentForm((current) => ({ ...current, date: event.target.value }))}
            />
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={adjustBoth} onChange={(event) => setAdjustBoth(event.target.checked)} />
            Cash와 Capital을 같은 금액만큼 조정
          </label>
          {adjustBoth ? (
            <label>
              조정 금액
              <input
                value={adjustmentForm.amount}
                inputMode="decimal"
                placeholder="입금은 양수, 출금은 음수"
                onChange={(event) => setAdjustmentForm((current) => ({ ...current, amount: event.target.value }))}
              />
            </label>
          ) : (
            <>
              <label>
                Cash 조정액
                <input
                  value={adjustmentForm.cash_delta}
                  inputMode="decimal"
                  onChange={(event) => setAdjustmentForm((current) => ({ ...current, cash_delta: event.target.value }))}
                />
              </label>
              <label>
                Capital 조정액
                <input
                  value={adjustmentForm.capital_delta}
                  inputMode="decimal"
                  onChange={(event) => setAdjustmentForm((current) => ({ ...current, capital_delta: event.target.value }))}
                />
              </label>
            </>
          )}
          <label>
            메모
            <input
              value={adjustmentForm.memo}
              onChange={(event) => setAdjustmentForm((current) => ({ ...current, memo: event.target.value }))}
            />
          </label>
          <button type="submit" disabled={!selectedId || working}>
            <Save aria-hidden="true" size={16} /> 자본 조정 저장
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>자본 조정 내역</h2>
            <span>최근 조정 내역</span>
          </div>
        </div>
        <Table columns={adjustmentColumns} rows={adjustments} getRowKey={(row) => row.id} />
      </section>
    </div>
  );
}

const adjustmentColumns: TableColumn<PortfolioAdjustment>[] = [
  { key: "date", header: "날짜", render: (row) => row.date },
  { key: "cash", header: "Cash", align: "right", render: (row) => formatMoney(row.cash_delta) },
  { key: "capital", header: "Capital", align: "right", render: (row) => formatMoney(row.capital_delta) },
  { key: "memo", header: "메모", render: (row) => row.memo ?? "-" },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
