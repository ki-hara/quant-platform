import { RefreshCw, Save, Trash2, Wand2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { getDashboard } from "../api/dashboard";
import { listStrategyConfigs } from "../api/strategies";
import {
  deleteTrade,
  listPositions,
  listTrades,
  recordManualTrade,
  updatePosition,
} from "../api/trades";
import { getDailyPlan } from "../api/tradingPlan";
import { Table, type TableColumn } from "../components/Table";
import type {
  DailyPlan,
  DashboardResponse,
  PositionRow,
  StrategyConfig,
  TradeRow,
} from "../types/api";
import {
  formatMoney,
  todayIso,
  translateMode,
  translateReason,
  translateSide,
} from "../utils/format";

const initialManualForm = {
  trade_date: todayIso(),
  side: "buy" as "buy" | "sell",
  quantity: "",
  limit_price: "",
  price: "",
  fee: "0",
  source: "manual" as "manual" | "correction",
  mode: "safe",
  position_id: "",
  sell_reason: "",
};

interface SellSignalRow {
  position_id?: number;
  should_sell?: boolean;
  reason?: string | null;
}

export function TradesPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [manualForm, setManualForm] = useState(initialManualForm);
  const [positionEdits, setPositionEdits] = useState<Record<number, { quantity: string; buy_price: string; status: string }>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const openPositions = useMemo(
    () => positions.filter((position) => position.status.toLowerCase() === "open"),
    [positions],
  );

  const sellRecommendations = useMemo(() => {
    const signals = Array.isArray(dashboard?.signals.sell_signals)
      ? dashboard.signals.sell_signals
      : [];
    return signals
      .map(toSellSignalRow)
      .filter((signal) => signal.should_sell)
      .map((signal) => ({
        ...signal,
        position: openPositions.find((position) => position.id === signal.position_id),
      }))
      .filter((signal) => signal.position);
  }, [dashboard?.signals.sell_signals, openPositions]);

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
      const [positionRows, tradeRows, dailyPlan, dashboardData] = await Promise.all([
        listPositions(configId),
        listTrades(configId),
        getDailyPlan(configId),
        getDashboard(configId),
      ]);
      setPositions(positionRows);
      setPositionEdits(
        Object.fromEntries(
          positionRows.map((position) => [
            position.id,
            { quantity: position.quantity, buy_price: position.buy_price, status: "open" },
          ]),
        ),
      );
      setTrades(tradeRows);
      setPlan(dailyPlan);
      setDashboard(dashboardData);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  function fillBuyRecommendation() {
    if (!plan || !plan.buy_available) return;
    setManualForm((current) => ({
      ...current,
      trade_date: plan.plan_date,
      side: "buy",
      quantity: String(plan.LOC.quantity),
      limit_price: plan.LOC.limit_price,
      price: plan.LOC.limit_price,
      fee: "0",
      mode: plan.confirmed_mode,
      position_id: "",
      sell_reason: "",
    }));
  }

  function fillSellRecommendation(position: PositionRow, reason: string | null | undefined) {
    const price = dashboard?.latest_price?.close ?? position.buy_price;
    const fee = estimateFee(price, position.quantity, dashboard?.config.fee_rate);
    setManualForm((current) => ({
      ...current,
      trade_date: todayIso(),
      side: "sell",
      quantity: position.quantity,
      limit_price: "",
      price,
      fee,
      position_id: String(position.id),
      sell_reason: reason ?? "manual_signal",
    }));
  }

  async function handleManualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId) return;
    if (manualForm.side === "sell" && !manualForm.position_id) {
      setError("매도할 포지션을 선택해 주세요.");
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
        limit_price: manualForm.side === "buy" && manualForm.limit_price ? manualForm.limit_price : null,
        price: manualForm.price,
        fee: estimateFee(manualForm.price, manualForm.quantity, dashboard?.config.fee_rate),
        sell_reason: manualForm.side === "sell" ? manualForm.sell_reason.trim() || null : null,
        source: "manual",
        mode: manualForm.side === "buy" ? manualForm.mode : undefined,
        position_id: manualForm.side === "sell" ? Number(manualForm.position_id) : null,
      });
      setMessage("거래가 저장되었습니다.");
      setManualForm({ ...initialManualForm, trade_date: todayIso() });
      await loadRows(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteTrade(trade: TradeRow) {
    if (!window.confirm(`${trade.date} ${translateSide(trade.side)} 거래를 삭제할까요?`)) return;
    try {
      setDeletingId(trade.id);
      setError("");
      setMessage("");
      await deleteTrade(trade.id);
      setMessage("거래내역을 삭제했습니다.");
      await loadRows(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setDeletingId(null);
    }
  }

  async function handleSavePosition(positionId: number) {
    if (!selectedId) return;
    const edit = positionEdits[positionId];
    if (!edit) return;
    try {
      setSaving(true);
      setError("");
      setMessage("");
      await updatePosition(positionId, edit);
      setMessage(edit.status === "unfilled" ? "포지션을 미체결로 제거했습니다." : "포지션을 보정했습니다.");
      await loadRows(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  const tradeColumnsWithActions: TableColumn<TradeRow>[] = [
    ...tradeColumns,
    {
      key: "delete",
      header: "삭제",
      align: "center",
      render: (row) => (
        <button
          className="icon-button"
          type="button"
          title="수동/보정 매수 거래만 삭제할 수 있습니다."
          disabled={deletingId === row.id || !["manual", "correction"].includes(row.source)}
          onClick={() => handleDeleteTrade(row)}
        >
          <Trash2 aria-hidden="true" size={15} />
        </button>
      ),
    },
  ];

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
          <RefreshCw aria-hidden="true" size={16} /> 새로고침
        </button>
      </section>

      {loading ? <div className="notice">불러오는 중입니다.</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice notice-success">{message}</div> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>전략 추천 거래</h2>
            <span>추천값을 실제 체결 입력 폼에 기본값으로 채웁니다.</span>
          </div>
        </div>
        <div className="recommendation-grid">
          <div className="recommendation-card">
            <div>
              <span className="signal-label">오늘의 LOC 매수</span>
              <strong>{plan?.buy_available ? "매수 가능" : "매수 불가"}</strong>
              <p>
                {plan
                  ? `${plan.symbol} / 지정가 ${formatMoney(plan.LOC.limit_price)} / 수량 ${plan.LOC.quantity}`
                  : "일일 계획 데이터가 없습니다."}
              </p>
              <small>{translateReason(plan?.LOC.blocking_reason)}</small>
              {plan?.LOC.orders?.length ? (
                <div className="loc-order-list">
                  {plan.LOC.orders.slice(0, 5).map((order) => (
                    <div className="loc-order-row" key={order.step}>
                      <span>{order.step}차 LOC</span>
                      <strong>
                        {formatMoney(order.limit_price)} × {order.quantity}주
                      </strong>
                      <small>누적 {order.cumulative_quantity}주 / {formatMoney(order.cumulative_amount)}</small>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
            <button type="button" onClick={fillBuyRecommendation} disabled={!plan?.buy_available || saving}>
              <Wand2 aria-hidden="true" size={16} /> 매수 주문 입력
            </button>
          </div>

          {sellRecommendations.length > 0 ? (
            sellRecommendations.map((signal) => (
              <div className="recommendation-card" key={signal.position?.id}>
                <div>
                  <span className="signal-label">매도 후보</span>
                  <strong>#{signal.position?.id} {translateReason(signal.reason)}</strong>
                  <p>
                    {signal.position?.buy_date} 매수 / 수량 {formatMoney(signal.position?.quantity)} / 현재가{" "}
                    {formatMoney(dashboard?.latest_price?.close)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => signal.position && fillSellRecommendation(signal.position, signal.reason)}
                >
                  <Wand2 aria-hidden="true" size={16} /> 추천값 입력
                </button>
              </div>
            ))
          ) : (
            <div className="recommendation-card">
              <div>
                <span className="signal-label">매도 후보</span>
                <strong>추천 없음</strong>
                <p>현재 조건에서 자동으로 제안할 매도 포지션이 없습니다.</p>
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="page-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>보유 포지션</h2>
              <span>수량, 매수가, 체결 상태를 직접 보정합니다.</span>
            </div>
          </div>
          <div className="position-edit-list">
            {positions.length === 0 ? <div className="empty-state">보유 포지션이 없습니다.</div> : null}
            {positions.map((position) => {
              const edit = positionEdits[position.id] ?? {
                quantity: position.quantity,
                buy_price: position.buy_price,
                status: "open",
              };
              return (
                <div className="position-edit-row" key={position.id}>
                  <span>#{position.id} / {position.buy_date}</span>
                  <label>
                    수량
                    <input
                      value={edit.quantity}
                      inputMode="decimal"
                      onChange={(event) =>
                        setPositionEdits((current) => ({
                          ...current,
                          [position.id]: { ...edit, quantity: event.target.value },
                        }))
                      }
                    />
                  </label>
                  <label>
                    매수가
                    <input
                      value={edit.buy_price}
                      inputMode="decimal"
                      onChange={(event) =>
                        setPositionEdits((current) => ({
                          ...current,
                          [position.id]: { ...edit, buy_price: event.target.value },
                        }))
                      }
                    />
                  </label>
                  <label>
                    상태
                    <select
                      value={edit.status}
                      onChange={(event) =>
                        setPositionEdits((current) => ({
                          ...current,
                          [position.id]: { ...edit, status: event.target.value },
                        }))
                      }
                    >
                      <option value="open">체결</option>
                      <option value="unfilled">미체결</option>
                    </select>
                  </label>
                  <button type="button" onClick={() => handleSavePosition(position.id)} disabled={saving}>
                    저장
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>{manualForm.side === "buy" ? "매수 주문" : "매도 주문"}</h2>
              <span>매수는 주문 수량을 입력하고, 체결가는 보유 포지션에서 보정합니다.</span>
            </div>
          </div>
          <form className="form-stack" onSubmit={handleManualSubmit}>
            <label>
              거래일
              <input
                type="date"
                value={manualForm.trade_date}
                onChange={(event) => setManualForm((current) => ({ ...current, trade_date: event.target.value }))}
                required
              />
            </label>
            <label>
              구분
              <select
                value={manualForm.side}
                onChange={(event) =>
                  setManualForm((current) => ({
                    ...current,
                    side: event.target.value as "buy" | "sell",
                    position_id: "",
                    sell_reason: "",
                    limit_price: event.target.value === "buy" ? current.limit_price : "",
                  }))
                }
              >
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </label>
            {manualForm.side === "sell" ? (
              <div className="position-pick-list">
                {openPositions.map((position) => (
                  <button
                    key={position.id}
                    type="button"
                    className={manualForm.position_id === String(position.id) ? "is-active" : undefined}
                    onClick={() =>
                      setManualForm((current) => ({
                        ...current,
                        position_id: String(position.id),
                        quantity: position.quantity,
                      }))
                    }
                  >
                    #{position.id} / {position.buy_date} / {formatMoney(position.quantity)}주 / 매수가{" "}
                    {formatMoney(position.buy_price)}
                  </button>
                ))}
              </div>
            ) : (
              <label>
                모드
                <select
                  value={manualForm.mode}
                  onChange={(event) => setManualForm((current) => ({ ...current, mode: event.target.value }))}
                >
                  <option value="safe">안전</option>
                  <option value="aggressive">공세</option>
                </select>
              </label>
            )}
            {manualForm.side === "buy" ? (
              <label>
                LOC 주문가
                <input
                  value={manualForm.limit_price}
                  onChange={(event) => setManualForm((current) => ({ ...current, limit_price: event.target.value }))}
                  placeholder="추천 LOC가"
                  inputMode="decimal"
                />
              </label>
            ) : null}
            <label>
              {manualForm.side === "buy" ? "주문 수량" : "매도 수량"}
              <input
                value={manualForm.quantity}
                onChange={(event) => setManualForm((current) => ({ ...current, quantity: event.target.value }))}
                placeholder="0"
                inputMode="decimal"
                required
              />
            </label>
            {manualForm.side === "sell" ? (
              <label>
                매도가
                <input
                  value={manualForm.price}
                  onChange={(event) => setManualForm((current) => ({ ...current, price: event.target.value }))}
                  placeholder="0"
                  inputMode="decimal"
                  required
                />
              </label>
            ) : null}
            <label>
              실제 수수료
              <input
                type="hidden"
                value={estimateFee(manualForm.price, manualForm.quantity, dashboard?.config.fee_rate)}
                readOnly
              />
            </label>
            {manualForm.side === "sell" ? (
              <label>
                매도 사유
                <input
                  value={manualForm.sell_reason}
                  onChange={(event) => setManualForm((current) => ({ ...current, sell_reason: event.target.value }))}
                  placeholder="profit_target, max_holding_period 등"
                />
              </label>
            ) : null}
            <button type="submit" disabled={!selectedId || saving}>
              <Save aria-hidden="true" size={16} /> {saving ? "저장 중" : "거래 저장"}
            </button>
            <p className="form-status">매수 체결 수량과 매수가는 보유 포지션에서 보정합니다.</p>
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
        <Table columns={tradeColumnsWithActions} rows={trades} getRowKey={(row) => row.id} />
      </section>
    </div>
  );
}

const tradeColumns: TableColumn<TradeRow>[] = [
  { key: "date", header: "일자", render: (row) => row.date },
  { key: "side", header: "구분", render: (row) => translateSide(row.side) },
  { key: "quantity", header: "수량", align: "right", render: (row) => formatMoney(row.quantity) },
  { key: "limit_price", header: "LOC가", align: "right", render: (row) => formatOptionalMoney(row.limit_price) },
  { key: "price", header: "체결가", align: "right", render: (row) => formatMoney(row.price) },
  { key: "fee", header: "수수료", align: "right", render: (row) => formatMoney(row.fee) },
  { key: "pnl", header: "실현손익", align: "right", render: (row) => formatMoney(row.realized_pnl) },
  { key: "reason", header: "사유", render: (row) => translateReason(row.sell_reason) },
];

function formatOptionalMoney(value: string | null | undefined): string {
  return value ? formatMoney(value) : "-";
}

function toSellSignalRow(row: Record<string, unknown>): SellSignalRow {
  return {
    position_id: typeof row.position_id === "number" ? row.position_id : undefined,
    should_sell: row.should_sell === true,
    reason: typeof row.reason === "string" ? row.reason : null,
  };
}

function estimateFee(price: string, quantity: string, feeRate: string | undefined): string {
  const fee = Number(price) * Number(quantity) * Number(feeRate ?? "0") / 100;
  return Number.isFinite(fee) ? fee.toFixed(6) : "0";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
