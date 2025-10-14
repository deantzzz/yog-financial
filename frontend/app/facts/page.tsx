'use client';

import { useState } from 'react';

import { FactRecord, fetchFactRecords } from '../../features/workspaces/services';

export default function FactsPage() {
  const [workspace, setWorkspace] = useState('2025-01');
  const [name, setName] = useState('');
  const [metric, setMetric] = useState('');
  const [records, setRecords] = useState<FactRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleQuery = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFactRecords(workspace, {
        employeeName: name || undefined,
        metricCode: metric || undefined
      });
      setRecords(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '查询失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-800">事实数据浏览</h1>
        <p className="text-sm text-slate-600">按员工与指标过滤，查看解析出的原子事实，并关注置信度。</p>
      </header>
      <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="flex flex-col text-sm">
            工作区
            <input value={workspace} onChange={(event) => setWorkspace(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="flex flex-col text-sm">
            姓名关键词
            <input value={name} onChange={(event) => setName(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="flex flex-col text-sm">
            指标代码
            <input value={metric} onChange={(event) => setMetric(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" placeholder="HOUR_TOTAL" />
          </label>
        </div>
        <button
          onClick={handleQuery}
          disabled={loading}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? '查询中…' : '查询'}
        </button>
        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-100">
            <tr className="text-left">
              <th className="px-3 py-2 font-medium">姓名</th>
              <th className="px-3 py-2 font-medium">指标</th>
              <th className="px-3 py-2 font-medium">数值</th>
              <th className="px-3 py-2 font-medium">单位</th>
              <th className="px-3 py-2 font-medium">来源文件</th>
              <th className="px-3 py-2 font-medium">置信度</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {records.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-sm text-slate-500">
                  {loading ? '加载中…' : '暂无数据'}
                </td>
              </tr>
            ) : (
              records.map((record, index) => {
                const confidenceValue = record.confidence;
                const rowConfidence = confidenceValue ?? 0;
                return (
                  <tr key={`${record.employee_name}-${index}`} className={rowConfidence < 0.7 ? 'bg-orange-50' : ''}>
                    <td className="px-3 py-2">{record.employee_name}</td>
                    <td className="px-3 py-2">{record.metric_code}</td>
                    <td className="px-3 py-2">{record.metric_value}</td>
                    <td className="px-3 py-2">{record.unit}</td>
                    <td className="px-3 py-2 text-slate-500">{record.source_file}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded px-2 py-1 text-xs font-medium ${rowConfidence < 0.7 ? 'bg-orange-200 text-orange-800' : 'bg-emerald-100 text-emerald-700'}`}>
                        {confidenceValue !== null ? confidenceValue.toFixed(2) : '—'}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
