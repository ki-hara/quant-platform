import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { TradingChart } from "../types/api";
import { translateMode } from "../utils/format";

interface RsiChartProps {
  chart: TradingChart | null;
}

export function RsiChart({ chart }: RsiChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || !chart || chart.rsi.points.length === 0) return undefined;

    const instance: IChartApi = createChart(containerRef.current, {
      height: 220,
      layout: { background: { color: "#ffffff" }, textColor: "#2b3036" },
      grid: { vertLines: { color: "#eef0f2" }, horzLines: { color: "#eef0f2" } },
      rightPriceScale: { borderColor: "#d9dde3" },
      timeScale: { borderColor: "#d9dde3" },
    });
    const rsi: ISeriesApi<"Line"> = instance.addLineSeries({
      color: "#4a5f80",
      lineWidth: 2,
      priceLineVisible: false,
    });
    rsi.setData(chart.rsi.points.map((point) => ({ time: point.date, value: Number(point.value) })));
    chart.rsi.guides.forEach((guide) => {
      rsi.createPriceLine({
        price: Number(guide),
        color: "#c8ced7",
        lineStyle: 2,
        lineWidth: 1,
        axisLabelVisible: true,
        title: guide,
      });
    });
    rsi.setMarkers(
      chart.mode_markers.map((marker) => ({
        time: marker.date,
        position: marker.mode === "aggressive" ? "belowBar" : "aboveBar",
        color: marker.mode === "aggressive" ? "#d17a22" : "#24745a",
        shape: marker.mode === "aggressive" ? "arrowUp" : "arrowDown",
        text: `${translateMode(marker.mode)} ${marker.rule_code ?? ""}`.trim(),
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
          <h2>QQQ 주간 RSI</h2>
          <span>35 / 40 / 50 / 60 / 65 기준선</span>
        </div>
      </div>
      {chart && chart.rsi.points.length > 0 ? (
        <div className="chart chart-rsi" ref={containerRef} />
      ) : (
        <div className="chart-empty">RSI 데이터가 없습니다.</div>
      )}
    </section>
  );
}
