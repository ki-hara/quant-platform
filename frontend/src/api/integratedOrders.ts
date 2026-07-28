import { apiGet, apiPut } from "./client";
import type {
  IntegratedOrderPreference,
  IntegratedOrderPreferenceUpdate,
  IntegratedOrdersResponse,
} from "../types/api";

export function getIntegratedOrders(signal?: AbortSignal): Promise<IntegratedOrdersResponse> {
  return apiGet<IntegratedOrdersResponse>("/api/integrated-orders", signal);
}

export function updateIntegratedOrderPreference(
  configId: number,
  request: IntegratedOrderPreferenceUpdate,
): Promise<IntegratedOrderPreference> {
  return apiPut<IntegratedOrderPreference>(
    `/api/integrated-orders/preferences/${configId}`,
    request,
  );
}
