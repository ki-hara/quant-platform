import { createChart, type IChartApi } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { TradingChart, TrendFilter } from "../types/api";

interface CciChartProps {
  chart: TradingChart | null;
  trendFilter: TrendFilter | null;
}

const lineColors = ["#2f7d5c", "#b45f2a", "#4a5f80", "#8a6f2a", "#7b5aa6"];

function formatChartDate(time: unknown): string {
  if (typeof time === "string") return time;
  if (typeof time === "object" && time !== null && "year" in time && "month" in time && "day" in time) {
    const value = time as { year: number; month: number; day: number };
    return `${value.year}-${String(value.month).padStart(2, "0")}-${String(value.day).padStart(2, "0")}`;
  }
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10);
  return "";
}

export function CciChart({ chart, trendFilter }: CciChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const series = chart?.cci.series ?? [];
  const hasData = series.some((row) => row.points.length > 0);

  useEffect(() => {
    if (!containerRef.current || !chart || !hasData) return undefined;

    const instance: IChartApi = createChart(containerRef.current, {
      height: 220,
      layout: { background: { color: "#ffffff" }, textColor: "#2b3036" },
      grid: { vertLines: { color: "#eef0f2" }, horzLines: { color: "#eef0f2" } },
      rightPriceScale: { borderColor: "#d9dde3" },
      timeScale: {
        borderColor: "#d9dde3",
        tickMarkFormatter: formatChartDate,
      },
      localization: {
        timeFormatter: formatChartDate,
      },
    });

    series.forEach((row, index) => {
      const line = instance.addLineSeries({
        color: lineColors[index % lineColors.length],
        lineWidth: 2,
        priceLineVisible: false,
        title: row.symbol,
      });
      line.setData(row.points.map((point) => ({ time: point.date, value: Number(point.value) })));
      if (index === 0) {
        line.createPriceLine({
          price: 0,
          color: "#9aa1a9",
          lineStyle: 2,
          lineWidth: 1,
          axisLabelVisible: true,
          title: "0",
        });
      }
    });
    instance.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) instance.applyOptions({ width: containerRef.current.clientWidth });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      instance.remove();
    };
  }, [chart, hasData, series]);

  return (
    <section className="panel chart-panel trend-cci-panel">
      <div className="panel-header">
        <div>
          <h2>추세 필터 / CCI 주봉 30</h2>
          <span>0 이상 상승장 / 0 미만 하락장 후보</span>
        </div>
        <div className="chart-legend">
          {series.map((row, index) => (
            <span key={row.symbol}>
              <i style={{ background: lineColors[index % lineColors.length] }} />
              {row.symbol}
            </span>
          ))}
        </div>
      </div>

      <TrendSummary trendFilter={trendFilter} />

      {hasData ? <div className="chart chart-rsi" ref={containerRef} /> : <div className="chart-empty">CCI 데이터가 없습니다.</div>}
    </section>
  );
}

function TrendSummary({ trendFilter }: { trendFilter: TrendFilter | null }) {
  if (!trendFilter || trendFilter.symbols.length === 0) {
    return <div className="empty-state compact">추세 데이터가 없습니다.</div>;
  }
  return (
    <div className="trend-summary-block">
      <div className="trend-symbol-list">
        {trendFilter.symbols.map((row) => (
          <div className={`trend-symbol-row ${trendStatusClass(row.status)}`} key={row.symbol}>
            <div>
              <strong>{row.symbol}</strong>
              <span>{row.label}</span>
            </div>
            <div>
              <strong>{formatCci(row.latest_cci)}</strong>
              <span>{row.streak > 0 ? `${row.streak}주 연속` : row.as_of ?? "대기"}</span>
            </div>
          </div>
        ))}
      </div>
      <p className="trend-summary">{trendFilter.summary}</p>
    </div>
  );
}

function formatCci(value: string | number | null | undefined): string {
  if (value == null || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function trendStatusClass(status: string): string {
  if (status === "bearish_confirmed") return "is-bearish";
  if (status === "bearish_candidate") return "is-warning";
  if (status === "bullish_candidate") return "is-watch";
  if (status === "bullish_confirmed") return "is-bullish";
  return "is-muted";
}
