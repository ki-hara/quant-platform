import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { ChartRange, TradingChart } from "../types/api";

interface MarketChartProps {
  chart: TradingChart | null;
  range: ChartRange;
  onRangeChange: (range: ChartRange) => void;
}

const ranges: Array<{ key: ChartRange; label: string }> = [
  { key: "1m", label: "1개월" },
  { key: "3m", label: "3개월" },
  { key: "6m", label: "6개월" },
  { key: "1y", label: "1년" },
];

function formatChartDate(time: unknown): string {
  if (typeof time === "string") return time;
  if (typeof time === "object" && time !== null && "year" in time && "month" in time && "day" in time) {
    const value = time as { year: number; month: number; day: number };
    return `${value.year}-${String(value.month).padStart(2, "0")}-${String(value.day).padStart(2, "0")}`;
  }
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10);
  return "";
}

export function MarketChart({ chart, range, onRangeChange }: MarketChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || !chart || chart.candles.length === 0) return undefined;

    const instance: IChartApi = createChart(containerRef.current, {
      height: 360,
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
    const candles: ISeriesApi<"Candlestick"> = instance.addCandlestickSeries({
      upColor: "#24745a",
      downColor: "#b54b4b",
      borderVisible: false,
      wickUpColor: "#24745a",
      wickDownColor: "#b54b4b",
    });
    const volume = instance.addHistogramSeries({
      color: "rgba(74, 95, 128, 0.32)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    candles.setData(
      chart.candles.map((row) => ({
        time: row.date,
        open: Number(row.open),
        high: Number(row.high),
        low: Number(row.low),
        close: Number(row.close),
      })),
    );
    volume.setData(
      chart.candles.map((row) => ({
        time: row.date,
        value: Number(row.volume),
        color: Number(row.close) >= Number(row.open) ? "rgba(36, 116, 90, 0.28)" : "rgba(181, 75, 75, 0.28)",
      })),
    );
    candles.createPriceLine({
      price: Number(chart.LOC.value),
      color: "#4a5f80",
      lineStyle: 2,
      lineWidth: 2,
      axisLabelVisible: true,
      title: "LOC",
    });
    candles.setMarkers(
      [...chart.trade_markers].sort((left, right) => left.date.localeCompare(right.date)).map((marker) => ({
        time: marker.date,
        position: marker.kind === "buy" ? "belowBar" : "aboveBar",
        color: marker.kind === "buy" ? "#24745a" : "#b54b4b",
        shape: marker.kind === "buy" ? "arrowUp" : "arrowDown",
        text: marker.kind === "buy" ? "매수" : "매도",
      })),
    );
    instance.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) instance.applyOptions({ width: containerRef.current.clientWidth });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      instance.remove();
    };
  }, [chart]);

  return (
    <section className="panel chart-panel">
      <div className="panel-header">
        <div>
          <h2>종목 차트</h2>
          <span>{chart?.LOC.as_of ? `${chart.LOC.as_of} LOC ${chart.LOC.value}` : "LOC 대기"}</span>
        </div>
        <div className="range-control" role="group" aria-label="차트 기간">
          {ranges.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={range === item.key}
              onClick={() => onRangeChange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      {chart && chart.candles.length > 0 ? (
        <div className="chart chart-large" ref={containerRef} />
      ) : (
        <div className="chart-empty">차트 데이터가 없습니다.</div>
      )}
    </section>
  );
}
