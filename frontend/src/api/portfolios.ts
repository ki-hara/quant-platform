import { apiGet, apiPost } from "./client";
import type { PortfolioAdjustment, PortfolioAdjustmentCreateRequest } from "../types/api";

export function listPortfolioAdjustments(configId: number): Promise<PortfolioAdjustment[]> {
  return apiGet<PortfolioAdjustment[]>(`/api/strategy-configs/${configId}/portfolio-adjustments`);
}

export function createPortfolioAdjustment(
  configId: number,
  request: PortfolioAdjustmentCreateRequest,
): Promise<PortfolioAdjustment> {
  return apiPost<PortfolioAdjustment>(`/api/strategy-configs/${configId}/portfolio-adjustments`, request);
}
