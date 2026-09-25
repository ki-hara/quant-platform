import { expect, it, vi } from "vitest";
import { applyLatestResult } from "./applyLatestResult";

it("updates successful data even when another panel fails", async () => {
  const update = vi.fn(); const fail = vi.fn();
  await Promise.all([
    applyLatestResult(Promise.resolve(123), () => true, update, fail),
    applyLatestResult(Promise.reject(new Error("chart")), () => true, vi.fn(), fail),
  ]);
  expect(update).toHaveBeenCalledWith(123);
  expect(fail).toHaveBeenCalledTimes(1);
});

it("ignores stale responses and failures", async () => {
  const update = vi.fn(); const fail = vi.fn();
  await applyLatestResult(Promise.resolve(1), () => false, update, fail);
  await applyLatestResult(Promise.reject(new Error("old")), () => false, update, fail);
  expect(update).not.toHaveBeenCalled(); expect(fail).not.toHaveBeenCalled();
});

it("does not show request cancellation as an error", async () => {
  const fail = vi.fn();
  await applyLatestResult(Promise.reject(new DOMException("cancelled", "AbortError")), () => true, vi.fn(), fail);
  expect(fail).not.toHaveBeenCalled();
});
