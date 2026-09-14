export function modeRuleDescription(code: string | null | undefined): string {
  const descriptions: Record<string, string> = {
    A1: "RSI 50 상향 돌파",
    A2: "이전 RSI 50~60 구간에서 상승",
    A3: "이전 RSI 35 이하에서 상승",
    S1: "이전 RSI 65 이상에서 하락",
    S2: "이전 RSI 40~50 구간에서 하락",
    S3: "RSI 50 하향 돌파",
  };
  return code ? `${code} · ${descriptions[code] ?? code}` : "유지 · 전환 조건 없음";
}
