import { apiGet } from "./client";
import type { DashboardResponse } from "../types/api";

export function getDashboard(configId: number, signal?: AbortSignal): Promise<DashboardResponse> {
  return apiGet<DashboardResponse>(`/api/dashboard/${configId}`, signal);
}
