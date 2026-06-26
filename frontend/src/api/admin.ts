import { apiUrl } from "./client";

export function getSqliteBackupUrl(): string {
  return apiUrl("/api/admin/sqlite-backup");
}
