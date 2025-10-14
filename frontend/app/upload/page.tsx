'use client';

import { useState } from 'react';

import {
  WorkspaceJob,
  fetchWorkspaceOverview,
  uploadWorkspaceFile
} from '../../features/workspaces/services';

export default function UploadPage() {
  const [workspace, setWorkspace] = useState('2025-01');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [files, setFiles] = useState<WorkspaceJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refreshFiles = async (ws: string) => {
    try {
      const overview = await fetchWorkspaceOverview(ws);
      setFiles(overview.files ?? []);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? `加载失败：${error.message}` : '加载失败');
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setMessage('请选择需要上传的文件');
      return;
    }
    setLoading(true);
    setMessage(null);

    try {
      await uploadWorkspaceFile(workspace, selectedFile);
      setMessage('上传成功，解析任务已排队');
      setSelectedFile(null);
      await refreshFiles(workspace);
    } catch (error) {
      if (error instanceof Error) {
        setMessage(`上传失败：${error.message}`);
      } else {
        setMessage('上传失败：未知错误');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-800">文件上传与任务监控</h1>
        <p className="text-sm text-slate-600">上传原始文件后，后端会自动触发模板识别、解析和事实层写入。</p>
      </header>

      <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col text-sm">
            工作区（YYYY-MM）
            <input
              value={workspace}
              onChange={(event) => setWorkspace(event.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2"
              placeholder="2025-01"
            />
          </label>
          <label className="flex flex-col text-sm">
            选择文件
            <input
              type="file"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              className="mt-1 text-sm"
            />
          </label>
        </div>
        <button
          onClick={handleUpload}
          disabled={loading}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? '上传中…' : '上传文件'}
        </button>
        {message && <p className="text-sm text-slate-600">{message}</p>}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-slate-800">工作区文件状态</h2>
          <button
            onClick={() => refreshFiles(workspace)}
            className="text-sm text-primary hover:text-accent"
          >
            刷新
          </button>
        </div>
        {files.length === 0 ? (
          <p className="text-sm text-slate-500">暂无文件，请先上传。</p>
        ) : (
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead>
              <tr className="bg-slate-100 text-left">
                <th className="px-3 py-2 font-medium">文件名</th>
                <th className="px-3 py-2 font-medium">状态</th>
                <th className="px-3 py-2 font-medium">错误信息</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {files.map((file) => (
                <tr key={file.job_id ?? file.filename}>
                  <td className="px-3 py-2">{file.filename ?? '-'}</td>
                  <td className="px-3 py-2">
                    <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                      {file.status ?? '-'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-500">{file.error ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
