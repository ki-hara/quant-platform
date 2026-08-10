import { Clipboard, RefreshCw } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  clearGoldToiletManualOpen,
  getGoldToiletOrderSheet,
  setGoldToiletManualOpen,
  updateGoldToiletAccount,
  updateGoldToiletOrderSheet,
  type GoldToiletOrderResponse,
} from "../api/goldToiletOrders";
import { formatMoney, marketDateIso } from "../utils/format";
import {
  goldToiletOrderResultItems,
  GOLD_TOILET_OPEN_POLL_INTERVAL_MS,
  orderCopyText,
  shouldPollForOpen,
} from "../utils/goldToiletOrders";

export function GoldToiletOrdersPage() {
  const [orderDate, setOrderDate] = useState(() => marketDateIso("SOXL"));
  const [capital, setCapital] = useState("");
  const [cash, setCash] = useState("");
  const [entryPercent, setEntryPercent] = useState("1.49");
  const [allocationPercent, setAllocationPercent] = useState("22.50");
  const [locPercent, setLocPercent] = useState("-9.34");
  const [manualOpen, setManualOpen] = useState("");
  const [data, setData] = useState<GoldToiletOrderResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await getGoldToiletOrderSheet(orderDate, signal);
      setData(response);
      if (response.account) {
        setCapital(response.account.capital);
        setCash(response.account.cash);
      }
      if (response.sheet) {
        setEntryPercent(response.sheet.entry_percent);
        setAllocationPercent(response.sheet.allocation_percent);
        setLocPercent(response.sheet.loc_percent);
      }
      setError("");
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        setError(caught instanceof Error ? caught.message : "주문표를 불러오지 못했습니다.");
      }
    }
  }, [orderDate]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!data || !shouldPollForOpen(orderDate, data.sheet?.provider_market_open)) return;
    const timer = window.setInterval(() => void load(), GOLD_TOILET_OPEN_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [data, load, orderDate]);

  async function saveAccount(event: FormEvent) {
    event.preventDefault();
    await runSave(async () => {
      await updateGoldToiletAccount({ capital, cash });
      await load();
      setMessage("운용 원본과 주문 가능 현금을 저장했습니다.");
    });
  }

  async function saveSheet(event: FormEvent) {
    event.preventDefault();
    await runSave(async () => {
      await updateGoldToiletOrderSheet(orderDate, {
        entry_percent: entryPercent,
        allocation_percent: allocationPercent,
        loc_percent: locPercent,
      });
      await load();
      setMessage("주문표를 저장하고 다시 계산했습니다.");
    });
  }

  async function applyManualOpen(event: FormEvent) {
    event.preventDefault();
    await runSave(async () => {
      const response = await setGoldToiletManualOpen(orderDate, manualOpen);
      setData(response);
      setManualOpen("");
      setMessage("직접 입력한 시가를 계산에 강제 적용했습니다.");
    });
  }

  async function resetManualOpen() {
    await runSave(async () => {
      const response = await clearGoldToiletManualOpen(orderDate);
      setData(response);
      setManualOpen("");
      setMessage("직접 입력값을 해제하고 자동 시가로 되돌렸습니다.");
    });
  }

  async function runSave(action: () => Promise<void>) {
    try {
      setWorking(true);
      setError("");
      setMessage("");
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "저장하지 못했습니다.");
    } finally {
      setWorking(false);
    }
  }

  const calculation = data?.calculation;
  const sheet = data?.sheet;
  const effectiveOpen = sheet?.effective_market_open;
  const providerOpen = sheet?.provider_market_open;
  const manualOverrideAllowed = data?.manual_open_allowed ?? false;
  const orderResults = goldToiletOrderResultItems(calculation ?? null);

  return (
    <section className="gold-toilet-page">
      <div className="gold-toilet-intro">
        <div>
          <span className="gold-kicker">SOXL · 메리츠증권 주문 보조</span>
          <h2>시가가 확인되면 세 숫자만 바로 주문하세요</h2>
          <p>돌파 매수가와 LOC 매수가에는 같은 수량을 사용하며, 수량은 더 낮은 LOC 가격을 기준으로 계산합니다.</p>
        </div>
        <button className="ghost-button" type="button" onClick={() => void load()} disabled={working}>
          <RefreshCw size={16} aria-hidden="true" /> 새로고침
        </button>
      </div>

      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice">{message}</div> : null}

      <div className="gold-toilet-input-grid">
        <form className="panel gold-input-panel" onSubmit={saveAccount}>
          <div className="panel-header"><div><h3>운용 금액</h3><span>손익 반영 전날 마감 금액입니다.</span></div></div>
          <label>운용 원본 (USD)<input type="number" min="0.01" step="0.01" value={capital} onChange={(event) => setCapital(event.target.value)} required /></label>
          <label>주문 가능 현금 (USD)<input type="number" min="0" step="0.01" value={cash} onChange={(event) => setCash(event.target.value)} required /></label>
          <button type="submit" disabled={working}>금액 저장</button>
        </form>

        <form className="panel gold-input-panel" onSubmit={saveSheet}>
          <div className="panel-header"><div><h3>주문표 입력</h3><span>Quanters 주문표의 백분율만 입력하세요. 시가는 여기서 변경되지 않습니다.</span></div></div>
          <div className="gold-sheet-grid">
            <label>주문일<input type="date" value={orderDate} onChange={(event) => setOrderDate(event.target.value)} required /></label>
            <label>돌파 진입 (%)<input type="number" step="0.01" value={entryPercent} onChange={(event) => setEntryPercent(event.target.value)} required /></label>
            <label>매수 비중 (%)<input type="number" min="0.01" max="100" step="0.01" value={allocationPercent} onChange={(event) => setAllocationPercent(event.target.value)} required /></label>
            <label>LOC 시가 대비 (%)<input type="number" step="0.01" value={locPercent} onChange={(event) => setLocPercent(event.target.value)} required /></label>
          </div>
          <button type="submit" disabled={working}>주문표 저장 · 계산</button>
        </form>
      </div>

      <OpenStatus data={data} orderDate={orderDate} />
      <article className="gold-allocation-card" aria-live="polite">
        <div>
          <span>매수 비중 금액</span>
          <small>시가 없이 미리 확정</small>
        </div>
        <strong>{data?.allocation_amount ? formatMoney(data.allocation_amount, "SOXL") : "-"}</strong>
      </article>


      <article className={`gold-market-open-card ${effectiveOpen ? "ready" : "waiting"}`}>
        <div>
          <span>계산 적용 시가</span>
          <strong>{effectiveOpen ? `$${Number(effectiveOpen).toFixed(2)}` : "조회 대기"}</strong>
        </div>
        <div className="gold-market-open-meta">
          <b>SOXL</b>
          <span>자동 시가 {providerOpen ? `$${Number(providerOpen).toFixed(2)}` : "조회 중"}</span>
          <span>직접 입력 {sheet?.manual_market_open ? `$${Number(sheet.manual_market_open).toFixed(2)}` : "미적용"}</span>
          {sheet?.provider_open_observed_at ? <time>일봉 시가 수신 · {formatObservedAt(sheet.provider_open_observed_at)}</time> : null}
        </div>
      </article>

      <form className="panel gold-manual-open-panel" onSubmit={applyManualOpen}>
        <div>
          <h3>시가 직접 입력</h3>
          <p>뉴욕 정규장 시작 후 사용할 수 있습니다. 직접 입력 중에도 자동 시가 조회는 계속됩니다.</p>
        </div>
        <label>
          강제 적용 시가
          <input
            type="number"
            min="0.01"
            step="0.001"
            value={manualOpen}
            onChange={(event) => setManualOpen(event.target.value)}
            placeholder={manualOverrideAllowed ? "예: 131.50" : "뉴욕 정규장 시작 후 입력 가능"}
            disabled={!manualOverrideAllowed || working}
            required
          />
        </label>
        <button type="submit" disabled={!manualOverrideAllowed || !manualOpen || working}>직접 입력값 강제 적용</button>
        {sheet?.manual_market_open ? <button className="ghost-button" type="button" onClick={() => void resetManualOpen()} disabled={working}>자동 시가로 되돌리기</button> : null}
      </form>

      {calculation ? (
        <div className="gold-order-results" aria-live="polite">
          {orderResults.map((item) => (
            <OrderResult
              key={item.label}
              {...item}
              featured={item.kind === "quantity"}
            />
          ))}
        </div>
      ) : null}

      {calculation ? (
        <div className={calculation.cash_warning ? "notice notice-error" : "gold-cash-summary"}>
          두 주문 예약 필요 현금 {formatMoney(calculation.required_reservation_cash, "SOXL")}
          {calculation.cash_warning ? " · 현재 현금으로 두 주문을 동시에 예약하기 부족합니다." : " · 두 주문 동시 예약 가능"}
        </div>
      ) : null}
    </section>
  );
}

function OpenStatus({ data, orderDate }: { data: GoldToiletOrderResponse | null; orderDate: string }) {
  if (!data?.sheet) {
    return <div className="open-status waiting"><span className="status-dot" />먼저 주문표를 저장하세요.</div>;
  }
  if (data.open_status === "ready") {
    const sheet = data.sheet;
    return (
      <div className="open-status ready">
        <span className="status-dot" />
        SOXL 시가 ${Number(sheet.effective_market_open).toFixed(2)} 확정 · {sourceLabel(sheet.effective_open_source)}
      </div>
    );
  }
  if (data.open_status === "failed") {
    return (
      <div className="open-status failed">
        <span className="status-dot" />
        자동 시가 검증 실패 · {failureLabel(data.open_failure_reason)} · 1초마다 계속 재조회합니다.
      </div>
    );
  }
  return (
    <div className="open-status waiting">
      <span className="status-dot" />
      {orderDate} 09:30(뉴욕) 당일 일봉 시가를 기다리는 중입니다. 1초마다 확인합니다.
    </div>
  );
}

function OrderResult({ label, value, copyValue, kind, featured = false }: { label: string; value: string; copyValue?: string | number; kind: "price" | "quantity"; featured?: boolean }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    if (copyValue === undefined) return;
    await navigator.clipboard.writeText(orderCopyText(kind, copyValue));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }
  return (
    <article className={`gold-order-card${featured ? " featured" : ""}`}>
      <span>{label}</span><strong>{value}</strong>
      <button type="button" onClick={() => void copy()} disabled={copyValue === undefined}><Clipboard size={16} aria-hidden="true" />{copied ? "복사됨" : "복사"}</button>
    </article>
  );
}

function sourceLabel(source: string | null) {
  return source === "manual" ? "직접 입력 강제 적용" : "Yahoo 당일 일봉 시가";
}

function failureLabel(reason: string | null) {
  const labels: Record<string, string> = {
    regular_session_not_started: "정규장 개시 대기",
    opening_bar_not_available: "당일 일봉 미수신",
    opening_bar_values_missing: "당일 일봉 값 누락",
    opening_bar_values_invalid: "당일 일봉 값 오류",
    opening_bar_ohlc_invalid: "당일 일봉 OHLC 검증 실패",
    opening_price_payload_invalid: "시세 응답 형식 오류",
    opening_price_provider_unavailable: "시세 제공자 연결 실패",
  };
  return reason ? labels[reason] ?? reason : "원인 확인 중";
}

function formatObservedAt(value: string) {
  const utcValue = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  return new Date(utcValue).toLocaleString("ko-KR");
}
