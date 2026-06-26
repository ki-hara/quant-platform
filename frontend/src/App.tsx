import { Activity, BarChart3, BriefcaseBusiness, Settings2, WalletCards } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getMe } from "./api/auth";
import { setAuthToken } from "./api/client";
import { BacktestPage } from "./pages/BacktestPage";
import { CapitalAdjustmentPage } from "./pages/CapitalAdjustmentPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TradesPage } from "./pages/TradesPage";
import type { AuthOwner } from "./types/api";

type TabKey = "dashboard" | "backtest" | "settings" | "trades" | "capital";

interface TabItem {
  key: TabKey;
  label: string;
  icon: typeof Activity;
}

const tabs: TabItem[] = [
  { key: "dashboard", label: "대시보드", icon: Activity },
  { key: "backtest", label: "백테스트", icon: BarChart3 },
  { key: "capital", label: "자본 조정", icon: WalletCards },
  { key: "settings", label: "전략 설정", icon: Settings2 },
  { key: "trades", label: "거래/포지션", icon: BriefcaseBusiness },
];

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [owner, setOwner] = useState<AuthOwner | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const activeLabel = useMemo(
    () => tabs.find((tab) => tab.key === activeTab)?.label ?? "대시보드",
    [activeTab],
  );

  useEffect(() => {
    getMe()
      .then(setOwner)
      .catch(() => setAuthToken(null))
      .finally(() => setCheckingAuth(false));
  }, []);

  if (checkingAuth) {
    return <div className="notice app-loading">로그인 상태를 확인하는 중입니다.</div>;
  }

  if (!owner) {
    return <LoginPage onLogin={setOwner} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="주요 메뉴">
        <div className="brand">
          <span className="brand-mark">Q</span>
          <div>
            <p className="brand-title">퀀트 운용</p>
            <p className="brand-subtitle">매매 지원 콘솔</p>
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
            <p className="eyebrow">실전 매매 지원</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="user-chip">
            <span>{owner.name}</span>
          </div>
        </header>

        {activeTab === "dashboard" && (
          <DashboardPage
            onLogout={() => {
              setAuthToken(null);
              setOwner(null);
            }}
          />
        )}
        {activeTab === "backtest" && <BacktestPage />}
        {activeTab === "capital" && <CapitalAdjustmentPage />}
        {activeTab === "settings" && <SettingsPage />}
        {activeTab === "trades" && <TradesPage />}
      </main>
    </div>
  );
}

export default App;
