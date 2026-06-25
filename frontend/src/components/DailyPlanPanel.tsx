import { AlertCircle, CheckCircle2 } from "lucide-react";
import type { DailyPlan } from "../types/api";
import { formatMoney, translateMode, translateReason } from "../utils/format";

interface DailyPlanPanelProps {
  plan: DailyPlan | null;
}

export function DailyPlanPanel({ plan }: DailyPlanPanelProps) {
  const available = plan?.buy_available === true;

  return (
    <section className="panel daily-plan-panel">
      <div className="panel-header">
        <div>
          <h2>오늘의 LOC 매수</h2>
          <span>{plan?.market_data_as_of ? `${plan.market_data_as_of} 종가 기준` : "시장 데이터 대기"}</span>
        </div>
        <span className={`status-pill compact ${available ? "is-ok" : "is-blocked"}`}>
          {available ? <CheckCircle2 aria-hidden="true" size={15} /> : <AlertCircle aria-hidden="true" size={15} />}
          {available ? "가능" : "불가"}
        </span>
      </div>

      <div className="daily-plan-main">
        <div>
          <span>LOC 지정가</span>
          <strong>{formatMoney(plan?.LOC.limit_price, plan?.symbol)}</strong>
        </div>
        <div>
          <span>매수 수량</span>
          <strong>{plan?.LOC.quantity ?? "-"}</strong>
        </div>
      </div>

      <dl className="detail-grid">
        <div>
          <dt>종목</dt>
          <dd>{plan?.symbol ?? "-"}</dd>
        </div>
        <div>
          <dt>확정 모드</dt>
          <dd>{translateMode(plan?.confirmed_mode)}</dd>
        </div>
        <div>
          <dt>전일 종가</dt>
          <dd>{formatMoney(plan?.previous_close, plan?.symbol)}</dd>
        </div>
        <div>
          <dt>LOC 기준일</dt>
          <dd>{plan?.loc_basis_date ?? "-"}</dd>
        </div>
        <div>
          <dt>기준 종가</dt>
          <dd>{formatMoney(plan?.loc_basis_close, plan?.symbol)}</dd>
        </div>
        <div className="detail-grid-wide">
          <dt>계산식</dt>
          <dd>{plan?.loc_formula ?? "-"}</dd>
        </div>
        <div>
          <dt>매수조건</dt>
          <dd>{plan?.mode_buy_threshold_percent ? `${plan.mode_buy_threshold_percent}%` : "-"}</dd>
        </div>
        <div>
          <dt>Capital</dt>
          <dd>{formatMoney(plan?.capital, plan?.symbol)}</dd>
        </div>
        <div>
          <dt>Cash</dt>
          <dd>{formatMoney(plan?.cash, plan?.symbol)}</dd>
        </div>
        <div>
          <dt>분할수</dt>
          <dd>{plan?.mode_split_count ?? "-"}</dd>
        </div>
        <div>
          <dt>보유 포지션</dt>
          <dd>{plan?.open_position_count ?? "-"}</dd>
        </div>
        <div>
          <dt>1회 배정금</dt>
          <dd>{formatMoney(plan?.LOC.allocation, plan?.symbol)}</dd>
        </div>
        <div>
          <dt>예상 수수료</dt>
          <dd>{formatMoney(plan?.LOC.estimated_fee, plan?.symbol)}</dd>
        </div>
        <div>
          <dt>필요 현금</dt>
          <dd>{formatMoney(plan?.LOC.required_cash, plan?.symbol)}</dd>
        </div>
        <div>
          <dt>차단 사유</dt>
          <dd>{translateReason(plan?.LOC.blocking_reason)}</dd>
        </div>
      </dl>
    </section>
  );
}
