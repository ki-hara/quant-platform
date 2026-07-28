import { useEffect, useState } from "react";
import {
  getIntegratedOrders,
  updateIntegratedOrderPreference,
} from "../api/integratedOrders";
import type { IntegratedOrder, IntegratedOrdersResponse } from "../types/api";

type ViewMode = "original" | "netted";

export function IntegratedOrdersPage() {
  const [data, setData] = useState<IntegratedOrdersResponse | null>(null);
  const [mode, setMode] = useState<ViewMode>("original");
  const [error, setError] = useState("");
  const [workingId, setWorkingId] = useState<number | null>(null);

  function load(signal?: AbortSignal) {
    return getIntegratedOrders(signal).then(setData).catch((caught) => {
      if ((caught as Error).name !== "AbortError") {
        setError(caught instanceof Error ? caught.message : "통합 주문을 불러오지 못했습니다.");
      }
    });
  }

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, []);

  async function toggle(configId: number, included: boolean) {
    try {
      setWorkingId(configId);
      setError("");
      await updateIntegratedOrderPreference(configId, { included });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "포함 설정을 변경하지 못했습니다.");
    } finally {
      setWorkingId(null);
    }
  }

  const orders = mode === "original" ? data?.original_orders : data?.netted_orders;

  return (
    <section className="integrated-orders-page">
      <div className="panel integrated-preferences">
        <div className="panel-header">
          <div>
            <h2>전략 통합 주문</h2>
            <span>전략 계산과 포지션에는 영향을 주지 않는 별도 표시 설정입니다.</span>
          </div>
        </div>
        {error ? <div className="notice notice-error">{error}</div> : null}
        <div className="preference-list">
          {data?.preferences.map((preference) => (
            <label className="preference-row" key={preference.strategy_config_id}>
              <div>
                <strong>{preference.strategy_name}</strong>
                <span>{preference.symbol} · {strategyLabel(preference.strategy_type)}</span>
              </div>
              <span className="toggle-label">
                통합 주문 포함
                <input
                  type="checkbox"
                  checked={preference.included}
                  disabled={workingId === preference.strategy_config_id}
                  onChange={(event) => void toggle(preference.strategy_config_id, event.target.checked)}
                />
              </span>
            </label>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="integrated-toolbar">
          <div className="segmented-control" role="group" aria-label="주문 표시 방식">
            <button type="button" className={mode === "original" ? "active" : ""} onClick={() => setMode("original")}>
              일반 주문
            </button>
            <button type="button" className={mode === "netted" ? "active" : ""} onClick={() => setMode("netted")}>
              퉁치기 주문
            </button>
          </div>
          <span className="read-only-badge">읽기 전용</span>
        </div>
        <div className="integrated-order-list">
          {orders?.map((order, index) => (
            <OrderRow order={order} key={`${order.symbol}-${order.side}-${order.limit_price}-${index}`} />
          ))}
          {data && orders?.length === 0 ? <div className="empty-state">표시할 주문이 없습니다.</div> : null}
        </div>
      </div>
    </section>
  );
}

function OrderRow({ order }: { order: IntegratedOrder }) {
  return (
    <details className="integrated-order-row">
      <summary>
        <span className={`order-side ${order.side}`}>{order.side === "buy" ? "매수" : "매도"}</span>
        <strong>{order.symbol}</strong>
        <span className="order-price">${Number(order.limit_price).toFixed(2)}</span>
        <span>{order.quantity.toLocaleString()}주</span>
      </summary>
      <div className="source-breakdown">
        {order.sources.map((source, index) => (
          <div key={`${source.strategy_config_id}-${source.position_id ?? "buy"}-${index}`}>
            <span>{source.strategy_name}</span>
            <span>{source.tier ? `${source.tier}티어` : "일반"}</span>
            <strong>{source.quantity.toLocaleString()}주</strong>
          </div>
        ))}
      </div>
    </details>
  );
}

function strategyLabel(strategyType: string) {
  return strategyType === "radar0458_pro" ? "레이더0458 Pro" : "Dynamic Wave";
}
