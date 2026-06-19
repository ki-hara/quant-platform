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

export function translateSide(side: string): string {
  if (side === "buy") return "매수";
  if (side === "sell") return "매도";
  return side;
}

export function translateStatus(status: string): string {
  const map: Record<string, string> = {
    open: "보유",
    closed: "청산",
    completed: "완료",
    failed: "실패",
    running: "실행 중",
  };
  return map[status] ?? status;
}
