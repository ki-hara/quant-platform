import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { BacktestDailySnapshot } from "../types/api";

interface BacktestChartProps {
  rows: BacktestDailySnapshot[];
}

export function BacktestChart({ rows }: BacktestChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return undefined;

    const chart: IChartApi = createChart(containerRef.current, {
      height: 280,
      layout: {
        background: { color: "#ffffff" },
        textColor: "#333730",
      },
      grid: {
        vertLines: { color: "#eef0eb" },
        horzLines: { color: "#eef0eb" },
      },
      rightPriceScale: {
        borderColor: "#d7d9d2",
      },
      timeScale: {
        borderColor: "#d7d9d2",
      },
    });

    const assetSeries: ISeriesApi<"Line"> = chart.addLineSeries({
      color: "#2f6b4f",
      lineWidth: 2,
      priceLineVisible: false,
      title: "총자산",
    });
    const drawdownSeries: ISeriesApi<"Area"> = chart.addAreaSeries({
      topColor: "rgba(176, 74, 74, 0.24)",
      bottomColor: "rgba(176, 74, 74, 0.03)",
      lineColor: "#b04a4a",
      lineWidth: 1,
      priceLineVisible: false,
      title: "MDD",
    });

    assetSeries.setData(
      rows.map((row) => ({
        time: row.date,
        value: Number(row.total_asset),
      })),
    );
    drawdownSeries.setData(
      rows.map((row) => ({
        time: row.date,
        value: Number(row.drawdown),
      })),
    );

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [rows]);

  if (rows.length === 0) {
    return <div className="chart-empty">백테스트 실행 후 자산 곡선이 표시됩니다.</div>;
  }

  return <div className="chart" ref={containerRef} />;
}
