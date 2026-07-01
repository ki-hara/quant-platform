import { apiGet, apiPost, apiUrl } from "./client";
import type { AdminSummary, AdminUser, PinResetResponse } from "../types/api";

export function getSqliteBackupUrl(): string {
  return apiUrl("/api/admin/sqlite-backup");
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
