import { apiDownload, apiGet, apiPost } from "./client";
import type { AdminSummary, AdminUser, PinResetResponse } from "../types/api";

export function downloadSqliteBackup(): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
  return apiDownload("/api/admin/sqlite-backup", `quant-platform-backup-${timestamp}.db`);
}

export function getAdminSummary(): Promise<AdminSummary> {
  return apiGet<AdminSummary>("/api/admin/summary");
}

export function listAdminUsers(): Promise<AdminUser[]> {
  return apiGet<AdminUser[]>("/api/admin/users");
}

export function resetUserPin(ownerId: string): Promise<PinResetResponse> {
  return apiPost<PinResetResponse>(`/api/admin/users/${encodeURIComponent(ownerId)}/reset-pin`);
}

export function deactivateUser(ownerId: string): Promise<AdminUser> {
  return apiPost<AdminUser>(`/api/admin/users/${encodeURIComponent(ownerId)}/deactivate`);
}

export function activateUser(ownerId: string): Promise<AdminUser> {
  return apiPost<AdminUser>(`/api/admin/users/${encodeURIComponent(ownerId)}/activate`);
}
