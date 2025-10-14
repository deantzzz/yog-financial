'use client';

import { useState } from 'react';

import { PolicyRow, fetchPolicySnapshots } from '../../features/workspaces/services';

function parseNumeric(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    const normalised = value.replace(/,/g, '').trim();
    if (!normalised) {
      return null;
    }
    const parsed = Number(normalised);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatCurrency(value: number | null, suffix = ''): string {
  if (value === null) {
    return '—';
  }
  return `¥ ${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${suffix}`;
}

function formatNumber(value: number | null, fractionDigits = 2, suffix = ''): string {
  if (value === null) {
    return '—';
  }
  return `${value.toFixed(fractionDigits)}${suffix}`;
}

function flattenObjectEntries(data: Record<string, unknown>, prefix = ''): Array<{ label: string; value: unknown }> {
  return Object.entries(data).flatMap(([key, value]) => {
    const label = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenObjectEntries(value as Record<string, unknown>, label);
    }
    return [{ label, value }];
  });
}

function formatValue(value: unknown): string {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value);
}

export default function PolicyPage() {
  const [workspace, setWorkspace] = useState('2025-01');
  const [policies, setPolicies] = useState<PolicyRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchPolicySnapshots(workspace);
      setPolicies(rows);
      if (rows.length === 0) {
        setError('当前工作区尚无口径快照，请先上传工资口径表或名册');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
      setPolicies([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-800">口径快照</h1>
        <p className="text-sm text-slate-600">展示每位员工在当前工作区生效的薪资、津贴、社保与税费参数。</p>
      </header>
      <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <label className="flex flex-col text-sm">
          工作区
          <input
            value={workspace}
            onChange={(event) => setWorkspace(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          onClick={handleLoad}
          disabled={loading}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? '加载中…' : '加载口径'}
        </button>
        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>

      <div className="space-y-3">
        {policies.length === 0 && !loading ? (
          <p className="text-sm text-slate-500">{error ?? '尚未加载口径数据'}</p>
        ) : null}
        {policies.length > 0 && (
          <ul className="space-y-3">
            {policies.map((policy) => {
              const baseLabel = policy.mode === 'HOURLY' ? '基准时薪' : '基础月薪';
              const baseValue = policy.mode === 'HOURLY' ? formatCurrency(policy.base_rate, '/小时') : formatCurrency(policy.base_amount);
              const ssEmployee = parseNumeric(policy.social_security_json['employee']);
              const ssEmployer = parseNumeric(policy.social_security_json['employer']);
              const ssDisplay = [
                ssEmployee !== null ? `个人 ${formatNumber(ssEmployee * 100, 2, '%')}` : null,
                ssEmployer !== null ? `公司 ${formatNumber(ssEmployer * 100, 2, '%')}` : null,
              ]
                .filter(Boolean)
                .join(' / ');

              const allowanceEntries = flattenObjectEntries(policy.allowances_json);
              const deductionEntries = flattenObjectEntries(policy.deductions_json);

              return (
                <li key={`${policy.employee_name_norm}-${policy.period_month}`} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-lg font-medium text-slate-800">{policy.employee_name_norm}</h3>
                    <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{policy.period_month}</span>
                  </div>
                  <dl className="grid gap-2 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-slate-500">计薪模式</dt>
                      <dd className="font-medium text-slate-800">{policy.mode === 'HOURLY' ? '小时工' : '月薪制'}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">{baseLabel}</dt>
                      <dd className="font-medium text-slate-800">{baseValue}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">工作日加班</dt>
                      <dd className="font-medium text-slate-800">
                        {policy.ot_weekday_rate !== null
                          ? `${formatCurrency(policy.ot_weekday_rate, '/小时')}`
                          : formatNumber(policy.ot_weekday_multiplier, 2, '×')}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">周末/节假日加班</dt>
                      <dd className="font-medium text-slate-800">
                        {policy.ot_weekend_rate !== null
                          ? `${formatCurrency(policy.ot_weekend_rate, '/小时')}`
                          : formatNumber(policy.ot_weekend_multiplier, 2, '×')}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">社保/公积金</dt>
                      <dd className="font-medium text-slate-800">{ssDisplay || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">有效期</dt>
                      <dd className="font-medium text-slate-800">
                        {policy.valid_from || policy.valid_to
                          ? `${policy.valid_from ?? '开始生效'} → ${policy.valid_to ?? '长期有效'}`
                          : '未指定'}
                      </dd>
                    </div>
                  </dl>

                  {allowanceEntries.length > 0 && (
                    <section className="rounded-md bg-emerald-50 p-3 text-sm">
                      <h4 className="font-medium text-emerald-700">固定津贴 / 奖励</h4>
                      <ul className="mt-1 space-y-1">
                        {allowanceEntries.map(({ label, value }) => (
                          <li key={label} className="flex justify-between text-emerald-800">
                            <span>{label}</span>
                            <span>{formatValue(value)}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {deductionEntries.length > 0 && (
                    <section className="rounded-md bg-rose-50 p-3 text-sm">
                      <h4 className="font-medium text-rose-700">固定扣款 / 处罚</h4>
                      <ul className="mt-1 space-y-1">
                        {deductionEntries.map(({ label, value }) => (
                          <li key={label} className="flex justify-between text-rose-800">
                            <span>{label}</span>
                            <span>{formatValue(value)}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  <footer className="text-xs text-slate-500">
                    <p>来源：{policy.source_file ?? '未记录'}{policy.source_sheet ? ` · ${policy.source_sheet}` : ''}</p>
                    <p>快照哈希：{policy.snapshot_hash ?? '—'}</p>
                  </footer>

                  <details className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
                    <summary className="cursor-pointer font-medium text-slate-700">查看原始快照 JSON</summary>
                    <pre className="mt-2 max-h-56 overflow-auto rounded bg-black/80 p-3 text-xs text-emerald-100">
                      {JSON.stringify(policy.raw_snapshot, null, 2)}
                    </pre>
                  </details>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
