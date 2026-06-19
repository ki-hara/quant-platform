import { Save } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type { StrategyConfigCreateRequest, StrategyInfo, StrategySchema } from "../types/api";
import { translateStrategyType } from "../utils/format";

type FieldValue = string | number | boolean;

interface FieldDescriptor {
  key: string;
  label: string;
  defaultValue: FieldValue;
}

interface SettingsFormProps {
  strategies: StrategyInfo[];
  schema: StrategySchema | null;
  selectedStrategyType: string;
  onStrategyTypeChange: (strategyType: string) => void;
  onSubmit: (request: StrategyConfigCreateRequest) => Promise<void>;
  saving?: boolean;
}

const commonDefaults = {
  name: "",
  symbol: "",
  initial_capital: "10000000",
  fee_rate: "0.001",
  slippage_rate: "0",
};

export function SettingsForm({
  strategies,
  schema,
  selectedStrategyType,
  onStrategyTypeChange,
  onSubmit,
  saving = false,
}: SettingsFormProps) {
  const [common, setCommon] = useState(commonDefaults);
  const fields = useMemo(() => flattenSchemaFields(schema?.schema), [schema]);
  const [settings, setSettings] = useState<Record<string, FieldValue>>({});

  function valueFor(field: FieldDescriptor): FieldValue {
    return settings[field.key] ?? field.defaultValue;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const settingsJson = buildNestedSettings(fields, settings);
    await onSubmit({
      ...common,
      strategy_type: selectedStrategyType,
      settings_json: settingsJson,
    });
    setCommon(commonDefaults);
    setSettings({});
  }

  return (
    <form className="settings-form" onSubmit={handleSubmit}>
      <div className="form-section">
        <h2>공통 설정</h2>
        <div className="form-grid">
          <label>
            전략
            <select
              value={selectedStrategyType}
              onChange={(event) => {
                onStrategyTypeChange(event.target.value);
                setSettings({});
              }}
              required
            >
              {strategies.map((strategy) => (
                <option key={strategy.type} value={strategy.type}>
                  {translateStrategyType(strategy.type)}
                </option>
              ))}
            </select>
          </label>
          <label>
            이름
            <input
              value={common.name}
              onChange={(event) => setCommon((current) => ({ ...current, name: event.target.value }))}
              placeholder="전략 이름"
              required
            />
          </label>
          <label>
            티커
            <input
              value={common.symbol}
              onChange={(event) =>
                setCommon((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))
              }
              placeholder="005930 또는 QQQ"
              required
            />
          </label>
          <label>
            초기 자본
            <input
              value={common.initial_capital}
              onChange={(event) =>
                setCommon((current) => ({ ...current, initial_capital: event.target.value }))
              }
              required
            />
          </label>
          <label>
            수수료율
            <input
              value={common.fee_rate}
              onChange={(event) =>
                setCommon((current) => ({ ...current, fee_rate: event.target.value }))
              }
              required
            />
          </label>
          <label>
            슬리피지율
            <input
              value={common.slippage_rate}
              onChange={(event) =>
                setCommon((current) => ({ ...current, slippage_rate: event.target.value }))
              }
              required
            />
          </label>
        </div>
      </div>

      <div className="form-section">
        <h2>전략별 설정</h2>
        {fields.length === 0 ? (
          <div className="empty-state">스키마 데이터 없음</div>
        ) : (
          <div className="form-grid">
            {fields.map((field) => (
              <label key={field.key}>
                {field.label}
                <input
                  value={String(valueFor(field))}
                  onChange={(event) =>
                    setSettings((current) => ({ ...current, [field.key]: coerceValue(event.target.value) }))
                  }
                />
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="form-actions">
        <button type="submit" disabled={saving || strategies.length === 0}>
          <Save aria-hidden="true" size={16} />
          {saving ? "저장 중" : "설정 저장"}
        </button>
      </div>
    </form>
  );
}

function flattenSchemaFields(schema: Record<string, unknown> | undefined): FieldDescriptor[] {
  const root = schema?.fields;
  if (!root || typeof root !== "object" || Array.isArray(root)) return [];
  return flattenObject(root as Record<string, unknown>);
}

function flattenObject(value: Record<string, unknown>, prefix = ""): FieldDescriptor[] {
  return Object.entries(value).flatMap(([key, child]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === "object" && !Array.isArray(child)) {
      return flattenObject(child as Record<string, unknown>, nextKey);
    }
    return [{ key: nextKey, label: labelFor(nextKey), defaultValue: child as FieldValue }];
  });
}

function buildNestedSettings(fields: FieldDescriptor[], values: Record<string, FieldValue>) {
  const root: Record<string, unknown> = {};
  fields.forEach((field) => {
    const parts = field.key.split(".");
    let target = root;
    parts.slice(0, -1).forEach((part) => {
      target[part] = target[part] && typeof target[part] === "object" ? target[part] : {};
      target = target[part] as Record<string, unknown>;
    });
    target[parts[parts.length - 1]] = values[field.key] ?? field.defaultValue;
  });
  return root;
}

function coerceValue(value: string): FieldValue {
  if (value === "true") return true;
  if (value === "false") return false;
  if (value.trim() !== "" && !Number.isNaN(Number(value))) return Number(value);
  return value;
}

function labelFor(key: string): string {
  const labels: Record<string, string> = {
    mode_rsi_symbol: "모드 RSI 티커",
    base_index: "기준 지수",
    profit_compounding_rate: "수익 복리 반영률",
    loss_compounding_rate: "손실 복리 반영률",
    "capital_update.type": "자본 갱신 방식",
    "capital_update.interval": "자본 갱신 간격",
    "safe.split_count": "안전 분할 수",
    "safe.max_holding_days": "안전 최대 보유일",
    "safe.buy_threshold_percent": "안전 매수 임계값(%)",
    "safe.sell_threshold_percent": "안전 매도 임계값(%)",
    "aggressive.split_count": "공세 분할 수",
    "aggressive.max_holding_days": "공세 최대 보유일",
    "aggressive.buy_threshold_percent": "공세 매수 임계값(%)",
    "aggressive.sell_threshold_percent": "공세 매도 임계값(%)",
  };
  return labels[key] ?? key;
}
