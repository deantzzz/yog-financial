"use client";

import { useEffect, useMemo, useState } from 'react';

import Image from 'next/image';

import DataGrid, { type Column, type RowsChangeData, textEditor } from 'react-data-grid';

import { API_BASE_URL } from '../lib/api';
import { WorkspaceDocument } from '../features/workspaces/services';

type GridRow = {
  id: string;
} & Record<string, string>;

type Props = {
  document: WorkspaceDocument;
  onClose: () => void;
  onConfirm: (table: string[][]) => void;
  saving?: boolean;
  error?: string | null;
};

function dedupeRepeatingSegments(value: string): string {
  const trimmed = String(value ?? '').replace(/\s+/g, ' ').trim();
  if (!trimmed) {
    return '';
  }
  const tokens = trimmed.split(' ');
  if (tokens.length <= 1) {
    return trimmed;
  }
  const [first, ...rest] = tokens;
  if (rest.every((token) => token === first)) {
    return first;
  }
  return trimmed;
}

function normaliseTable(table: string[][]): string[][] {
  if (!Array.isArray(table) || table.length === 0) {
    return [['']];
  }
  const columnCount = table.reduce((max, row) => Math.max(max, Array.isArray(row) ? row.length : 0), 0) || 1;
  return table.map((row) => {
    const cells = Array.isArray(row) ? row.map((cell) => dedupeRepeatingSegments(cell)) : [];
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

  const columns = useMemo<Column<GridRow>[]>(() => {
    return Array.from({ length: columnCount }, (_, columnIndex) => ({
      key: `col-${columnIndex}`,
      name: `列 ${columnIndex + 1}`,
      editor: textEditor,
      resizable: true,
      minWidth: 120,
      cellClass: 'text-sm text-slate-800',
      headerCellClass: 'bg-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500',
    }));
  }, [columnCount]);

  const rows = useMemo<GridRow[]>(() => {
    return tableData.map((row, rowIndex) => {
      const record: GridRow = { id: String(rowIndex) };
      for (let columnIndex = 0; columnIndex < columnCount; columnIndex += 1) {
        record[`col-${columnIndex}`] = row[columnIndex] ?? '';
      }
      return record;
    });
  }, [tableData, columnCount]);

  const handleRowsChange = (updatedRows: GridRow[], _meta: RowsChangeData<GridRow>) => {
    setTableData(
      updatedRows.map((row) => {
        const cells: string[] = [];
        for (let columnIndex = 0; columnIndex < columnCount; columnIndex += 1) {
          const key = `col-${columnIndex}`;
          cells.push(dedupeRepeatingSegments(row[key] ?? ''));
        }
        return cells;
      })
    );
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
            <div className="relative h-full min-h-[320px] w-full">
              <Image
                src={imageUrl}
                alt={document.source_file}
                fill
                sizes="(min-width: 1024px) 50vw, 100vw"
                className="object-contain"
                unoptimized
              />
            </div>
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
              <div className="h-full overflow-hidden rounded-md border border-slate-200">
                <DataGrid
                  className="rdg-light h-full"
                  columns={columns}
                  rows={rows}
                  rowKeyGetter={(row) => row.id}
                  style={{ blockSize: '100%' }}
                  onRowsChange={handleRowsChange}
                />
              </div>
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
