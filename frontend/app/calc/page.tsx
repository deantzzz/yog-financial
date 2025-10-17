'use client';

import { useState } from 'react';

import {
  PayrollResult,
  fetchPayrollResults,
  triggerPayrollCalculation
} from '../../features/workspaces/services';

export default function CalcPage() {
  const [workspace, setWorkspace] = useState('2025-01');
  const [period, setPeriod] = useState('2025-01');
  const [employees, setEmployees] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [results, setResults] = useState<PayrollResult[]>([]);

  const handleCalc = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await triggerPayrollCalculation(workspace, {
        period,
        selected: employees
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean)
      });
      const resultPeriod = response.period ?? period;
      if (response.period && response.period !== period) {
        setPeriod(response.period);
      }
      setResults(response.items);
      setMessage(
        response.items.length === 0
          ? '计算已完成，但未生成结果，请检查输入数据。'
          : `计算完成，生成 ${resultPeriod} 的 ${response.items.length} 条结果。`
      );
    } catch (error) {
      setMessage(error instanceof Error ? `计算失败：${error.message}` : '计算失败');
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await fetchPayrollResults(workspace, period);
      setResults(data);
      if (data.length === 0) {
        setMessage('暂无结果，请确认任务是否完成。');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '查询失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-800">计算与导出</h1>
        <p className="text-sm text-slate-600">触发工资计算并查询结果，完成后可通过后端导出银行与税务文件。</p>
      </header>

      <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="flex flex-col text-sm">
            工作区
            <input value={workspace} onChange={(event) => setWorkspace(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="flex flex-col text-sm">
            计薪月份
            <input value={period} onChange={(event) => setPeriod(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="flex flex-col text-sm">
            指定员工（可选，逗号分隔）
            <input value={employees} onChange={(event) => setEmployees(event.target.value)} className="mt-1 rounded-md border border-slate-300 px-3 py-2" placeholder="张三, 李四" />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleCalc}
            disabled={loading}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? '处理中…' : '触发计算'}
          </button>
          <button
            onClick={loadResults}
            disabled={loading}
            className="inline-flex items-center justify-center rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            刷新结果
          </button>
        </div>
        {message && <p className="text-sm text-slate-600">{message}</p>}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-100">
            <tr className="text-left">
              <th className="px-3 py-2 font-medium">姓名</th>
              <th className="px-3 py-2 font-medium">月份</th>
              <th className="px-3 py-2 font-medium">应发</th>
              <th className="px-3 py-2 font-medium">实发</th>
              <th className="px-3 py-2 font-medium">基本</th>
              <th className="px-3 py-2 font-medium">加班</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {results.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-sm text-slate-500">
                  {loading ? '加载中…' : '暂无结果'}
                </td>
              </tr>
            ) : (
              results.map((row) => (
                <tr key={`${row.employee_name_norm}-${row.period_month}`}>
                  <td className="px-3 py-2">{row.employee_name_norm}</td>
                  <td className="px-3 py-2">{row.period_month}</td>
                  <td className="px-3 py-2">¥ {row.gross_pay.toFixed(2)}</td>
                  <td className="px-3 py-2">¥ {row.net_pay.toFixed(2)}</td>
                  <td className="px-3 py-2">¥ {row.base_pay.toFixed(2)}</td>
                  <td className="px-3 py-2">¥ {row.ot_pay.toFixed(2)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
