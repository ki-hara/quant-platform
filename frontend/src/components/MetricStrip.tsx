export interface MetricItem {
  label: string;
  value: string;
  helper?: string;
  tone?: "neutral" | "positive" | "negative" | "warning";
}

interface MetricStripProps {
  metrics: MetricItem[];
}

export function MetricStrip({ metrics }: MetricStripProps) {
  if (metrics.length === 0) {
    return <div className="empty-state">데이터 없음</div>;
  }

  return (
    <div className="metric-strip">
      {metrics.map((metric) => (
        <div className="metric" key={metric.label} data-tone={metric.tone ?? "neutral"}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          {metric.helper ? <small>{metric.helper}</small> : null}
        </div>
      ))}
    </div>
  );
}
