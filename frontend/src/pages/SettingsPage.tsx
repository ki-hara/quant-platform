import { useEffect, useMemo, useState } from "react";
import { RotateCcw, Save, Trash2 } from "lucide-react";
import {
  applyStrategyConfigSnapshot,
  createStrategyConfig,
  createStrategyConfigSnapshot,
  deleteStrategyConfig,
  deleteStrategyConfigSnapshot,
  getStrategySchema,
  listStrategies,
  listStrategyConfigSnapshots,
  listStrategyConfigs,
  updateStrategyConfig,
} from "../api/strategies";
import { SettingsForm } from "../components/SettingsForm";
import { Table, type TableColumn } from "../components/Table";
import type {
  StrategyConfig,
  StrategyConfigCreateRequest,
  StrategyConfigSnapshot,
  StrategyInfo,
  StrategySchema,
} from "../types/api";
import { formatMoney, translateStrategyType } from "../utils/format";
import { rememberStrategyConfigId, resolveRememberedStrategyConfigId } from "../utils/strategySelection";

export function SettingsPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [configs, setConfigs] = useState<StrategyConfig[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedStrategyType, setSelectedStrategyType] = useState("");
  const [schema, setSchema] = useState<StrategySchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [snapshotSaving, setSnapshotSaving] = useState(false);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshots, setSnapshots] = useState<StrategyConfigSnapshot[]>([]);
  const [snapshotName, setSnapshotName] = useState("");
  const [snapshotMemo, setSnapshotMemo] = useState("");
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
        const rememberedId = resolveRememberedStrategyConfigId(configRows);
        const rememberedConfig = configRows.find((row) => row.id === rememberedId);
        setEditingId(rememberedId);
        setSelectedStrategyType(rememberedConfig?.strategy_type ?? strategyRows[0]?.type ?? "");
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

  useEffect(() => {
    let cancelled = false;

    async function loadSnapshots() {
      if (!editingId) {
        setSnapshots([]);
        setSnapshotLoading(false);
        return;
      }

      try {
        setSnapshotLoading(true);
        setSnapshots([]);
        const rows = await listStrategyConfigSnapshots(editingId);
        if (!cancelled) {
          setSnapshots(rows);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(errorMessage(caught));
        }
      } finally {
        if (!cancelled) {
          setSnapshotLoading(false);
        }
      }
    }

    void loadSnapshots();

    return () => {
      cancelled = true;
    };
  }, [editingId]);

  function selectEditingConfig(value: string) {
    const configId = Number(value) || null;
    rememberStrategyConfigId(configId);
    setEditingId(configId);
    const config = configs.find((row) => row.id === configId);
    setSelectedStrategyType(config?.strategy_type ?? strategies[0]?.type ?? "");
    setSnapshots([]);
    setSnapshotName("");
    setSnapshotMemo("");
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
        rememberStrategyConfigId(updated.id);
        setMessage("기존 설정을 수정했습니다.");
      } else {
        const created = await createStrategyConfig(request);
        setConfigs((current) => [created, ...current]);
        setEditingId(created.id);
        setSelectedStrategyType(created.strategy_type);
        rememberStrategyConfigId(created.id);
        setMessage("새 설정을 저장했습니다.");
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteConfig(config: StrategyConfig) {
    if (!window.confirm(`${config.name} / ${config.symbol} 설정을 삭제할까요? 거래 이력은 보존됩니다.`)) return;
    try {
      setSaving(true);
      setError("");
      setMessage("");
      await deleteStrategyConfig(config.id);
      setConfigs((current) => current.filter((row) => row.id !== config.id));
      if (editingId === config.id) {
        setEditingId(null);
        rememberStrategyConfigId(null);
      }
      setMessage("설정을 삭제했습니다. 기존 거래 이력은 유지됩니다.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateSnapshot() {
    if (!editingId) return;
    const name = snapshotName.trim();
    if (!name) {
      setError("스냅샷 이름을 입력해 주세요.");
      return;
    }

    try {
      setSnapshotSaving(true);
      setError("");
      setMessage("");
      const created = await createStrategyConfigSnapshot(editingId, {
        name,
        memo: snapshotMemo.trim() || null,
      });
      setSnapshots((current) => [created, ...current]);
      setSnapshotName("");
      setSnapshotMemo("");
      setMessage("현재 설정을 스냅샷으로 저장했습니다.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSnapshotSaving(false);
    }
  }

  async function handleApplySnapshot(snapshot: StrategyConfigSnapshot) {
    if (!editingId) return;
    if (!window.confirm(`"${snapshot.name}" 스냅샷을 현재 설정에 적용할까요?\n기존 포지션과 거래 이력은 유지됩니다.`)) return;

    try {
      setSnapshotSaving(true);
      setError("");
      setMessage("");
      const updated = await applyStrategyConfigSnapshot(editingId, snapshot.id);
      setConfigs((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setSelectedStrategyType(updated.strategy_type);
      setMessage("스냅샷을 현재 설정에 적용했습니다.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSnapshotSaving(false);
    }
  }

  async function handleDeleteSnapshot(snapshot: StrategyConfigSnapshot) {
    if (!editingId) return;
    if (!window.confirm(`"${snapshot.name}" 스냅샷을 삭제할까요?`)) return;

    try {
      setSnapshotSaving(true);
      setError("");
      setMessage("");
      await deleteStrategyConfigSnapshot(editingId, snapshot.id);
      setSnapshots((current) => current.filter((row) => row.id !== snapshot.id));
      setMessage("스냅샷을 삭제했습니다.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSnapshotSaving(false);
    }
  }

  const isBusy = saving || snapshotSaving;

  const columns: TableColumn<StrategyConfig>[] = [
    ...configColumns,
    {
      key: "delete",
      header: "삭제",
      align: "center",
      render: (row) => (
        <button className="icon-button" type="button" disabled={isBusy} onClick={() => handleDeleteConfig(row)}>
          <Trash2 aria-hidden="true" size={15} />
        </button>
      ),
    },
  ];

  return (
    <div className="page-stack">
      {loading ? <div className="notice">불러오는 중...</div> : null}
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
            <h2>{editingConfig ? "기존 설정 수정" : "새 설정"}</h2>
            <span>공통 설정과 전략별 파라미터</span>
          </div>
        </div>
        <SettingsForm
          key={editingConfig ? `${editingConfig.id}:${editingConfig.updated_at}` : "new"}
          strategies={strategies}
          schema={schema}
          selectedStrategyType={selectedStrategyType}
          editingConfig={editingConfig}
          onStrategyTypeChange={setSelectedStrategyType}
          onSubmit={handleSubmit}
          saving={isBusy}
        />
      </section>

      {editingConfig ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>설정 스냅샷</h2>
              <span>현재 설정을 저장하고 같은 구성에 다시 적용할 수 있습니다.</span>
            </div>
          </div>

          <div className="form-grid">
            <label>
              스냅샷 이름
              <input
                value={snapshotName}
                onChange={(event) => setSnapshotName(event.target.value)}
                placeholder="예: 고점 추종형"
              />
            </label>
            <label>
              메모
              <input
                value={snapshotMemo}
                onChange={(event) => setSnapshotMemo(event.target.value)}
                placeholder="선택 사항"
              />
            </label>
            <button type="button" disabled={isBusy} onClick={handleCreateSnapshot}>
              <Save aria-hidden="true" size={16} />
              스냅샷 저장
            </button>
          </div>

          <div className="form-stack" style={{ marginTop: 14 }}>
            {snapshotLoading ? <div className="notice">스냅샷을 불러오는 중입니다.</div> : null}
            <Table
              columns={snapshotColumns(handleApplySnapshot, handleDeleteSnapshot, isBusy)}
              rows={snapshots}
              getRowKey={(row) => row.id}
              emptyText="저장된 스냅샷이 없습니다"
            />
          </div>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>설정 목록</h2>
            <span>저장된 기존 설정</span>
          </div>
        </div>
        <Table columns={columns} rows={configs} getRowKey={(row) => row.id} />
      </section>
    </div>
  );
}

function snapshotColumns(
  onApply: (snapshot: StrategyConfigSnapshot) => void,
  onDelete: (snapshot: StrategyConfigSnapshot) => void,
  disabled: boolean,
): TableColumn<StrategyConfigSnapshot>[] {
  return [
    { key: "name", header: "이름", className: "snapshot-name-cell", render: (row) => row.name },
    { key: "memo", header: "메모", className: "snapshot-memo-cell", render: (row) => row.memo ?? "-" },
    { key: "created", header: "생성일", align: "right", className: "snapshot-date-cell", render: (row) => row.created_at.slice(0, 10) },
    {
      key: "actions",
      header: "작업",
      align: "right",
      className: "snapshot-action-cell",
      render: (row) => (
        <div className="inline-actions">
          <button
            className="icon-button"
            type="button"
            disabled={disabled}
            title="적용"
            aria-label={`${row.name} 스냅샷 적용`}
            onClick={() => onApply(row)}
          >
            <RotateCcw aria-hidden="true" size={15} />
          </button>
          <button
            className="icon-button"
            type="button"
            disabled={disabled}
            title="삭제"
            aria-label={`${row.name} 스냅샷 삭제`}
            onClick={() => onDelete(row)}
          >
            <Trash2 aria-hidden="true" size={15} />
          </button>
        </div>
      ),
    },
  ];
}

const configColumns: TableColumn<StrategyConfig>[] = [
  { key: "id", header: "ID", render: (row) => row.id },
  { key: "name", header: "이름", render: (row) => row.name },
  { key: "strategy", header: "전략", render: (row) => translateStrategyType(row.strategy_type) },
  { key: "symbol", header: "종목", render: (row) => row.symbol },
  { key: "capital", header: "초기 자산", align: "right", render: (row) => formatMoney(row.initial_capital) },
  { key: "fee", header: "수수료율", align: "right", render: (row) => row.fee_rate },
  { key: "updated", header: "수정일", render: (row) => row.updated_at.slice(0, 10) },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";
}
