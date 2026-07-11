import { describe, expect, it } from "vitest";


async function loadLatestRequestModule() {
  try {
    return await import("./latestRequest");
  } catch {
    throw new Error("LatestRequest utility is missing");
  }
}


describe("LatestRequest", () => {
  it("aborts the previous request when a replacement starts", async () => {
    const { LatestRequest } = await loadLatestRequestModule();
    const requests = new LatestRequest();

    const first = requests.start();
    const second = requests.start();

    expect(first.signal.aborted).toBe(true);
    expect(second.signal.aborted).toBe(false);
    expect(requests.isCurrent(second)).toBe(true);
  });

  it("does not let an older request clear the current request", async () => {
    const { LatestRequest } = await loadLatestRequestModule();
    const requests = new LatestRequest();
    const first = requests.start();
    const second = requests.start();

    requests.finish(first);

    expect(requests.isCurrent(second)).toBe(true);
    requests.finish(second);
    expect(requests.isCurrent(second)).toBe(false);
  });

  it("recognizes abort errors without hiding other failures", async () => {
    const { isAbortError } = await loadLatestRequestModule();

    expect(isAbortError(new DOMException("Aborted", "AbortError"))).toBe(true);
    expect(isAbortError(new Error("network failed"))).toBe(false);
  });
});
