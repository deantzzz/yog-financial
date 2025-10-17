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
  const [tableZoom, setTableZoom] = useState(1);
  const [tableWidthRatio, setTableWidthRatio] = useState(0.5);
  const [isTableFullscreen, setIsTableFullscreen] = useState(false);

  useEffect(() => {
    setTableData(normaliseTable(document.ocr_table));
  }, [document]);

  const columnCount = useMemo(() => tableData.reduce((max, row) => Math.max(max, row.length), 0) || 1, [tableData]);

  const columns = useMemo<Column<GridRow>[]>(() => {
    return Array.from({ length: columnCount }, (_, columnIndex) => ({
      key: `col-${columnIndex}`,
      name: `列 ${columnIndex + 1}`,
      editor: textEditor,
      editable: true,
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

  const handleToggleFullscreen = () => {
    setIsTableFullscreen((current) => !current);
  };

  const handleZoomChange = (value: number) => {
    setTableZoom(Math.min(1.6, Math.max(0.8, value)));
  };

  const imageUrl = document.image_url.startsWith('http')
    ? document.image_url
    : `${API_BASE_URL}${document.image_url}`;

  const rowHeight = Math.max(28, Math.round(36 * tableZoom));
  const headerRowHeight = Math.max(32, Math.round(40 * tableZoom));

  const effectiveTableWidthRatio = isTableFullscreen ? 1 : Math.min(0.85, Math.max(0.3, tableWidthRatio));
  const imagePanelWidthRatio = isTableFullscreen ? 0 : 1 - effectiveTableWidthRatio;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">审查识别结果</h2>
          <p className="text-sm text-slate-500">{document.source_file}</p>
        </div>
        <button onClick={onClose} className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
          关闭
        </button>
      </header>

      <div className="flex flex-1 flex-col gap-4 overflow-hidden p-4 lg:flex-row lg:p-6">
        {isTableFullscreen ? null : (
          <div
            className="flex overflow-hidden rounded border border-slate-200 bg-slate-50 p-4 transition-[flex] duration-200"
            style={{ flex: imagePanelWidthRatio }}
          >
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
        )}
        <div
          className="flex flex-1 flex-col overflow-hidden rounded border border-slate-200 transition-[flex] duration-200"
          style={{ flex: effectiveTableWidthRatio }}
        >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <div className="flex items-center gap-2">
                  <span className="whitespace-nowrap">缩放</span>
                  <input
                    type="range"
                    min="0.8"
                    max="1.6"
                    step="0.1"
                    value={tableZoom}
                    onChange={(event) => handleZoomChange(Number(event.target.value))}
                    className="h-2 w-28 cursor-pointer"
                  />
                  <span className="min-w-[3ch] text-right">{Math.round(tableZoom * 100)}%</span>
                </div>
                {!isTableFullscreen && (
                  <div className="flex items-center gap-2">
                    <span className="whitespace-nowrap">表格宽度</span>
                    <input
                      type="range"
                      min="0.3"
                      max="0.85"
                      step="0.05"
                      value={effectiveTableWidthRatio}
                      onChange={(event) =>
                        setTableWidthRatio(Math.min(0.85, Math.max(0.3, Number(event.target.value))))
                      }
                      className="h-2 w-28 cursor-pointer"
                    />
                  </div>
                )}
                <button onClick={handleAddRow} className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300">
                  添加行
                </button>
                <button onClick={handleAddColumn} className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300">
                  添加列
                </button>
                <button
                  onClick={handleRemoveRow}
                  className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300 disabled:opacity-50"
                  disabled={tableData.length <= 1}
                >
                  删除末行
                </button>
                <button
                  onClick={handleRemoveColumn}
                  className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300 disabled:opacity-50"
                  disabled={columnCount <= 1}
                >
                  删除末列
                </button>
                <button onClick={handleReset} className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300">
                  重置
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleToggleFullscreen}
                  className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
                >
                  {isTableFullscreen ? '退出全屏' : '表格全屏'}
                </button>
                {error && <p className="text-xs text-red-500">{error}</p>}
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <div
                className="h-full overflow-hidden rounded-md border border-slate-200 bg-white"
                style={{ fontSize: `${(tableZoom * 0.875).toFixed(3)}rem` }}
              >
                <DataGrid
                  className="rdg-light h-full"
                  columns={columns}
                  rows={rows}
                  rowKeyGetter={(row) => row.id}
                  style={{ blockSize: '100%' }}
                  rowHeight={rowHeight}
                  headerRowHeight={headerRowHeight}
                  onCellClick={({ selectCell }) => selectCell(true)}
                  onRowsChange={handleRowsChange}
                />
              </div>
            </div>
        </div>
      </div>

      <footer className="flex flex-col gap-3 border-t border-slate-200 bg-white px-6 py-4 shadow-inner md:flex-row md:items-center md:justify-between">
        <p className="text-xs text-slate-500">
          对照原图调整表格后点击确认，系统将保存修改并标记为已审查。
        </p>
        <div className="space-x-3 text-right">
          <button onClick={onClose} className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600">
            取消
          </button>
          <button
            onClick={() => onConfirm(tableData)}
            disabled={saving}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? '保存中' : '确认审查结果'}
          </button>
        </div>
      </footer>
    </div>
  );
}
