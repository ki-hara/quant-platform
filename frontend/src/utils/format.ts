export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 2,
  }).format(number);
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
    price_above_threshold: "가격이 매수 기준보다 높음",
    aod_threshold: "매수 기준 충족",
    split_limit_reached: "분할 매수 한도 도달",
    quantity_zero: "계산 수량 0",
    insufficient_cash: "현금 부족",
    profit_target: "목표 수익 도달",
    max_holding_period: "최대 보유 기간 도달",
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
