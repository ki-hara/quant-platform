import { describe, expect, it } from "vitest";
import {
  canOverrideOpen,
  GOLD_TOILET_OPEN_POLL_INTERVAL_MS,
  orderCopyText,
  shouldPollForOpen,
} from "./goldToiletOrders";

describe("gold toilet order helpers", () => {
  it("polls every second for today's SOXL open until it is ready", () => {
    const now = new Date("2026-08-04T15:00:00Z");
    expect(GOLD_TOILET_OPEN_POLL_INTERVAL_MS).toBe(1_000);
    expect(shouldPollForOpen("2026-08-04", "waiting", now)).toBe(true);
    expect(shouldPollForOpen("2026-08-04", "failed", now)).toBe(true);
    expect(shouldPollForOpen("2026-08-04", "ready", now)).toBe(false);
    expect(shouldPollForOpen("2026-08-03", "waiting", now)).toBe(false);
  });

  it("allows a manual override only after an automatic open exists", () => {
    expect(canOverrideOpen("131.505")).toBe(true);
    expect(canOverrideOpen(null)).toBe(false);
  });

  it("copies broker-ready raw values", () => {
    expect(orderCopyText("price", "48.97")).toBe("48.97");
    expect(orderCopyText("quantity", 51)).toBe("51");
  });
});
