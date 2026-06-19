import { useEffect, useMemo, useState } from "react";
import {
  createStrategyConfig,
  getStrategySchema,
  listStrategies,
  listStrategyConfigs,
  updateStrategyConfig,
} from "../api/strategies";
import { SettingsForm } from "../components/SettingsForm";
import { Table, type TableColumn } from "../components/Table";
import type { StrategyConfig, StrategyConfigCreateRequest, StrategyInfo, StrategySchema } from "../types/api";
import { formatMoney, translateStrategyType } from "../utils/format";

export function SettingsPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedStrategyType, setSelectedStrategyType] = useState("");
  const [schema, setSchema] = useState<StrategySchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const editingConfig = useMemo(
    () => configs.find((config) => config.id === editingId) ?? null,
    [configs, editingId],
  );

  useEffect(() => {
    async function load() {
      try {
        const [strategyRows, configRows] = await Promise.all([listStrategies(), listStrategyConfigs()]);
        setStrategies(strategyRows);
        setConfigs(configRows);
        setSelectedStrategyType(strategyRows[0]?.type ?? "");
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  useEffect(() => {
    if (!selectedStrategyType) return;
    getStrategySchema(selectedStrategyType).then(setSchema).catch((caught) => setError(errorMessage(caught)));
  }, [selectedStrategyType]);

  function selectEditingConfig(value: string) {
    const configId = Number(value) || null;
    setEditingId(configId);
    const config = configs.find((row) => row.id === configId);
    setSelectedStrategyType(config?.strategy_type ?? strategies[0]?.type ?? "");
    setMessage("");
    setError("");
  }

  async function handleSubmit(request: StrategyConfigCreateRequest) {
    try {
      setSaving(true);
      setError("");
      setMessage("");
      if (editingId) {
        const updated = await updateStrategyConfig(editingId, request);
        setConfigs((current) => current.map((row) => (row.id === updated.id ? updated : row)));
        setMessage("전략 설정이 수정되었습니다.");
      } else {
        const created = await createStrategyConfig(request);
        setConfigs((current) => [created, ...current]);
        setMessage("새 전략 설정이 저장되었습니다.");
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack">
      {loading ? <div className="notice">불러오는 중</div> : null}
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice notice-success">{message}</div> : null}

      <section className="toolbar">
        <label>
          편집할 설정
          <select value={editingId ?? ""} onChange={(event) => selectEditingConfig(event.target.value)}>
            <option value="">새 설정 만들기</option>
            {configs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.name} / {config.symbol}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>{editingConfig ? "전략 설정 수정" : "새 전략 설정"}</h2>
            <span>공통 설정과 전략별 파라미터</span>
          </div>
        </div>
        <SettingsForm
          key={editingConfig?.id ?? "new"}
          strategies={strategies}
          schema={schema}
          selectedStrategyType={selectedStrategyType}
          editingConfig={editingConfig}
          onStrategyTypeChange={setSelectedStrategyType}
          onSubmit={handleSubmit}
          saving={saving}
        />
      </section>

      <section className="panel">
        <div className="panel-header"><div><h2>설정 목록</h2><span>저장된 전략 설정</span></div></div>
        <Table columns={configColumns} rows={configs} getRowKey={(row) => row.id} />
      </section>
    </div>
  );
}

const configColumns: TableColumn<StrategyConfig>[] = [
  { key: "id", header: "ID", render: (row) => row.id },
  { key: "name", header: "이름", render: (row) => row.name },
  { key: "strategy", header: "전략", render: (row) => translateStrategyType(row.strategy_type) },
  { key: "symbol", header: "종목", render: (row) => row.symbol },
  { key: "capital", header: "초기 투자금", align: "right", render: (row) => formatMoney(row.initial_capital) },
  { key: "fee", header: "수수료율", align: "right", render: (row) => row.fee_rate },
  { key: "updated", header: "수정일", render: (row) => row.updated_at.slice(0, 10) },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
