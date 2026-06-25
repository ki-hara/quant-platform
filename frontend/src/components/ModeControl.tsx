import { Check, ShieldCheck, Zap } from "lucide-react";
import type { ModeRecommendation, StrategyMode } from "../types/api";
import { formatDecimal, translateMode } from "../utils/format";

interface ModeControlProps {
  mode: ModeRecommendation | null;
  loading?: boolean;
  onSetMode: (mode: StrategyMode) => Promise<void>;
  onApplyRecommendation: () => Promise<void>;
}

export function ModeControl({
  mode,
  loading = false,
  onSetMode,
  onApplyRecommendation,
}: ModeControlProps) {
  return (
    <section className="panel mode-panel">
      <div className="panel-header">
        <div>
          <h2>운용 모드</h2>
          <span>{mode?.effective_week ? `${mode.effective_week} 적용 추천` : "추천 계산 대기"}</span>
        </div>
      </div>

      <div className="segmented-control" role="group" aria-label="확정 운용 모드">
        <button
          type="button"
          aria-pressed={mode?.confirmed_mode === "safe"}
          disabled={loading}
          onClick={() => onSetMode("safe")}
        >
          <ShieldCheck aria-hidden="true" size={16} />
          안전
        </button>
        <button
          type="button"
          aria-pressed={mode?.confirmed_mode === "aggressive"}
          disabled={loading}
          onClick={() => onSetMode("aggressive")}
        >
          <Zap aria-hidden="true" size={16} />
          공세
        </button>
      </div>

      <dl className="detail-grid">
        <div>
          <dt>확정 모드</dt>
          <dd>{translateMode(mode?.confirmed_mode)}</dd>
        </div>
        <div>
          <dt>추천 모드</dt>
          <dd>{translateMode(mode?.recommended_mode)}</dd>
        </div>
        <div>
          <dt>이전 RSI</dt>
          <dd>{formatDecimal(mode?.previous_rsi, 2)}</dd>
        </div>
        <div>
          <dt>현재 RSI</dt>
          <dd>{formatDecimal(mode?.current_rsi, 2)}</dd>
        </div>
        <div>
          <dt>규칙</dt>
          <dd>{mode?.rule_code ?? "-"}</dd>
        </div>
        <div>
          <dt>기준일</dt>
          <dd>{mode?.data_as_of ?? "-"}</dd>
        </div>
      </dl>

      {mode?.differs ? <div className="notice notice-warning">추천 모드와 확정 모드가 다릅니다.</div> : null}

      <button type="button" onClick={onApplyRecommendation} disabled={loading || !mode?.recommended_mode}>
        <Check aria-hidden="true" size={16} />
        추천 적용
      </button>
    </section>
  );
}
