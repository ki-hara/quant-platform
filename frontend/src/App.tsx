import { Activity, BarChart3, BriefcaseBusiness, KeyRound, LogOut, Settings2, ShieldCheck, WalletCards } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { changeMyPin, getMe } from "./api/auth";
import { setAuthToken } from "./api/client";
import { AdminPage } from "./pages/AdminPage";
import { BacktestPage } from "./pages/BacktestPage";
import { CapitalAdjustmentPage } from "./pages/CapitalAdjustmentPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TradesPage } from "./pages/TradesPage";
import type { AuthOwner } from "./types/api";

type TabKey = "dashboard" | "backtest" | "settings" | "trades" | "capital" | "admin";

interface TabItem {
  key: TabKey;
  label: string;
  icon: typeof Activity;
}

const baseTabs: TabItem[] = [
  { key: "dashboard", label: "대시보드", icon: Activity },
  { key: "trades", label: "거래/포지션", icon: BriefcaseBusiness },
  { key: "settings", label: "전략 설정", icon: Settings2 },
  { key: "backtest", label: "백테스트", icon: BarChart3 },
  { key: "capital", label: "자본 조정", icon: WalletCards },
];

const adminTab: TabItem = { key: "admin", label: "운영 관리", icon: ShieldCheck };

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [owner, setOwner] = useState<AuthOwner | null>(null);
  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [newPinConfirm, setNewPinConfirm] = useState("");
  const [pinMessage, setPinMessage] = useState("");
  const [pinError, setPinError] = useState("");
  const [pinWorking, setPinWorking] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const tabs = useMemo(() => (owner?.is_admin ? [...baseTabs, adminTab] : baseTabs), [owner?.is_admin]);
  const activeLabel = useMemo(
    () => tabs.find((tab) => tab.key === activeTab)?.label ?? "대시보드",
    [activeTab, tabs],
  );

  useEffect(() => {
    getMe()
      .then(setOwner)
      .catch(() => setAuthToken(null))
      .finally(() => setCheckingAuth(false));
  }, []);

  useEffect(() => {
    if (activeTab === "admin" && !owner?.is_admin) setActiveTab("dashboard");
  }, [activeTab, owner?.is_admin]);

  async function handlePinChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPin !== newPinConfirm) {
      setPinError("새 PIN과 확인 PIN이 일치하지 않습니다.");
      return;
    }
    try {
      setPinWorking(true);
      setPinError("");
      setPinMessage("");
      const nextOwner = await changeMyPin({ current_pin: currentPin, new_pin: newPin });
      setOwner(nextOwner);
      setCurrentPin("");
      setNewPin("");
      setNewPinConfirm("");
      setPinMessage("PIN이 변경되었습니다.");
    } catch (caught) {
      setPinError(errorMessage(caught));
    } finally {
      setPinWorking(false);
    }
  }

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
          {activeTab === "dashboard" ? (
            <div className="user-chip">
              <div>
                <span className="user-chip-label">사용자</span>
                <strong>{owner.name}</strong>
              </div>
              <button
                type="button"
                disabled={!owner.pin_change_allowed}
                onClick={() => setPinModalOpen(true)}
              >
                <KeyRound aria-hidden="true" size={16} />
                PIN 변경
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthToken(null);
                  setOwner(null);
                }}
              >
                <LogOut aria-hidden="true" size={16} />
                로그아웃
              </button>
            </div>
          ) : null}
        </header>

        {activeTab === "dashboard" && <DashboardPage canBackup={owner.is_admin} />}
        {activeTab === "backtest" && <BacktestPage />}
        {activeTab === "capital" && <CapitalAdjustmentPage />}
        {activeTab === "settings" && <SettingsPage />}
        {activeTab === "trades" && <TradesPage />}
        {activeTab === "admin" && owner.is_admin && <AdminPage />}
      </main>
      {pinModalOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-label="PIN 변경">
            <div className="panel-header">
              <div>
                <h2>PIN 변경</h2>
                <span>현재 PIN을 확인한 뒤 새 PIN을 저장합니다.</span>
              </div>
            </div>
            {pinError ? <div className="notice notice-error">{pinError}</div> : null}
            {pinMessage ? <div className="notice">{pinMessage}</div> : null}
            <form className="form-stack" onSubmit={handlePinChange}>
              <label>
                현재 PIN
                <input type="password" value={currentPin} onChange={(event) => setCurrentPin(event.target.value)} minLength={4} maxLength={32} required />
              </label>
              <label>
                새 PIN
                <input type="password" value={newPin} onChange={(event) => setNewPin(event.target.value)} minLength={4} maxLength={32} required />
              </label>
              <label>
                새 PIN 확인
                <input type="password" value={newPinConfirm} onChange={(event) => setNewPinConfirm(event.target.value)} minLength={4} maxLength={32} required />
              </label>
              <div className="inline-actions">
                <button type="submit" disabled={pinWorking}>
                  저장
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => {
                    setPinModalOpen(false);
                    setPinError("");
                    setPinMessage("");
                  }}
                >
                  닫기
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}

export default App;
