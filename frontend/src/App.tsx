import { Activity, BarChart3, BriefcaseBusiness, Settings2 } from "lucide-react";
import { useMemo, useState } from "react";
import { BacktestPage } from "./pages/BacktestPage";
import { DashboardPage } from "./pages/DashboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TradesPage } from "./pages/TradesPage";

type TabKey = "dashboard" | "backtest" | "settings" | "trades";

interface TabItem {
  key: TabKey;
  label: string;
  icon: typeof Activity;
}

const tabs: TabItem[] = [
  { key: "dashboard", label: "대시보드", icon: Activity },
  { key: "backtest", label: "백테스트", icon: BarChart3 },
  { key: "settings", label: "전략 설정", icon: Settings2 },
  { key: "trades", label: "거래/포지션", icon: BriefcaseBusiness },
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
            API 연결
          </div>
        </header>

        {activeTab === "dashboard" && <DashboardPage />}
        {activeTab === "backtest" && <BacktestPage />}
        {activeTab === "settings" && <SettingsPage />}
        {activeTab === "trades" && <TradesPage />}
      </main>
    </div>
  );
}

export default App;
