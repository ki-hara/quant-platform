import { apiGet, apiPost } from "./client";
import type { AuthOwner, LoginResponse } from "../types/api";

export function listOwners(): Promise<AuthOwner[]> {
  return apiGet<AuthOwner[]>("/api/auth/owners");
}

export function loginOwner(request: { owner_id: string; pin: string }): Promise<LoginResponse> {
  return apiPost<LoginResponse>("/api/auth/login", request);
}

export function createOwner(request: { id: string; name: string; pin: string }): Promise<AuthOwner> {
  return apiPost<AuthOwner>("/api/auth/owners", request);
}

export function getMe(): Promise<AuthOwner> {
  return apiGet<AuthOwner>("/api/auth/me");
}
