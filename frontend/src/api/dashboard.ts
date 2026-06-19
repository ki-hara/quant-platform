import { apiGet } from "./client";
import type { DashboardResponse } from "../types/api";

export function getDashboard(configId: number): Promise<DashboardResponse> {
  return apiGet<DashboardResponse>(`/api/dashboard/${configId}`);
}
