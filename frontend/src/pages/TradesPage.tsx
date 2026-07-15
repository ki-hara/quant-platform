import { RefreshCw, Save, Trash2, Wand2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { getDashboard } from "../api/dashboard";
import { listStrategyConfigs } from "../api/strategies";
import {
  createBuyOrderPosition,
  deleteTrade,
  listPositionHistory,
  listPositions,
  recordManualTrade,
  updatePosition,
} from "../api/trades";
import { getDailyPlan } from "../api/tradingPlan";
import { Table, type TableColumn } from "../components/Table";
import type {
  DailyPlan,
  DashboardResponse,
  PositionHistoryRow,
  PositionRow,
  StrategyConfig,
} from "../types/api";
import {
  formatMoney,
  marketDateIso,
  translateCode,
  translateMode,
  translateReason,
} from "../utils/format";
import { hasCrossedLocOrders, netLocOrders, tickSizeForSymbol, type LocOrderInput } from "../utils/locNetting";
import { isAbortError, LatestRequest } from "../utils/latestRequest";
import { recommendedBuyPrice, recommendedSellPrice } from "../utils/orderPrices";
import { rememberStrategyConfigId, resolveRememberedStrategyConfigId } from "../utils/strategySelection";

function initialManualForm(symbol?: string | null) {
  return {
    trade_date: marketDateIso(symbol),
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
}

interface SellSignalRow {
  position_id?: number;
  should_sell?: boolean;
  reason?: string | null;
  return_percent?: string | number | null;
  sell_limit_price?: string | number | null;
  sell_threshold_percent?: string | number | null;
  holding_days?: number | null;
  max_holding_days?: number | null;
  days_to_deadline?: number | null;
  urgency?: string | null;
}

type SellOrderRow = SellSignalRow & { position: PositionRow };
type LivePositionSizingPolicy = "fixed_quantity" | "full_allocation";

export function TradesPage() {
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [positionHistory, setPositionHistory] = useState<PositionHistoryRow[]>([]);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [livePositionSizingPolicy, setLivePositionSizingPolicy] = useState<LivePositionSizingPolicy>("fixed_quantity");
  const [manualForm, setManualForm] = useState(() => initialManualForm());
  const [positionEdits, setPositionEdits] = useState<Record<number, { quantity: string; buy_price: string; status: string }>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const rowRequestsRef = useRef<LatestRequest | null>(null);
  if (rowRequestsRef.current === null) rowRequestsRef.current = new LatestRequest();
  const rowRequests = rowRequestsRef.current;
  const selectedSymbol = dashboard?.config.symbol ?? plan?.symbol ?? configs.find((config) => config.id === selectedId)?.symbol;

  const sortedPositions = useMemo(
    () => [...positions].sort(comparePositionByDate),
    [positions],
  );

  const openPositions = useMemo(
    () => sortedPositions.filter((position) => position.status.toLowerCase() === "open"),
    [sortedPositions],
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
      openPositions
        .map((position) => ({
          ...sellSignalByPosition.get(position.id),
          position,
        }))
        .sort(compareSellOrderRow),
    [openPositions, sellSignalByPosition],
  );

  const locNettingPreview = useMemo(() => {
    const orders = buildLocNettingInputs(plan, sellOrderRows);
    const tickSize = tickSizeForSymbol(selectedSymbol);
    return {
      needed: hasCrossedLocOrders(orders),
      orders,
      nettedOrders: sortLocOrdersByPriceDesc(netLocOrders(orders, tickSize)),
      tickSize,
    };
  }, [plan, sellOrderRows, selectedSymbol]);

  useEffect(() => {
    const controller = new AbortController();
    listStrategyConfigs(controller.signal)
      .then((rows) => {
        setConfigs(rows);
        setSelectedId(resolveRememberedStrategyConfigId(rows));
      })
      .catch((caught) => {
        if (!isAbortError(caught)) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (selectedId) void loadRows(selectedId, livePositionSizingPolicy);
  }, [selectedId, livePositionSizingPolicy]);

  useEffect(() => () => rowRequests.cancel(), [rowRequests]);

  async function loadRows(configId = selectedId, positionSizingPolicy = livePositionSizingPolicy) {
    if (!configId) return;
    const controller = rowRequests.start();
    try {
      setLoading(true);
      setError("");
      const [positionRows, positionHistoryRows, dailyPlan, dashboardData] = await Promise.all([
        listPositions(configId, controller.signal),
        listPositionHistory(configId, controller.signal),
        getDailyPlan(configId, positionSizingPolicy, controller.signal),
        getDashboard(configId, controller.signal),
      ]);
      if (!rowRequests.isCurrent(controller)) return;
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
      setPositionHistory(positionHistoryRows);
      setPlan(dailyPlan);
      setDashboard(dashboardData);
    } catch (caught) {
      if (rowRequests.isCurrent(controller) && !isAbortError(caught)) {
        setError(errorMessage(caught));
      }
    } finally {
      if (rowRequests.isCurrent(controller)) {
        setLoading(false);
        rowRequests.finish(controller);
      }
    }
  }

  function fillBuyRecommendation() {
    if (!plan || !plan.buy_available) return;
    setManualForm((current) => ({
      ...current,
      trade_date: plan.plan_date,
      side: "buy",
      quantity: wholeShare(plan.LOC.quantity),
      limit_price: recommendedBuyPrice(plan.LOC.limit_price),
      price: recommendedBuyPrice(plan.LOC.limit_price),
      fee: "0",
      mode: plan.confirmed_mode,
      position_id: "",
      sell_reason: "",
    }));
  }

  function fillSellRecommendation(position: PositionRow, signal: SellSignalRow | undefined) {
    const price = sellExecutionPrice(position);
    const quantity = wholeShare(position.quantity);
    const fee = estimateFee(price, quantity, dashboard?.config.fee_rate);
    setManualForm((current) => ({
      ...current,
      trade_date: marketDateIso(selectedSymbol),
      side: "sell",
      quantity,
      limit_price: "",
      price,
      fee,
      position_id: String(position.id),
      sell_reason: signal?.reason ?? "manual_signal",
    }));
  }

  function sellExecutionPrice(position: PositionRow): string {
    return recommendedSellPrice({
      previousClose: plan?.previous_close,
      locBasisClose: plan?.loc_basis_close,
      latestClose: dashboard?.latest_price?.close,
      buyPrice: position.buy_price,
    });
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
        setManualForm(initialManualForm(selectedSymbol));
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
      setManualForm(initialManualForm(selectedSymbol));
      await loadRows(selectedId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeletePositionHistory(row: PositionHistoryRow) {
    if (!row.trade_id || !row.sell_date) return;
    if (!window.confirm(`${row.sell_date} 매도 거래를 삭제할까요?`)) return;
    try {
      setDeletingId(row.trade_id);
      setError("");
      setMessage("");
      await deleteTrade(row.trade_id);
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

  const positionHistoryColumns: TableColumn<PositionHistoryRow>[] = [
    ...buildPositionHistoryColumns(selectedSymbol),
    {
      key: "delete",
      header: "삭제",
      align: "center",
      render: (row) => (
        <button
          className="icon-button"
          type="button"
          title="매도 체결 거래를 삭제합니다."
          disabled={!row.trade_id || deletingId === row.trade_id}
          onClick={() => handleDeletePositionHistory(row)}
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
            <h2>오늘 주문표</h2>
            <span>증권사에 입력할 LOC 주문을 확인합니다.</span>
          </div>
        </div>
        <div className="order-board-grid">
          <div className="order-board-card">
            <div className="order-board-header">
              <div>
                <span className="signal-label">오늘의 LOC 매수 주문표</span>
                <strong>{plan?.LOC.orders?.length ? `${Math.min(plan.LOC.orders.length, 5)}건` : "주문 없음"}</strong>
              </div>
              <div className="order-policy-switch" role="group" aria-label="매수 수량 계산">
                <button
                  type="button"
                  className={livePositionSizingPolicy === "fixed_quantity" ? "is-active" : undefined}
                  onClick={() => setLivePositionSizingPolicy("fixed_quantity")}
                >
                  정량매수
                </button>
                <button
                  type="button"
                  className={livePositionSizingPolicy === "full_allocation" ? "is-active" : undefined}
                  onClick={() => setLivePositionSizingPolicy("full_allocation")}
                >
                  정액매수
                </button>
              </div>
            </div>
            <div className="order-board-body">
              {plan?.LOC.orders?.length ? (
                <div className="loc-order-list">
                  {plan.LOC.orders.slice(0, 5).map((order) => (
                    <div className="loc-order-row" key={order.step}>
                      <span>{order.step}차 LOC</span>
                      <strong>LOC {formatMoney(order.limit_price, plan.symbol)}</strong>
                      <small>주문 {order.quantity}주 / 누적 {order.cumulative_quantity}주</small>
                    </div>
                  ))}
                </div>
              ) : (
                <small>{translateReason(plan?.LOC.blocking_reason) || "오늘 입력할 LOC 매수 주문이 없습니다."}</small>
              )}
            </div>
            <div className="order-board-actions">
              <button type="button" onClick={fillBuyRecommendation} disabled={!plan?.buy_available || saving}>
                <Wand2 aria-hidden="true" size={16} /> 매수 주문 입력
              </button>
            </div>
          </div>

          {sellOrderRows.length > 0 ? (
            <div className="order-board-card">
              <div className="order-board-header">
                <div>
                  <span className="signal-label">오늘의 LOC 매도 주문표</span>
                  <strong>{sellOrderRows.length}건</strong>
                </div>
              </div>
              <div className="order-board-body">
                <div className="sell-order-list">
                  {sellOrderRows.map((signal) => (
                    <div className={`sell-order-row ${sellCardClass(signal)}`} key={signal.position?.id}>
                      <div>
                        <strong>{signal.position.buy_date}</strong>
                        <small>{sellOrderSummaryText(signal)}</small>
                      </div>
                      <span>{wholeShare(signal.position.quantity)}주</span>
                      <strong>{sellOrderPriceText(signal, dashboard?.config.symbol)}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="order-board-card">
              <div className="order-board-header">
                <div>
                  <span className="signal-label">오늘의 LOC 매도 주문표</span>
                  <strong>주문 없음</strong>
                </div>
              </div>
              <div className="order-board-body">
                <p>체결된 보유 포지션이 없습니다.</p>
              </div>
            </div>
          )}
        </div>
        {locNettingPreview.needed ? (
          <div className="loc-netting-card">
            <div className="loc-netting-header">
              <div>
                <strong>자전거래 방지 주문표</strong>
                <span>매수/매도 LOC 가격이 겹쳐 퉁치기 주문으로 변환했습니다.</span>
              </div>
              <em>호가 {locNettingPreview.tickSize}</em>
            </div>
            <div className="loc-netting-tables">
              <LocNettingTable title="원주문" orders={locNettingPreview.orders} symbol={selectedSymbol} />
              <LocNettingTable title="퉁치기 주문" orders={locNettingPreview.nettedOrders} symbol={selectedSymbol} highlighted />
            </div>
          </div>
        ) : null}
      </section>

      <div className="page-grid">
        <section className="panel positions-panel">
          <div className="panel-header">
            <div>
              <h2>보유 포지션</h2>
              <span>대기 중인 LOC 매수 주문의 체결 여부와 실제 체결 수량·가격을 확인합니다.</span>
            </div>
            <span className="status-pill compact is-muted">{positions.length}건</span>
          </div>
          <div className="position-edit-list">
            {positions.length === 0 ? <div className="empty-state">보유 포지션이 없습니다.</div> : null}
            {sortedPositions.map((position) => {
              const edit = positionEdits[position.id] ?? {
                quantity: position.quantity,
                buy_price: position.buy_price,
                status: position.status.toLowerCase() === "pending" ? "pending" : "open",
              };
              const sellSignal = sellSignalByPosition.get(position.id);
              return (
                <div className="position-edit-row" key={position.id}>
                  <div className="position-summary">
                    <span>체결일</span>
                    <strong>{position.buy_date}</strong>
                    <em className={`state-badge ${positionStatusClass(edit.status)}`}>{positionStatusText(edit.status)}</em>
                  </div>
                  <div className="position-exit-policy">
                    <span>매도 LOC</span>
                    <strong>{positionSellLimitText(position, selectedSymbol)}</strong>
                    <small>{positionSellTargetText(position)}</small>
                  </div>
                  <div className="readonly-field">
                    <span>매수 LOC</span>
                    <strong>{formatOptionalMoney(position.limit_price, selectedSymbol)}</strong>
                  </div>
                  <div className={`holding-status ${holdingStatusClass(sellSignal)}`}>
                    <span>보유 기간</span>
                    <div className="holding-status-badges">{holdingStatusBadges(sellSignal)}</div>
                  </div>
                  <div className="position-edit-controls">
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
                    <button type="button" onClick={() => handleSavePosition(position.id)} disabled={saving}>
                      {position.status.toLowerCase() === "pending" ? "등록" : "수정"}
                    </button>
                  </div>
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
              <span>매수 주문은 대기 포지션으로 등록하고, 매도 체결은 선택한 보유 포지션에 기록합니다.</span>
            </div>
          </div>
          <form className="form-stack order-entry-form" onSubmit={handleManualSubmit}>
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
                      const price = sellExecutionPrice(position);
                      const quantity = wholeShare(position.quantity);
                      setManualForm((current) => ({
                        ...current,
                        position_id: String(position.id),
                        quantity,
                        price,
                        fee: estimateFee(price, quantity, dashboard?.config.fee_rate),
                        sell_reason: signal?.reason ?? current.sell_reason,
                      }));
                    }}
                  >
                    <span>{position.buy_date}</span>
                    <strong>{wholeShare(position.quantity)}주</strong>
                    <small>매수가 {formatMoney(position.buy_price, selectedSymbol)}</small>
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
          </form>
        </section>
      </div>

      <section className="panel position-history-panel">
        <div className="panel-header">
          <div>
            <h2>거래 내역</h2>
          </div>
        </div>
        <Table
          columns={positionHistoryColumns}
          rows={positionHistory}
          getRowKey={(row, index) => `${row.position_id ?? "trade"}-${row.buy_date}-${row.sell_date ?? "open"}-${index}`}
        />
      </section>
    </div>
  );
}

function LocNettingTable({
  title,
  orders,
  symbol,
  highlighted = false,
}: {
  title: string;
  orders: LocOrderInput[];
  symbol: string | null | undefined;
  highlighted?: boolean;
}) {
  return (
    <div className={`loc-netting-table ${highlighted ? "is-highlighted" : ""}`}>
      <strong>{title}</strong>
      <div className="loc-netting-rows">
        {orders.map((order, index) => (
          <div className="loc-netting-row" key={`${order.side}-${order.limitPrice}-${order.quantity}-${index}`}>
            <span className={order.side === "buy" ? "is-buy" : "is-sell"}>{order.side === "buy" ? "매수" : "매도"}</span>
            <strong>{formatMoney(String(order.limitPrice), symbol)}</strong>
            <em>{order.quantity}주</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildPositionHistoryColumns(symbol: string | null | undefined): TableColumn<PositionHistoryRow>[] {
  return [
    { key: "buy_date", header: "매수일", render: (row) => row.buy_date },
    { key: "sell_date", header: "매도일", render: (row) => row.sell_date ?? "-" },
    { key: "quantity", header: "수량", align: "right", render: (row) => `${wholeShare(row.quantity) || "0"}주` },
    { key: "entry_price", header: "매수가", align: "right", render: (row) => formatMoney(row.entry_price, symbol) },
    { key: "exit_price", header: "매도가", align: "right", render: (row) => formatOptionalMoney(row.exit_price, symbol) },
    { key: "pnl", header: "실현손익", align: "right", render: (row) => formatOptionalMoney(row.realized_pnl, symbol) },
    { key: "fee", header: "수수료", align: "right", render: (row) => formatMoney(row.fee, symbol) },
    { key: "status", header: "상태/사유", render: (row) => positionHistoryStatus(row) },
  ];
}

function buildLocNettingInputs(plan: DailyPlan | null, sellOrderRows: SellOrderRow[]): LocOrderInput[] {
  const buyOrders =
    plan?.LOC.orders?.length
      ? plan.LOC.orders.map((order) => ({
          side: "buy" as const,
          limitPrice: Number(order.limit_price),
          quantity: Number(order.quantity),
        }))
      : plan?.LOC.quantity
        ? [
            {
              side: "buy" as const,
              limitPrice: Number(plan.LOC.limit_price),
              quantity: Number(plan.LOC.quantity),
            },
          ]
        : [];

  const sellOrders = sellOrderRows
    .map((signal) => ({
      side: "sell" as const,
      limitPrice: Number(signal.sell_limit_price ?? signal.position.buy_price),
      quantity: Number(signal.position.quantity),
    }))
    .filter((order) => Number.isFinite(order.limitPrice) && order.limitPrice > 0 && order.quantity > 0);

  return [...buyOrders, ...sellOrders].filter(
    (order) => Number.isFinite(order.limitPrice) && order.limitPrice > 0 && order.quantity > 0,
  );
}

function sortLocOrdersByPriceDesc(orders: LocOrderInput[]): LocOrderInput[] {
  return [...orders].sort((left, right) => right.limitPrice - left.limitPrice);
}

function formatOptionalMoney(value: string | null | undefined, symbol?: string | null): string {
  return value ? formatMoney(value, symbol) : "-";
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
    sell_threshold_percent:
      typeof row.sell_threshold_percent === "string" || typeof row.sell_threshold_percent === "number"
        ? row.sell_threshold_percent
        : null,
    holding_days: typeof row.holding_days === "number" ? row.holding_days : null,
    max_holding_days: typeof row.max_holding_days === "number" ? row.max_holding_days : null,
    days_to_deadline: typeof row.days_to_deadline === "number" ? row.days_to_deadline : null,
    urgency: typeof row.urgency === "string" ? row.urgency : null,
  };
}

function deadlineActionText(days: number | null | undefined): string {
  if (days === null || days === undefined) return "D-";
  if (days <= 0) return "종가매도";
  return `D-${days}`;
}

function sellCardClass(signal: SellSignalRow): string {
  if (isExpiredSellOrder(signal)) return "recommendation-danger";
  if (isFilledCandidate(signal)) return "recommendation-success";
  if (signal.urgency === "near_deadline") return "recommendation-warning";
  return "";
}

function holdingStatusBadges(signal: SellSignalRow | undefined) {
  if (!signal) return <strong>-</strong>;
  const progress =
    signal.holding_days === null || signal.holding_days === undefined
      ? "-"
      : signal.holding_days === 0
        ? "당일"
        : signal.max_holding_days === null || signal.max_holding_days === undefined
          ? `${signal.holding_days}일`
          : `${signal.holding_days}/${signal.max_holding_days}`;
  return (
    <>
      <strong>{progress}</strong>
      <strong className={isCloseSellDue(signal) ? "is-danger" : undefined}>
        {deadlineActionText(signal.days_to_deadline)}
      </strong>
    </>
  );
}

function holdingStatusClass(signal: SellSignalRow | undefined): string {
  if (!signal) return "";
  if (isCloseSellDue(signal)) return "is-danger";
  if (signal.urgency === "near_deadline") return "is-warning";
  if (signal.urgency === "profit_target") return "is-success";
  return "";
}

function positionHistoryStatus(row: PositionHistoryRow): string {
  if (row.sell_reason) return translateReason(row.sell_reason);
  return translateCode(row.status.toLowerCase(), {
    pending: "대기",
    open: "보유중",
    closed: "청산",
  });
}

function positionStatusText(status: string): string {
  return translateCode(status.toLowerCase(), {
    pending: "대기",
    open: "체결",
    unfilled: "미체결",
    closed: "청산",
  });
}

function positionStatusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "open") return "is-success";
  if (normalized === "pending") return "is-warning";
  if (normalized === "unfilled") return "is-danger";
  return "";
}

function wholeShare(value: string | number | null | undefined): string {
  const number = Math.trunc(Number(value ?? 0));
  return Number.isFinite(number) && number > 0 ? String(number) : "";
}

function comparePositionByDate(left: PositionRow, right: PositionRow): number {
  const byDate = left.buy_date.localeCompare(right.buy_date);
  return byDate || left.id - right.id;
}

function compareSellOrderRow(left: SellOrderRow, right: SellOrderRow): number {
  const leftPriority = sellOrderPriority(left);
  const rightPriority = sellOrderPriority(right);
  if (leftPriority !== rightPriority) return leftPriority - rightPriority;
  const leftDeadline = normalizedDeadline(left.days_to_deadline);
  const rightDeadline = normalizedDeadline(right.days_to_deadline);
  return leftDeadline - rightDeadline || comparePositionByDate(left.position, right.position);
}

function sellOrderPriority(signal: SellSignalRow): number {
  if (isExpiredSellOrder(signal)) return 0;
  if (isFilledCandidate(signal)) return 1;
  return 2;
}

function normalizedDeadline(days: number | null | undefined): number {
  if (days === null || days === undefined) return Number.MAX_SAFE_INTEGER;
  return days;
}

function isExpiredSellOrder(signal: SellSignalRow): boolean {
  return isCloseSellDue(signal);
}

function isCloseSellDue(signal: SellSignalRow | undefined): boolean {
  return typeof signal?.days_to_deadline === "number" && signal.days_to_deadline <= 0;
}

function isFilledCandidate(signal: SellSignalRow): boolean {
  return signal.should_sell === true && signal.reason === "profit_target";
}

function positionSellLimitText(position: PositionRow, symbol: string | null | undefined): string {
  if (position.status.toLowerCase() === "pending") return "체결 후 확정";
  return formatOptionalMoney(position.sell_limit_price, symbol);
}

function positionSellTargetText(position: PositionRow): string {
  if (position.status.toLowerCase() === "pending") return "체결가 확인 후 익절 기준을 고정합니다.";
  return sellTargetText(position.sell_threshold_percent);
}
function sellOrderSummaryText(signal: SellSignalRow): string {
  return `${sellTargetText(signal.sell_threshold_percent)} · ${sellOrderDeadlineText(signal)}`;
}

function sellTargetText(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "익절 기준 -";
  const percent = Number(value);
  if (!Number.isFinite(percent)) return "익절 기준 -";
  return `익절 +${percent.toFixed(2).replace(/\.?0+$/, "")}%`;
}
function sellOrderDeadlineText(signal: SellSignalRow): string {
  if (isCloseSellDue(signal)) return "보유기간 도달: 종가매도";
  return deadlineActionText(signal.days_to_deadline);
}

function sellOrderPriceText(signal: SellSignalRow, symbol: string | null | undefined): string {
  if (isCloseSellDue(signal)) return "종가";
  return `LOC ${formatMoney(signal.sell_limit_price, symbol)}`;
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
