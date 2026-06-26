import { RefreshCw, Save, Trash2, Wand2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { getDashboard } from "../api/dashboard";
import { listStrategyConfigs } from "../api/strategies";
import {
  createBuyOrderPosition,
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
  return_percent?: string | number | null;
  sell_limit_price?: string | number | null;
  holding_days?: number | null;
  max_holding_days?: number | null;
  days_to_deadline?: number | null;
  urgency?: string | null;
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

  const sellSignalByPosition = useMemo(() => {
    const signals = Array.isArray(dashboard?.signals.sell_signals)
      ? dashboard.signals.sell_signals
      : [];
    return new Map(
      signals
        .map(toSellSignalRow)
        .filter((signal) => typeof signal.position_id === "number")
        .map((signal) => [signal.position_id as number, signal]),
    );
  }, [dashboard?.signals.sell_signals]);

  const sellOrderRows = useMemo(
    () =>
      openPositions.map((position) => ({
        ...sellSignalByPosition.get(position.id),
        position,
      })),
    [openPositions, sellSignalByPosition],
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
            {
              quantity: String(Math.trunc(Number(position.quantity))),
              buy_price: Number(position.buy_price).toFixed(2),
              status: position.status.toLowerCase() === "pending" ? "pending" : "open",
            },
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
      quantity: wholeShare(plan.LOC.quantity),
      limit_price: plan.LOC.limit_price,
      price: plan.LOC.limit_price,
      fee: "0",
      mode: plan.confirmed_mode,
      position_id: "",
      sell_reason: "",
    }));
  }

  function fillSellRecommendation(position: PositionRow, signal: SellSignalRow | undefined) {
    const price = String(signal?.sell_limit_price ?? position.buy_price);
    const quantity = wholeShare(position.quantity);
    const fee = estimateFee(price, quantity, dashboard?.config.fee_rate);
    setManualForm((current) => ({
      ...current,
      trade_date: todayIso(),
      side: "sell",
      quantity,
      limit_price: "",
      price,
      fee,
      position_id: String(position.id),
      sell_reason: signal?.reason ?? "manual_signal",
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
      if (manualForm.side === "buy") {
        await createBuyOrderPosition(selectedId, {
          order_date: manualForm.trade_date,
          quantity: manualForm.quantity,
          limit_price: manualForm.limit_price,
          mode: manualForm.mode,
        });
        setMessage("매수 주문이 보유 포지션에 대기 상태로 등록되었습니다.");
        setManualForm({ ...initialManualForm, trade_date: todayIso() });
        await loadRows(selectedId);
        return;
      }
      await recordManualTrade({
        config_id: selectedId,
        trade_date: manualForm.trade_date,
        side: manualForm.side,
        quantity: manualForm.quantity,
        limit_price: null,
        price: manualForm.price,
        fee: estimateFee(manualForm.price, manualForm.quantity, dashboard?.config.fee_rate),
        sell_reason: manualForm.sell_reason.trim() || null,
        source: "manual",
        mode: undefined,
        position_id: Number(manualForm.position_id),
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
    const position = positions.find((row) => row.id === positionId);
    const nextEdit =
      position?.status.toLowerCase() === "pending" && edit.status === "pending"
        ? { ...edit, status: "open" }
        : edit;
    try {
      setSaving(true);
      setError("");
      setMessage("");
      await updatePosition(positionId, nextEdit);
      setMessage(
        nextEdit.status === "unfilled"
          ? "포지션을 미체결로 제거했습니다."
          : position?.status.toLowerCase() === "pending"
            ? "포지션을 체결 등록했습니다."
            : "포지션을 보정했습니다.",
      );
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
              <div className="compact-facts">
                <span>{plan?.symbol ?? "-"}</span>
                <span>{formatMoney(plan?.LOC.limit_price)}</span>
                <span>{plan?.LOC.quantity ?? "-"}주</span>
              </div>
              <small>{translateReason(plan?.LOC.blocking_reason)}</small>
              {plan?.LOC.orders?.length ? (
                <div className="loc-order-list">
                  {plan.LOC.orders.slice(0, 5).map((order) => (
                    <div className="loc-order-row" key={order.step}>
                      <span>{order.step}차 LOC</span>
                      <strong>{formatMoney(order.limit_price)}</strong>
                      <small>{order.quantity}주 / 누적 {order.cumulative_quantity}주</small>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
            <button type="button" onClick={fillBuyRecommendation} disabled={!plan?.buy_available || saving}>
              <Wand2 aria-hidden="true" size={16} /> 매수 주문 입력
            </button>
          </div>

          {sellOrderRows.length > 0 ? (
            <div className="recommendation-card recommendation-list-card">
              <div>
                <span className="signal-label">오늘의 LOC 매도</span>
                <strong>{sellOrderRows.length}건</strong>
                <div className="sell-order-list">
                  {sellOrderRows.map((signal) => (
                    <div className={`sell-order-row ${sellCardClass(signal)}`} key={signal.position?.id}>
                      <div>
                        <strong>#{signal.position?.id} {translateReason(signal.reason ?? "sell_condition_waiting")}</strong>
                        <small>
                          {holdingDaysText(signal.holding_days)} / {deadlineText(signal.days_to_deadline)} / 수익률{" "}
                          {returnPercentText(signal.return_percent)}
                        </small>
                      </div>
                      <span>{wholeShare(signal.position?.quantity)}주</span>
                      <strong>{formatMoney(signal.sell_limit_price, dashboard?.config.symbol)}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="recommendation-card">
              <div>
                <span className="signal-label">오늘의 LOC 매도</span>
                <strong>주문 없음</strong>
                <p>오늘 LOC 매도 주문이 필요한 포지션이 없습니다.</p>
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
                status: position.status.toLowerCase() === "pending" ? "pending" : "open",
              };
              const sellSignal = sellSignalByPosition.get(position.id);
              return (
                <div className="position-edit-row" key={position.id}>
                  <span>#{position.id} / {position.buy_date}</span>
                  <div className="readonly-field">
                    <span>LOC가</span>
                    <strong>{formatOptionalMoney(position.limit_price)}</strong>
                  </div>
                  <label>
                    수량
                    <input
                      type="number"
                      step="1"
                      min="0"
                      value={edit.quantity}
                      inputMode="numeric"
                      onChange={(event) =>
                        setPositionEdits((current) => ({
                          ...current,
                          [position.id]: { ...edit, quantity: normalizeShareInput(event.target.value) },
                        }))
                      }
                    />
                  </label>
                  <label>
                    체결가
                    <input
                      type="number"
                      step="0.01"
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
                      <option value="pending">대기</option>
                      <option value="open">체결</option>
                      <option value="unfilled">미체결</option>
                    </select>
                  </label>
                  <div className={`holding-status ${holdingStatusClass(sellSignal)}`}>
                    <span>보유기간</span>
                    <strong>{holdingStatusText(sellSignal)}</strong>
                  </div>
                  <button type="button" onClick={() => handleSavePosition(position.id)} disabled={saving}>
                    {position.status.toLowerCase() === "pending" ? "등록" : "수정"}
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <div className="order-tabs order-tabs-heading" role="tablist" aria-label="주문 구분">
                {(["buy", "sell"] as const).map((side) => (
                  <button
                    key={side}
                    type="button"
                    className={manualForm.side === side ? "is-active" : undefined}
                    onClick={() =>
                      setManualForm((current) => ({
                        ...current,
                        side,
                        position_id: "",
                        sell_reason: "",
                        limit_price: side === "buy" ? current.limit_price : "",
                      }))
                    }
                  >
                    {side === "buy" ? "매수 주문" : "매도 주문"}
                  </button>
                ))}
              </div>
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
            {manualForm.side === "sell" ? (
              <div className="position-pick-list">
                {openPositions.map((position) => (
                  <button
                    key={position.id}
                    type="button"
                    className={manualForm.position_id === String(position.id) ? "is-active" : undefined}
                    onClick={() => {
                      const signal = sellSignalByPosition.get(position.id);
                      const price = String(signal?.sell_limit_price ?? position.buy_price);
                      setManualForm((current) => ({
                        ...current,
                        position_id: String(position.id),
                        quantity: wholeShare(position.quantity),
                        price,
                        sell_reason: signal?.reason ?? current.sell_reason,
                      }));
                    }}
                  >
                    #{position.id} / {position.buy_date} / {wholeShare(position.quantity)}주 / 매수가{" "}
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
                  required
                />
              </label>
            ) : null}
            <label>
              {manualForm.side === "buy" ? "주문 수량" : "매도 수량"}
              <input
                type="number"
                step="1"
                min="1"
                value={manualForm.quantity}
                onChange={(event) =>
                  setManualForm((current) => ({ ...current, quantity: normalizeShareInput(event.target.value) }))
                }
                placeholder="0"
                inputMode="numeric"
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
              <Save aria-hidden="true" size={16} /> {saving ? "저장 중" : manualForm.side === "buy" ? "주문 저장" : "거래 저장"}
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
    return_percent:
      typeof row.return_percent === "string" || typeof row.return_percent === "number"
        ? row.return_percent
        : null,
    sell_limit_price:
      typeof row.sell_limit_price === "string" || typeof row.sell_limit_price === "number"
        ? row.sell_limit_price
        : null,
    holding_days: typeof row.holding_days === "number" ? row.holding_days : null,
    max_holding_days: typeof row.max_holding_days === "number" ? row.max_holding_days : null,
    days_to_deadline: typeof row.days_to_deadline === "number" ? row.days_to_deadline : null,
    urgency: typeof row.urgency === "string" ? row.urgency : null,
  };
}

function holdingDaysText(days: number | null | undefined): string {
  if (days === null || days === undefined) return "보유기간 -";
  if (days === 0) return "당일 체결";
  return `${days}일 보유`;
}

function deadlineText(days: number | null | undefined): string {
  if (days === null || days === undefined) return "기한 -";
  if (days < 0) return `${Math.abs(days)}일 초과`;
  if (days === 0) return "오늘 만료";
  return `${days}일 남음`;
}

function returnPercentText(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return `${number.toFixed(2)}%`;
}

function sellCardClass(signal: SellSignalRow): string {
  if (signal.urgency === "expired") return "recommendation-danger";
  if (signal.urgency === "profit_target") return "recommendation-success";
  if (signal.urgency === "near_deadline") return "recommendation-warning";
  return "";
}

function holdingStatusText(signal: SellSignalRow | undefined): string {
  if (!signal) return "-";
  const prefix = signal.holding_days === null || signal.holding_days === undefined
    ? "-"
    : signal.holding_days === 0
      ? "당일 체결"
      : `${signal.holding_days}일`;
  const max = signal.max_holding_days === null || signal.max_holding_days === undefined ? "-" : `${signal.max_holding_days}일`;
  return `${prefix} / ${max} / ${deadlineText(signal.days_to_deadline)}`;
}

function holdingStatusClass(signal: SellSignalRow | undefined): string {
  if (!signal) return "";
  if (signal.urgency === "expired") return "is-danger";
  if (signal.urgency === "near_deadline") return "is-warning";
  if (signal.urgency === "profit_target") return "is-success";
  return "";
}

function wholeShare(value: string | number | null | undefined): string {
  const number = Math.trunc(Number(value ?? 0));
  return Number.isFinite(number) && number > 0 ? String(number) : "";
}

function normalizeShareInput(value: string): string {
  if (!value) return "";
  const number = Math.trunc(Number(value));
  return Number.isFinite(number) && number >= 0 ? String(number) : "";
}

function estimateFee(price: string, quantity: string, feeRate: string | undefined): string {
  const fee = Number(price) * Number(quantity) * Number(feeRate ?? "0") / 100;
  return Number.isFinite(fee) ? fee.toFixed(6) : "0";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
