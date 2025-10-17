import { useEffect, useMemo, useState } from 'react';

import { API_BASE_URL } from '../lib/api';
import { WorkspaceDocument } from '../features/workspaces/services';

type Props = {
  document: WorkspaceDocument;
  onClose: () => void;
  onConfirm: (table: string[][]) => void;
  saving?: boolean;
  error?: string | null;
};

function normaliseTable(table: string[][]): string[][] {
  if (!Array.isArray(table) || table.length === 0) {
    return [['']];
  }
  const columnCount = table.reduce((max, row) => Math.max(max, Array.isArray(row) ? row.length : 0), 0) || 1;
  return table.map((row) => {
    const cells = Array.isArray(row) ? row.map((cell) => String(cell ?? '')) : [];
    while (cells.length < columnCount) {
      cells.push('');
    }
    return cells.slice(0, columnCount);
  });
}

export default function OcrReviewDialog({ document, onClose, onConfirm, saving = false, error = null }: Props) {
  const [tableData, setTableData] = useState<string[][]>(() => normaliseTable(document.ocr_table));

  useEffect(() => {
    setTableData(normaliseTable(document.ocr_table));
  }, [document]);

  const columnCount = useMemo(() => tableData.reduce((max, row) => Math.max(max, row.length), 0) || 1, [tableData]);

  const handleCellChange = (rowIndex: number, columnIndex: number, value: string) => {
    setTableData((rows) => {
      const draft = rows.map((row) => row.slice());
      if (!draft[rowIndex]) {
        draft[rowIndex] = new Array(columnCount).fill('');
      }
      draft[rowIndex][columnIndex] = value;
      return draft;
    });
  };

  const handleAddRow = () => {
    setTableData((rows) => {
      const next = rows.map((row) => row.slice());
      next.push(new Array(columnCount).fill(''));
      return next;
    });
  };

  const handleAddColumn = () => {
    setTableData((rows) => rows.map((row) => [...row, '']));
  };

  const handleRemoveRow = () => {
    setTableData((rows) => (rows.length > 1 ? rows.slice(0, -1) : rows));
  };

  const handleRemoveColumn = () => {
    if (columnCount <= 1) {
      return;
    }
    setTableData((rows) => rows.map((row) => row.slice(0, columnCount - 1)));
  };

  const handleReset = () => {
    setTableData(normaliseTable(document.ocr_table));
  };

  const imageUrl = document.image_url.startsWith('http')
    ? document.image_url
    : `${API_BASE_URL}${document.image_url}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="flex h-full w-full max-w-6xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">审查识别结果</h2>
            <p className="text-sm text-slate-500">{document.source_file}</p>
          </div>
          <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700">
            关闭
          </button>
        </header>

        <div className="flex flex-1 flex-col gap-4 overflow-hidden p-6 lg:flex-row">
          <div className="flex-1 overflow-auto rounded border border-slate-200 bg-slate-50 p-4">
            <img src={imageUrl} alt={document.source_file} className="h-full w-full object-contain" />
          </div>
          <div className="flex flex-1 flex-col overflow-hidden rounded border border-slate-200">
            <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
              <div className="space-x-2 text-xs text-slate-600">
                <button onClick={handleAddRow} className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300">
                  添加行
                </button>
                <button onClick={handleAddColumn} className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300">
                  添加列
                </button>
                <button
                  onClick={handleRemoveRow}
                  className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300"
                  disabled={tableData.length <= 1}
                >
                  删除末行
                </button>
                <button
                  onClick={handleRemoveColumn}
                  className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300"
                  disabled={columnCount <= 1}
                >
                  删除末列
                </button>
                <button onClick={handleReset} className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300">
                  重置
                </button>
              </div>
              {error && <p className="text-xs text-red-500">{error}</p>}
            </div>
            <div className="flex-1 overflow-auto p-4">
              <table className="min-w-full table-fixed border-collapse text-sm">
                <tbody>
                  {tableData.map((row, rowIndex) => (
                    <tr key={rowIndex} className="border-b border-slate-200 last:border-b-0">
                      {row.map((cell, columnIndex) => (
                        <td key={columnIndex} className="border-r border-slate-200 last:border-r-0 p-1 align-top">
                          <input
                            value={cell}
                            onChange={(event) => handleCellChange(rowIndex, columnIndex, event.target.value)}
                            className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-primary focus:outline-none"
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <footer className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
          <p className="text-xs text-slate-500">
            对照原图调整表格后点击确认，系统将保存修改并标记为已审查。
          </p>
          <div className="space-x-3">
            <button onClick={onClose} className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600">
              取消
            </button>
            <button
              onClick={() => onConfirm(tableData)}
              disabled={saving}
              className="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? '保存中…' : '确认审查结果'}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
