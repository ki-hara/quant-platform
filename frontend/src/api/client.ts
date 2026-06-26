const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "quant_owner_token";

export function getAuthToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string | null): void {
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: body === undefined ? authHeaders() : { ...authHeaders(), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE", headers: authHeaders() });
  if (!response.ok) throw new Error(await errorMessage(response));
}

export function apiUrl(path: string): string {
  const token = getAuthToken();
  const url = new URL(`${API_BASE_URL}${path}`, window.location.href);
  if (token) url.searchParams.set("access_token", token);
  return url.toString();
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function errorMessage(response: Response): Promise<string> {
  const fallback = `요청 처리에 실패했습니다. (${response.status})`;
  try {
    const body = await response.clone().json();
    const detail = body?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const messages = detail
        .map((item) => {
          if (typeof item?.msg !== "string") return null;
          const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
          return field ? `${field}: ${item.msg}` : item.msg;
        })
        .filter(Boolean)
        .join(", ");
      if (messages) return `입력값을 확인해 주세요. ${messages}`;
    }
  } catch {
    const text = await response.text();
    if (text.trim()) return text;
  }
  return fallback;
}
