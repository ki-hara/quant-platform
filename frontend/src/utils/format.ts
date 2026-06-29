export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function marketDateIso(symbol: string | null | undefined, now = new Date()): string {
  return dateInTimeZone(now, isKoreanSymbol(symbol) ? "Asia/Seoul" : "America/New_York");
}

export function isKoreanSymbol(symbol: string | null | undefined): boolean {
  if (!symbol) return false;
  const normalized = String(symbol).trim().toUpperCase();
  const compact = normalized.replace(/^(KRX|KOSPI|KOSDAQ):/, "").replace(/^A/, "");
  return compact.endsWith(".KS") || compact.endsWith(".KQ") || /^[0-9A-Z]{6}$/.test(compact);
}

function dateInTimeZone(value: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function formatMoney(value: string | number | null | undefined, symbol?: string | null): string {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  const formatted = new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 2,
  }).format(number);
  const currency = currencyForSymbol(symbol);
  return currency ? `${formatted} ${currency}` : formatted;
}

export function currencyForSymbol(symbol: string | null | undefined): "USD" | "KRW" | null {
  if (!symbol) return null;
  if (isKoreanSymbol(symbol)) return "KRW";
  return "USD";
}

export function formatDecimal(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return number.toFixed(digits);
}

export function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return `${(number * 100).toFixed(2)}%`;
}

export function translateMode(mode: string | null | undefined): string {
  return translateCode(mode, {
    safe: "안전",
    aggressive: "공세",
  });
}

export function translateStrategyType(strategyType: string | null | undefined): string {
  return translateCode(strategyType, {
    dynamic_wave: "동파법",
  });
}

export function translateReason(reason: string | null | undefined): string {
  return translateCode(reason, {
    loc_threshold: "LOC 매수 기준 충족",
    price_above_threshold: "종가가 LOC 지정가보다 높음",
    split_limit_reached: "분할 매수 한도 도달",
    quantity_zero: "계산 수량 0",
    insufficient_cash: "현금 부족",
    profit_target: "목표 수익 도달",
    max_holding_period: "최대 보유 거래일 도달",
    sell_condition_waiting: "매도 조건 대기",
    portfolio_unavailable: "포트폴리오 데이터 없음",
    market_data_unavailable: "시장 데이터 부족",
    manual_signal: "수동 신호",
  });
}

export function translateSource(source: string | null | undefined): string {
  return translateCode(source, {
    signal_execution: "신호 실행",
    manual: "수동",
    correction: "보정",
    backtest: "백테스트",
  });
}

export function translateSide(side: string | null | undefined): string {
  return translateCode(side, {
    buy: "매수",
    sell: "매도",
  });
}

export function translateStatus(status: string | null | undefined): string {
  return translateCode(status, {
    open: "보유",
    closed: "청산",
    completed: "완료",
    failed: "실패",
    running: "실행 중",
  });
}

export function translateCode(
  value: string | null | undefined,
  dictionary: Record<string, string>,
): string {
  if (value === null || value === undefined || value === "") return "-";
  return dictionary[value] ?? value;
}
