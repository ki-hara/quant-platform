import { Activity, BarChart3, BriefcaseBusiness, Settings2 } from "lucide-react";
import { useMemo, useState } from "react";

type TabKey = "dashboard" | "backtest" | "strategies" | "trades";

interface TabItem {
  key: TabKey;
  label: string;
  icon: typeof Activity;
}

const tabs: TabItem[] = [
  { key: "dashboard", label: "대시보드", icon: Activity },
  { key: "backtest", label: "백테스트", icon: BarChart3 },
  { key: "strategies", label: "전략 설정", icon: Settings2 },
  { key: "trades", label: "거래/포지션", icon: BriefcaseBusiness },
];

const metricRows = [
  { label: "총 자산", value: "연결 대기", tone: "neutral" },
  { label: "현금", value: "연결 대기", tone: "neutral" },
  { label: "실현 손익", value: "연결 대기", tone: "neutral" },
  { label: "보유 포지션", value: "0", tone: "neutral" },
];

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const activeLabel = useMemo(
    () => tabs.find((tab) => tab.key === activeTab)?.label ?? "대시보드",
    [activeTab],
  );

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="주요 메뉴">
        <div className="brand">
          <span className="brand-mark">Q</span>
          <div>
            <p className="brand-title">퀀트 투자</p>
            <p className="brand-subtitle">운영 콘솔</p>
          </div>
        </div>

        <nav className="tab-nav">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                className="tab-button"
                type="button"
                aria-current={isActive ? "page" : undefined}
                onClick={() => setActiveTab(tab.key)}
              >
                <Icon aria-hidden="true" size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="content">
        <header className="page-header">
          <div>
            <p className="eyebrow">실시간 전략 모니터링</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="status-pill" aria-label="API 연결 상태">
            API 연결 대기
          </div>
        </header>

        {activeTab === "dashboard" && <DashboardShell />}
        {activeTab === "backtest" && <BacktestShell />}
        {activeTab === "strategies" && <StrategiesShell />}
        {activeTab === "trades" && <TradesShell />}
      </main>
    </div>
  );
}

function DashboardShell() {
  return (
    <section className="page-grid" aria-label="대시보드 요약">
      <div className="panel panel-wide">
        <div className="panel-header">
          <h2>계좌 요약</h2>
          <span>선택 전략 기준</span>
        </div>
        <div className="metric-strip">
          {metricRows.map((metric) => (
            <div className="metric" key={metric.label} data-tone={metric.tone}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>매수 신호</h2>
          <span>최근 가격 기준</span>
        </div>
        <div className="empty-state">
          <strong>전략을 선택하면 신호가 표시됩니다.</strong>
          <p>백엔드 API 연결 후 최신 가격, 매수 조건, 매도 후보를 확인합니다.</p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>포지션</h2>
          <span>보유 종목</span>
        </div>
        <CompactTable
          headers={["매수일", "수량", "단가", "상태"]}
          rows={[["-", "-", "-", "대기"]]}
        />
      </div>
    </section>
  );
}

function BacktestShell() {
  return (
    <section className="page-grid">
      <div className="panel panel-wide">
        <div className="panel-header">
          <h2>백테스트 실행</h2>
          <span>기간별 성과 검증</span>
        </div>
        <div className="form-grid">
          <label>
            전략 ID
            <input type="number" placeholder="예: 1" />
          </label>
          <label>
            시작일
            <input type="date" />
          </label>
          <label>
            종료일
            <input type="date" />
          </label>
          <button type="button">실행 준비</button>
        </div>
      </div>
      <div className="panel">
        <div className="panel-header">
          <h2>성과 지표</h2>
          <span>최근 실행</span>
        </div>
        <CompactTable
          headers={["항목", "값"]}
          rows={[
            ["수익률", "-"],
            ["최대 낙폭", "-"],
            ["승률", "-"],
          ]}
        />
      </div>
      <div className="panel">
        <div className="panel-header">
          <h2>CSV 내보내기</h2>
          <span>일별/거래/요약</span>
        </div>
        <div className="button-row">
          <button type="button">일별</button>
          <button type="button">거래</button>
          <button type="button">요약</button>
        </div>
      </div>
    </section>
  );
}

function StrategiesShell() {
  return (
    <section className="page-grid">
      <div className="panel panel-wide">
        <div className="panel-header">
          <h2>전략 설정</h2>
          <span>설정 목록</span>
        </div>
        <CompactTable
          headers={["이름", "전략", "심볼", "초기 자본"]}
          rows={[["등록 대기", "-", "-", "-"]]}
        />
      </div>
      <div className="panel">
        <div className="panel-header">
          <h2>새 설정</h2>
          <span>기본 입력</span>
        </div>
        <div className="form-stack">
          <label>
            이름
            <input type="text" placeholder="전략 이름" />
          </label>
          <label>
            심볼
            <input type="text" placeholder="005930" />
          </label>
          <button type="button">저장 준비</button>
        </div>
      </div>
    </section>
  );
}

function TradesShell() {
  return (
    <section className="page-grid">
      <div className="panel">
        <div className="panel-header">
          <h2>거래 내역</h2>
          <span>전략별 체결</span>
        </div>
        <CompactTable
          headers={["일자", "구분", "수량", "가격"]}
          rows={[["-", "-", "-", "-"]]}
        />
      </div>
      <div className="panel">
        <div className="panel-header">
          <h2>포지션</h2>
          <span>현재 보유</span>
        </div>
        <CompactTable
          headers={["ID", "모드", "수량", "상태"]}
          rows={[["-", "-", "-", "-"]]}
        />
      </div>
    </section>
  );
}

function CompactTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
