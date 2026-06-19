import { Play, RotateCcw } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type { DashboardResponse, PositionRow, SignalExecutionRequest } from "../types/api";
import { todayIso } from "../utils/format";

interface SignalPanelProps {
  dashboard: DashboardResponse | null;
  onExecute: (request: SignalExecutionRequest) => Promise<void>;
  executing?: boolean;
}

const defaultForm = {
  side: "buy" as "buy" | "sell",
  trade_date: todayIso(),
  quantity: "1",
  price: "",
  fee: "0",
  mode: "safe",
  position_id: "",
  sell_reason: "",
};

export function SignalPanel({ dashboard, onExecute, executing = false }: SignalPanelProps) {
  const [form, setForm] = useState(defaultForm);
  const [expanded, setExpanded] = useState(false);

  const positions = dashboard?.open_positions ?? [];
  const latestClose = dashboard?.latest_price?.close ?? "";
  const signals = dashboard?.signals;

  const sellSignalCount = useMemo(() => {
    return Array.isArray(signals?.sell_signals) ? signals.sell_signals.length : 0;
  }, [signals?.sell_signals]);

  function prefill(side: "buy" | "sell", position?: PositionRow) {
    setExpanded(true);
    setForm((current) => ({
      ...current,
      side,
      price: latestClose || current.price,
      quantity: position?.quantity ?? current.quantity,
      position_id: position ? String(position.id) : "",
      sell_reason: side === "sell" ? "manual_signal" : "",
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onExecute({
      side: form.side,
      trade_date: form.trade_date,
      quantity: form.quantity,
      price: form.price,
      fee: form.fee,
      source: "signal_execution",
      mode: form.side === "buy" ? form.mode : undefined,
      position_id: form.side === "sell" && form.position_id ? Number(form.position_id) : null,
      sell_reason: form.side === "sell" ? form.sell_reason || "manual_signal" : null,
    });
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>오늘의 신호</h2>
          <span>{signals?.available ? "최신 시장 데이터 기준" : "신호 데이터 대기"}</span>
        </div>
        <button
          className="icon-button"
          type="button"
          title="입력 초기화"
          onClick={() => setForm({ ...defaultForm, trade_date: todayIso(), price: latestClose })}
        >
          <RotateCcw aria-hidden="true" size={16} />
        </button>
      </div>

      {!dashboard ? (
        <div className="empty-state">전략 설정을 선택하면 신호가 표시됩니다.</div>
      ) : (
        <div className="signal-grid">
          <div className="signal-card">
            <div>
              <span className="signal-label">오늘의 매수</span>
              <strong>{signals?.should_buy ? "매수 조건 충족" : "대기"}</strong>
              <p>{signals?.buy_reason ?? signals?.reason ?? "매수 신호 없음"}</p>
            </div>
            <button type="button" onClick={() => prefill("buy")} disabled={!signals?.available}>
              <Play aria-hidden="true" size={16} />
              실행
            </button>
          </div>

          <div className="signal-card">
            <div>
              <span className="signal-label">오늘의 매도</span>
              <strong>{sellSignalCount > 0 ? `${sellSignalCount}건` : "대기"}</strong>
              <p>{sellSignalCount > 0 ? "매도 후보 포지션이 있습니다." : "매도 신호 없음"}</p>
            </div>
            <button
              type="button"
              onClick={() => prefill("sell", positions[0])}
              disabled={!signals?.available || positions.length === 0}
            >
              <Play aria-hidden="true" size={16} />
              실행
            </button>
          </div>
        </div>
      )}

      {expanded ? (
        <form className="execution-form" onSubmit={handleSubmit}>
          <label>
            구분
            <select
              value={form.side}
              onChange={(event) =>
                setForm((current) => ({ ...current, side: event.target.value as "buy" | "sell" }))
              }
            >
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
          </label>
          <label>
            거래일
            <input
              type="date"
              value={form.trade_date}
              onChange={(event) => setForm((current) => ({ ...current, trade_date: event.target.value }))}
              required
            />
          </label>
          <label>
            수량
            <input
              value={form.quantity}
              onChange={(event) => setForm((current) => ({ ...current, quantity: event.target.value }))}
              required
            />
          </label>
          <label>
            가격
            <input
              value={form.price}
              onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              required
            />
          </label>
          <label>
            수수료
            <input
              value={form.fee}
              onChange={(event) => setForm((current) => ({ ...current, fee: event.target.value }))}
              required
            />
          </label>
          {form.side === "sell" ? (
            <>
              <label>
                포지션
                <select
                  value={form.position_id}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, position_id: event.target.value }))
                  }
                  required
                >
                  <option value="">선택</option>
                  {positions.map((position) => (
                    <option key={position.id} value={position.id}>
                      #{position.id} / {position.quantity}주
                    </option>
                  ))}
                </select>
              </label>
              <label>
                매도 사유
                <input
                  value={form.sell_reason}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, sell_reason: event.target.value }))
                  }
                />
              </label>
            </>
          ) : (
            <label>
              모드
              <select
                value={form.mode}
                onChange={(event) => setForm((current) => ({ ...current, mode: event.target.value }))}
              >
                <option value="safe">안정</option>
                <option value="aggressive">공격</option>
              </select>
            </label>
          )}
          <button type="submit" disabled={executing}>
            {executing ? "실행 중" : "실행"}
          </button>
        </form>
      ) : null}
    </section>
  );
}
