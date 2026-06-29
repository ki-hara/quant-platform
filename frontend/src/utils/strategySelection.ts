import type { StrategyConfig } from "../types/api";

const LAST_STRATEGY_CONFIG_ID_KEY = "quant-platform:last-strategy-config-id";

export function rememberStrategyConfigId(configId: number | null): void {
  if (configId === null) {
    window.localStorage.removeItem(LAST_STRATEGY_CONFIG_ID_KEY);
    return;
  }
  window.localStorage.setItem(LAST_STRATEGY_CONFIG_ID_KEY, String(configId));
}

export function resolveRememberedStrategyConfigId(configs: StrategyConfig[]): number | null {
  const remembered = Number(window.localStorage.getItem(LAST_STRATEGY_CONFIG_ID_KEY));
  if (Number.isFinite(remembered) && configs.some((config) => config.id === remembered)) {
    return remembered;
  }
  return configs[0]?.id ?? null;
}
