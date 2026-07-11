import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StrategyConfig } from "../types/api";
import { rememberStrategyConfigId, resolveRememberedStrategyConfigId } from "./strategySelection";


function config(id: number): StrategyConfig {
  return { id } as StrategyConfig;
}


describe("strategy selection", () => {
  const values = new Map<string, string>();

  beforeEach(() => {
    values.clear();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("restores a remembered strategy that still exists", () => {
    rememberStrategyConfigId(2);

    expect(resolveRememberedStrategyConfigId([config(1), config(2)])).toBe(2);
  });

  it("falls back to the first strategy when the remembered one is gone", () => {
    rememberStrategyConfigId(99);

    expect(resolveRememberedStrategyConfigId([config(1), config(2)])).toBe(1);
  });

  it("returns null when no strategy exists", () => {
    expect(resolveRememberedStrategyConfigId([])).toBeNull();
  });
});
