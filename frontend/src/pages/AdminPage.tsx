import { Download, RefreshCw, ShieldCheck, UserCheck, UserX } from "lucide-react";
import { useEffect, useState } from "react";
import {
  activateUser,
  deactivateUser,
  downloadSqliteBackup,
  getAdminSummary,
  listAdminUsers,
  resetUserPin,
} from "../api/admin";
import type { AdminSummary, AdminUser } from "../types/api";

export function AdminPage() {
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [workingId, setWorkingId] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    try {
      setError("");
      const [nextSummary, nextUsers] = await Promise.all([getAdminSummary(), listAdminUsers()]);
      setSummary(nextSummary);
      setUsers(nextUsers);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  async function handleResetPin(user: AdminUser) {
    try {
      setWorkingId(user.id);
      setMessage("");
      setError("");
      const result = await resetUserPin(user.id);
      setUsers((current) => current.map((row) => (row.id === user.id ? result.owner : row)));
      setMessage(`${user.name} PIN이 ${result.temporary_pin}으로 초기화되었습니다.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorkingId(null);
    }
  }

  async function handleToggleActive(user: AdminUser) {
    try {
      setWorkingId(user.id);
      setMessage("");
      setError("");
      const next = user.is_active ? await deactivateUser(user.id) : await activateUser(user.id);
      setUsers((current) => current.map((row) => (row.id === user.id ? next : row)));
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorkingId(null);
    }
  }

  async function handleDownloadBackup() {
    try {
      setMessage("");
      setError("");
      await downloadSqliteBackup();
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  return (
    <div className="page-stack">
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice">{message}</div> : null}

      <section className="metric-strip">
        <SummaryMetric label="전체 사용자" value={summary?.total_users} />
        <SummaryMetric label="활성 사용자" value={summary?.active_users} />
        <SummaryMetric label="전략 수" value={summary?.strategy_count} />
        <SummaryMetric label="거래 수" value={summary?.trade_count} />
        <SummaryMetric label="DB" value={summary?.database_backend ?? "-"} helper={summary?.database_path ?? "-"} />
        <SummaryMetric label="시장 데이터" value={summary?.latest_market_data_date ?? "-"} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>사용자 관리</h2>
            <span>게스트는 체험용 고정 계정이라 PIN 변경과 초기화가 제한됩니다.</span>
          </div>
          <button type="button" onClick={load}>
            <RefreshCw aria-hidden="true" size={16} />
            새로고침
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>사용자</th>
                <th>권한</th>
                <th>상태</th>
                <th>생성일</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.name}</strong>
                    <div className="muted-text">{user.id}</div>
                  </td>
                  <td>
                    <span className={`status-pill compact ${user.is_admin ? "is-ok" : "is-muted"}`}>
                      {user.is_admin ? "관리자" : user.is_guest ? "게스트" : "일반"}
                    </span>
                  </td>
                  <td>{user.is_active ? "활성" : "비활성"}</td>
                  <td>{user.created_at ? user.created_at.slice(0, 10) : "-"}</td>
                  <td>
                    <div className="inline-actions">
                      <button
                        type="button"
                        disabled={!user.pin_reset_allowed || workingId === user.id}
                        onClick={() => handleResetPin(user)}
                      >
                        <ShieldCheck aria-hidden="true" size={15} />
                        PIN 초기화
                      </button>
                      <button
                        type="button"
                        disabled={!user.deactivate_allowed || workingId === user.id}
                        onClick={() => handleToggleActive(user)}
                      >
                        {user.is_active ? <UserX aria-hidden="true" size={15} /> : <UserCheck aria-hidden="true" size={15} />}
                        {user.is_active ? "비활성화" : "활성화"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>DB 백업</h2>
            <span>현재 SQLite 데이터베이스를 다운로드합니다.</span>
          </div>
          <button type="button" onClick={handleDownloadBackup}>
            <Download aria-hidden="true" size={16} />
            DB 백업
          </button>
        </div>
      </section>
    </div>
  );
}

function SummaryMetric({ label, value, helper }: { label: string; value?: string | number | null; helper?: string | null }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value ?? "-"}</strong>
      {helper ? <small>{helper}</small> : null}
    </article>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
