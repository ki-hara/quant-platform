import { Save } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type {
  StrategyConfig,
  StrategyConfigCreateRequest,
  StrategyInfo,
  StrategySchema,
} from "../types/api";
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
  editingConfig?: StrategyConfig | null;
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

const investmentPresets: Array<{ label: string; values: Record<string, FieldValue> }> = [
  {
    label: "적극투자형",
    values: {
      profit_compounding_rate: 60,
      loss_compounding_rate: 20,
      "capital_update.type": "trading_days",
      "capital_update.interval": 10,
      "safe.split_count": 7,
      "aggressive.split_count": 7,
    },
  },
  {
    label: "공격투자형",
    values: {
      profit_compounding_rate: 80,
      loss_compounding_rate: 30,
      "capital_update.type": "trading_days",
      "capital_update.interval": 10,
      "safe.split_count": 7,
      "aggressive.split_count": 7,
    },
  },
];

export function SettingsForm({
  strategies,
  schema,
  selectedStrategyType,
  editingConfig,
  onStrategyTypeChange,
  onSubmit,
  saving = false,
}: SettingsFormProps) {
  const [common, setCommon] = useState(() =>
    editingConfig
      ? {
          name: editingConfig.name,
          symbol: editingConfig.symbol,
          initial_capital: editingConfig.initial_capital,
          fee_rate: editingConfig.fee_rate,
          slippage_rate: editingConfig.slippage_rate,
        }
      : commonDefaults,
  );
  const fields = useMemo(() => flattenSchemaFields(schema?.schema), [schema]);
  const [settings, setSettings] = useState<Record<string, FieldValue>>(() =>
    flattenSettings(editingConfig?.settings_json),
  );

  function valueFor(field: FieldDescriptor): FieldValue {
    return settings[field.key] ?? field.defaultValue;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      ...common,
      slippage_rate: common.slippage_rate || "0",
      strategy_type: selectedStrategyType,
      settings_json: buildNestedSettings(fields, settings),
    });
    if (!editingConfig) {
      setCommon(commonDefaults);
      setSettings({});
    }
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
            종목 코드
            <input
              value={common.symbol}
              onChange={(event) =>
                setCommon((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))
              }
              placeholder="SOXL 또는 005930.KS"
              required
            />
          </label>
          <label>
            초기 투자금
            <input
              value={common.initial_capital}
              onChange={(event) =>
                setCommon((current) => ({ ...current, initial_capital: event.target.value }))
              }
              readOnly={Boolean(editingConfig)}
              aria-describedby={editingConfig ? "initial-capital-edit-note" : undefined}
              required
            />
            {editingConfig ? (
              <small id="initial-capital-edit-note" className="form-status">
                실전 포트폴리오 장부 보호를 위해 생성 후에는 수정할 수 없습니다.
              </small>
            ) : null}
          </label>
          <label>
            거래 수수료율 (%)
            <input
              type="number"
              step="any"
              value={common.fee_rate}
              onChange={(event) =>
                setCommon((current) => ({ ...current, fee_rate: event.target.value }))
              }
              required
            />
          </label>
        </div>
      </div>

      <div className="form-section">
        <h2>전략별 설정</h2>
        <div className="segmented-control" role="group" aria-label="투자 성향">
          {investmentPresets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => setSettings((current) => ({ ...current, ...preset.values }))}
            >
              {preset.label}
            </button>
          ))}
        </div>
        {fields.length === 0 ? (
          <div className="empty-state">설정 스키마가 없습니다.</div>
        ) : (
          <div className="form-grid">
            {fields.filter((field) => isFieldVisible(field, fields, settings)).map((field) => (
              <label key={field.key}>
                {field.label}
                {field.key === "capital_update.type" ? (
                  <select
                    value={String(valueFor(field))}
                    onChange={(event) =>
                      setSettings((current) => ({ ...current, [field.key]: event.target.value }))
                    }
                  >
                    <option value="trading_days">거래일 간격</option>
                    <option value="calendar">달력 주기</option>
                  </select>
                ) : field.key === "capital_update.period" ? (
                  <select
                    value={String(valueFor(field))}
                    onChange={(event) =>
                      setSettings((current) => ({ ...current, [field.key]: event.target.value }))
                    }
                  >
                    <option value="monthly">매월</option>
                    <option value="quarterly">매분기</option>
                    <option value="yearly">매년</option>
                  </select>
                ) : (
                  <input
                    type="number"
                    step={inputStepFor(field.key)}
                    value={String(valueFor(field))}
                    onChange={(event) =>
                      setSettings((current) => ({ ...current, [field.key]: coerceValue(event.target.value) }))
                    }
                  />
                )}
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="form-actions">
        <button type="submit" disabled={saving || strategies.length === 0}>
          <Save aria-hidden="true" size={16} />
          {saving ? "저장 중" : editingConfig ? "변경사항 저장" : "새 설정 저장"}
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

function flattenSettings(value: Record<string, unknown> | undefined): Record<string, FieldValue> {
  if (!value) return {};
  return Object.fromEntries(flattenObject(value).map((field) => [field.key, field.defaultValue]));
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

function isFieldVisible(
  field: FieldDescriptor,
  fields: FieldDescriptor[],
  values: Record<string, FieldValue>,
): boolean {
  if (field.key !== "capital_update.interval" && field.key !== "capital_update.period") return true;
  const typeField = fields.find((candidate) => candidate.key === "capital_update.type");
  const updateType = String(values["capital_update.type"] ?? typeField?.defaultValue ?? "trading_days");
  return field.key === "capital_update.interval"
    ? updateType === "trading_days"
    : updateType === "calendar";
}

function coerceValue(value: string): FieldValue {
  if (value === "true") return true;
  if (value === "false") return false;
  if (value.trim() !== "" && !Number.isNaN(Number(value))) return Number(value);
  return value;
}

function inputStepFor(key: string): string {
  if (key.endsWith("_percent") || key.endsWith("_rate")) return "any";
  if (key.endsWith("_days") || key.endsWith("split_count") || key === "capital_update.interval") return "1";
  return "any";
}

function labelFor(key: string): string {
  const labels: Record<string, string> = {
    mode_rsi_symbol: "모드 변경 RSI 종목",
    base_index: "기초지수",
    profit_compounding_rate: "이익복리율 (PCR)",
    loss_compounding_rate: "손실복리율 (LCR)",
    "capital_update.type": "투자금 갱신 방식",
    "capital_update.interval": "투자금 갱신 거래일 간격",
    "capital_update.period": "투자금 갱신 달력 주기",
    "safe.split_count": "안전모드 분할수",
    "safe.max_holding_days": "안전모드 최대 보유기간",
    "safe.buy_threshold_percent": "안전모드 매수조건 (%)",
    "safe.sell_threshold_percent": "안전모드 매도조건 (%)",
    "aggressive.split_count": "공세모드 분할수",
    "aggressive.max_holding_days": "공세모드 최대 보유기간",
    "aggressive.buy_threshold_percent": "공세모드 매수조건 (%)",
    "aggressive.sell_threshold_percent": "공세모드 매도조건 (%)",
  };
  return labels[key] ?? key;
}
