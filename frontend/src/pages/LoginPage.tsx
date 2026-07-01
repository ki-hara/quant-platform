import { FormEvent, useEffect, useState } from "react";
import { createOwner, listOwners, loginOwner } from "../api/auth";
import { setAuthToken } from "../api/client";
import type { AuthOwner } from "../types/api";

interface LoginPageProps {
  onLogin: (owner: AuthOwner) => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [owners, setOwners] = useState<AuthOwner[]>([]);
  const [mode, setMode] = useState<"login" | "create">("login");
  const [ownerId, setOwnerId] = useState("");
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    listOwners()
      .then((rows) => {
        setOwners(rows);
        setOwnerId(rows[0]?.id ?? "default");
      })
      .catch((caught) => setError(errorMessage(caught)));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setWorking(true);
      setError("");
      if (mode === "create") {
        await createOwner({ id: ownerId.trim(), name: name.trim(), pin });
      }
      const response = await loginOwner({ owner_id: ownerId.trim(), pin });
      setAuthToken(response.token);
      onLogin(response.owner);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div>
          <p className="eyebrow">퀀트 운용</p>
          <h1>{mode === "login" ? "사용자 로그인" : "사용자 만들기"}</h1>
          <p className="login-copy">사용자별 전략, 포지션, 거래내역을 분리해서 관리합니다.</p>
        </div>
        {error ? <div className="notice notice-error">{error}</div> : null}
        <form className="form-stack" onSubmit={handleSubmit}>
          {mode === "login" && owners.length > 0 ? (
            <label>
              사용자
              <select value={ownerId} onChange={(event) => setOwnerId(event.target.value)}>
                {owners.map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.name} ({owner.id})
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              사용자 ID
              <input
                value={ownerId}
                onChange={(event) => setOwnerId(event.target.value)}
                placeholder="영문, 숫자, -, _"
                required
              />
            </label>
          )}
          {mode === "create" ? (
            <label>
              표시 이름
              <input value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
          ) : null}
          <label>
            PIN
            <input
              type="password"
              value={pin}
              onChange={(event) => setPin(event.target.value)}
              minLength={4}
              maxLength={32}
              required
            />
          </label>
          <button type="submit" disabled={working}>
            {working ? "처리 중" : mode === "login" ? "로그인" : "만들고 로그인"}
          </button>
        </form>
        <button
          className="ghost-button"
          type="button"
          onClick={() => {
            setMode((current) => (current === "login" ? "create" : "login"));
            setError("");
          }}
        >
          {mode === "login" ? "새 사용자 만들기" : "기존 사용자로 로그인"}
        </button>
        <p className="form-status">체험용 계정은 guest / 0000입니다. 개인 데이터 관리는 별도 사용자 계정을 사용하세요.</p>
      </section>
    </main>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
