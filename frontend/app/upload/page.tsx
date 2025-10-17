'use client';

import { useState } from 'react';

import {
  WorkspaceJob,
  WorkspaceDocument,
  fetchWorkspaceOverview,
  uploadWorkspaceFiles,
  updateWorkspaceDocument
} from '../../features/workspaces/services';
import OcrReviewDialog from '../../components/OcrReviewDialog';

export default function UploadPage() {
  const [workspace, setWorkspace] = useState('2025-01');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [files, setFiles] = useState<WorkspaceJob[]>([]);
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<WorkspaceDocument | null>(null);
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const refreshFiles = async (ws: string) => {
    try {
      const overview = await fetchWorkspaceOverview(ws);
      setFiles(overview.files ?? []);
      setDocuments(overview.documents ?? []);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? `加载失败：${error.message}` : '加载失败');
    }
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setMessage('请选择需要上传的文件');
      return;
    }
    setLoading(true);
    setMessage(null);

    try {
      const jobs = await uploadWorkspaceFiles(workspace, selectedFiles);
      const count = jobs.length || selectedFiles.length;
      setMessage(count > 1 ? `上传成功，${count} 个文件的解析任务已排队` : '上传成功，解析任务已排队');
      setSelectedFiles([]);
      setFileInputKey((key) => key + 1);
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

  const openReview = (document: WorkspaceDocument) => {
    setSelectedDocument(document);
    setReviewError(null);
  };

  const closeReview = () => {
    setSelectedDocument(null);
    setReviewError(null);
  };

  const handleConfirmReview = async (documentId: string, table: string[][]) => {
    setReviewSaving(true);
    setReviewError(null);
    try {
      const updated = await updateWorkspaceDocument(workspace, documentId, {
        ocrTable: table,
        reviewStatus: 'confirmed'
      });
      setDocuments((items) => items.map((item) => (item.document_id === updated.document_id ? updated : item)));
      setMessage('识别结果已保存');
      setSelectedDocument(null);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : '保存失败，请稍后再试');
    } finally {
      setReviewSaving(false);
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
              key={fileInputKey}
              type="file"
              multiple
              onChange={(event) => {
                const fileList = event.target.files;
                if (!fileList) {
                  setSelectedFiles([]);
                  return;
                }
                setSelectedFiles(Array.from(fileList));
              }}
              className="mt-1 text-sm"
            />
            {selectedFiles.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-slate-500">
                {selectedFiles.map((file, index) => (
                  <li key={`${file.name}-${index}`} className="truncate">
                    {file.name}
                  </li>
                ))}
              </ul>
            )}
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

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-slate-800">OCR 识别任务</h2>
          <button onClick={() => refreshFiles(workspace)} className="text-sm text-primary hover:text-accent">
            刷新
          </button>
        </div>
        {documents.length === 0 ? (
          <p className="text-sm text-slate-500">暂无待审查的识别结果。</p>
        ) : (
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead>
              <tr className="bg-slate-100 text-left">
                <th className="px-3 py-2 font-medium">文件名</th>
                <th className="px-3 py-2 font-medium">置信度</th>
                <th className="px-3 py-2 font-medium">审查状态</th>
                <th className="px-3 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((document) => (
                <tr key={document.document_id}>
                  <td className="px-3 py-2">{document.source_file}</td>
                  <td className="px-3 py-2 text-slate-600">
                    {document.ocr_confidence !== null ? document.ocr_confidence.toFixed(2) : '-'}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded px-2 py-1 text-xs font-medium ${
                        document.review_status === 'confirmed'
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {document.review_status === 'confirmed' ? '已确认' : '待审查'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => openReview(document)}
                      className="text-sm text-primary hover:text-accent"
                    >
                      {document.review_status === 'confirmed' ? '查看/调整' : '审查调整'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedDocument && (
        <OcrReviewDialog
          document={selectedDocument}
          onClose={closeReview}
          onConfirm={(table) => handleConfirmReview(selectedDocument.document_id, table)}
          saving={reviewSaving}
          error={reviewError}
        />
      )}
    </section>
  );
}
