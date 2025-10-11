'use client';

import { useState } from 'react';
import { apiFetch } from '../../lib/api';

type PolicyRow = {
  employee_name_norm: string;
  period_month: string;
  mode: string;
  base_amount: number;
  allowances_json?: Record<string, unknown>;
  deductions_json?: Record<string, unknown>;
  social_security_json?: Record<string, unknown>;
  tax_json?: Record<string, unknown>;
};

type PolicyResponse = {
  items: PolicyRow[];
};

export default function PolicyPage() {
  const [workspace, setWorkspace] = useState('2025-01');
  const [policies, setPolicies] = useState<PolicyRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<PolicyResponse>(`/api/workspaces/${workspace}/policy`);
      setPolicies(data.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-800">口径快照</h1>
        <p className="text-sm text-slate-600">展示每位员工在当前工作区生效的薪资与税费配置。</p>
      </header>
      <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <label className="flex flex-col text-sm">
          工作区
          <input value={workspace} onChange={(event) => setWorkspace(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" />
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
        {policies.length === 0 ? (
          <p className="text-sm text-slate-500">{loading ? '加载中…' : '尚未加载口径数据'}</p>
        ) : (
          <ul className="space-y-3">
            {policies.map((policy) => (
              <li key={`${policy.employee_name_norm}-${policy.period_month}`} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-lg font-medium text-slate-800">{policy.employee_name_norm}</h3>
                  <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{policy.period_month}</span>
                </div>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-slate-500">计薪模式</dt>
                    <dd className="font-medium text-slate-800">{policy.mode}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">基础金额/时薪</dt>
                    <dd className="font-medium text-slate-800">¥ {policy.base_amount?.toFixed(2)}</dd>
                  </div>
                </dl>
                <details className="mt-3 rounded border border-slate-200 bg-slate-50 p-3 text-sm">
                  <summary className="cursor-pointer font-medium text-slate-700">展开更多参数</summary>
                  <pre className="mt-2 max-h-56 overflow-auto rounded bg-black/80 p-3 text-xs text-emerald-100">{JSON.stringify(
                    {
                      allowances: policy.allowances_json,
                      deductions: policy.deductions_json,
                      social_security: policy.social_security_json,
                      tax: policy.tax_json
                    },
                    null,
                    2
                  )}</pre>
                </details>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
