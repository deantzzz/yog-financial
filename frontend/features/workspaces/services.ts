import { API_BASE_URL, apiFetch } from '../../lib/api';

export type WorkspaceJob = {
  job_id: string;
  filename: string | null;
  status: string;
  error?: string | null;
};

export type WorkspaceOverview = {
  ws_id: string;
  month: string;
  files: WorkspaceJob[];
  documents: WorkspaceDocument[];
};

export type WorkspaceDocument = {
  document_id: string;
  source_file: string;
  ocr_text: string;
  ocr_confidence: number | null;
  ocr_table: string[][];
  ocr_metadata: Record<string, unknown>;
  review_status: string;
  image_url: string;
  updated_at?: string;
};

export type WorkspaceSummary = {
  ws_id: string;
  month: string;
  jobs: number;
  facts: number;
  policy: number;
  results: number;
};

export type RequirementStatus = {
  id: string;
  label: string;
  description: string;
  optional: boolean;
  status: 'pending' | 'completed';
  filename?: string | null;
  job_id?: string | null;
  schema?: string | null;
  updated_at?: string | null;
  auto_inferred?: boolean;
};

export type StepStatus = 'pending' | 'in_progress' | 'blocked' | 'completed';

export type WorkflowStep = {
  id: string;
  label: string;
  description: string;
  status: StepStatus;
  requirements?: RequirementStatus[];
  meta?: Record<string, unknown>;
};

export type WorkspaceProgress = {
  ws_id: string;
  month: string;
  overall: number;
  steps: WorkflowStep[];
  next_step: string | null;
  summary: {
    jobs: { total: number; pending: number; failed: number; by_status: Record<string, number> };
    facts: { count: number; low_confidence: number };
    policy: { count: number };
    results: { count: number; periods: string[] };
  };
};

function parseDocuments(wsId: string, value: unknown): WorkspaceDocument[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => {
    const record = typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : {};
    const documentId = String(record.document_id ?? record.ingest_job_id ?? '');
    const rawConfidence = record.ocr_confidence;
    let confidence: number | null = null;
    if (typeof rawConfidence === 'number' && Number.isFinite(rawConfidence)) {
      confidence = rawConfidence;
    } else if (typeof rawConfidence === 'string') {
      const parsed = Number(rawConfidence);
      confidence = Number.isFinite(parsed) ? parsed : null;
    }

    const tableRaw = Array.isArray(record.ocr_table) ? (record.ocr_table as unknown[]) : [];
    const table: string[][] = tableRaw
      .map((row) => (Array.isArray(row) ? row.map((cell) => String(cell ?? '')) : []))
      .filter((row) => row.length > 0);

    const imageUrl = typeof record.image_url === 'string' ? record.image_url : `/api/workspaces/${wsId}/documents/${documentId}/image`;

    return {
      document_id: documentId,
      source_file: String(record.source_file ?? ''),
      ocr_text: String(record.ocr_text ?? ''),
      ocr_confidence: confidence,
      ocr_table: table.length > 0 ? table : [['']],
      ocr_metadata: (typeof record.ocr_metadata === 'object' && record.ocr_metadata !== null
        ? (record.ocr_metadata as Record<string, unknown>)
        : {}),
      review_status: typeof record.review_status === 'string' ? record.review_status : 'pending',
      image_url: imageUrl,
      updated_at: typeof record.updated_at === 'string' ? record.updated_at : undefined
    } satisfies WorkspaceDocument;
  });
}

export async function fetchWorkspaceOverview(wsId: string): Promise<WorkspaceOverview> {
  const data = await apiFetch<{
    ws_id?: string;
    month?: string;
    files?: WorkspaceJob[];
    documents?: unknown;
  }>(`/api/workspaces/${wsId}/files`);
  return {
    ws_id: data.ws_id ?? wsId,
    month: data.month ?? wsId,
    files: Array.isArray(data.files) ? data.files : [],
    documents: parseDocuments(wsId, data.documents)
  };
}

export async function listWorkspaces(): Promise<WorkspaceSummary[]> {
  const data = await apiFetch<{ items?: WorkspaceSummary[] }>(`/api/workspaces`);
  return Array.isArray(data.items)
    ? data.items.map((item) => ({
        ws_id: item.ws_id,
        month: item.month,
        jobs: Number(item.jobs ?? 0),
        facts: Number(item.facts ?? 0),
        policy: Number(item.policy ?? 0),
        results: Number(item.results ?? 0)
      }))
    : [];
}

export async function createWorkspace(month: string): Promise<{ ws_id: string }> {
  const data = await apiFetch<{ ws_id: string }>(`/api/workspaces`, {
    method: 'POST',
    body: JSON.stringify({ month })
  });
  return data;
}

export async function fetchWorkspaceProgress(wsId: string): Promise<WorkspaceProgress> {
  return await apiFetch<WorkspaceProgress>(`/api/workspaces/${wsId}/progress`);
}

export async function updateWorkspaceCheckpoint(
  wsId: string,
  step: string,
  status: 'pending' | 'completed'
): Promise<{ step: string; status: string; progress: WorkspaceProgress }> {
  return await apiFetch<{ step: string; status: string; progress: WorkspaceProgress }>(
    `/api/workspaces/${wsId}/progress/checkpoints`,
    {
      method: 'POST',
      body: JSON.stringify({ step, status })
    }
  );
}

export type UploadWorkspaceJob = { job_id: string; status: string; filename: string | null };

export async function uploadWorkspaceFiles(wsId: string, files: File[]): Promise<UploadWorkspaceJob[]> {
  if (files.length === 0) {
    throw new Error('请选择需要上传的文件');
  }

  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await fetch(`${API_BASE_URL}/api/workspaces/${wsId}/upload`, {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || '上传失败');
  }

  const data = (await response.json()) as { items?: Array<{ job_id?: string; status?: string; filename?: string | null }> };
  const items = Array.isArray(data.items) ? data.items : [];
  return items.map((item) => ({
    job_id: String(item.job_id ?? ''),
    status: String(item.status ?? ''),
    filename: item.filename ?? null
  }));
}

export type UpdateDocumentPayload = {
  ocrTable?: string[][];
  ocrText?: string;
  reviewStatus?: string;
};

export async function updateWorkspaceDocument(
  wsId: string,
  documentId: string,
  payload: UpdateDocumentPayload
): Promise<WorkspaceDocument> {
  const body: Record<string, unknown> = {};
  if (payload.ocrTable) {
    body.ocr_table = payload.ocrTable;
  }
  if (payload.ocrText !== undefined) {
    body.ocr_text = payload.ocrText;
  }
  if (payload.reviewStatus) {
    body.review_status = payload.reviewStatus;
  }

  const data = await apiFetch<Record<string, unknown>>(`/api/workspaces/${wsId}/documents/${documentId}`, {
    method: 'PUT',
    body: JSON.stringify(body)
  });
  const parsed = parseDocuments(wsId, [data]);
  if (!parsed.length) {
    throw new Error('文档返回格式异常');
  }
  return parsed[0];
}

type FactApiRecord = {
  employee_name?: string;
  employee_name_norm?: string;
  metric_code?: string;
  metric_value?: number | string | null;
  unit?: string;
  source_file?: string;
  confidence?: number | string | null;
};

type FactApiResponse = {
  items?: FactApiRecord[];
};

export type FactRecord = {
  employee_name: string;
  employee_name_norm: string;
  metric_code: string;
  metric_value: number | string;
  unit: string;
  source_file: string;
  confidence: number | null;
};

export async function fetchFactRecords(
  wsId: string,
  filters: { employeeName?: string; metricCode?: string } = {}
): Promise<FactRecord[]> {
  const params = new URLSearchParams();
  if (filters.employeeName) {
    params.set('employee_name', filters.employeeName);
  }
  if (filters.metricCode) {
    params.set('metric_code', filters.metricCode);
  }
  const query = params.toString();
  const path = query ? `/api/workspaces/${wsId}/fact?${query}` : `/api/workspaces/${wsId}/fact`;
  const data = await apiFetch<FactApiResponse>(path);

  return (data.items ?? []).map((item) => {
    const metricRaw = item.metric_value;
    let metricValue: number | string = metricRaw ?? 0;
    if (typeof metricRaw === 'number') {
      metricValue = metricRaw;
    } else if (typeof metricRaw === 'string') {
      const parsed = Number(metricRaw);
      metricValue = Number.isNaN(parsed) ? metricRaw : parsed;
    }

    let confidenceValue: number | null = null;
    if (typeof item.confidence === 'number') {
      confidenceValue = Number.isFinite(item.confidence) ? item.confidence : null;
    } else if (typeof item.confidence === 'string') {
      const parsed = Number(item.confidence);
      confidenceValue = Number.isNaN(parsed) ? null : parsed;
    }

    return {
      employee_name: item.employee_name ?? '',
      employee_name_norm: item.employee_name_norm ?? item.employee_name ?? '',
      metric_code: item.metric_code ?? '',
      metric_value: metricValue,
      unit: item.unit ?? '',
      source_file: item.source_file ?? '',
      confidence: confidenceValue
    };
  });
}

const NUMBER_PATTERN = /^[-+]?\d+(?:\.\d+)?$/;

function parseNumeric(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    const normalised = value.replace(/,/g, '').trim();
    if (!normalised || !NUMBER_PATTERN.test(normalised)) {
      return null;
    }
    const parsed = Number(normalised);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normaliseNested(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => normaliseNested(item));
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).reduce<Record<string, unknown>>((acc, [key, entry]) => {
      acc[key] = normaliseNested(entry);
      return acc;
    }, {});
  }
  const numeric = parseNumeric(value);
  return numeric ?? value;
}

function toRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }
  return normaliseNested(value) as Record<string, unknown>;
}

function toNullableString(value: unknown): string | null {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  return null;
}

export type PolicyRow = {
  employee_name_norm: string;
  period_month: string;
  mode: 'SALARIED' | 'HOURLY';
  base_amount: number | null;
  base_rate: number | null;
  ot_weekday_rate: number | null;
  ot_weekend_rate: number | null;
  ot_weekday_multiplier: number | null;
  ot_weekend_multiplier: number | null;
  allowances_json: Record<string, unknown>;
  deductions_json: Record<string, unknown>;
  social_security_json: Record<string, unknown>;
  tax_json: Record<string, unknown>;
  valid_from: string | null;
  valid_to: string | null;
  source_file: string | null;
  source_sheet: string | null;
  snapshot_hash: string | null;
  raw_snapshot: Record<string, unknown>;
};

function normalisePolicyRow(apiRow: Record<string, unknown>): PolicyRow | null {
  const employee = toNullableString(apiRow['employee_name_norm']) ?? '';
  const period = toNullableString(apiRow['period_month']) ?? '';
  if (!employee || !period) {
    return null;
  }

  const modeRaw = toNullableString(apiRow['mode'])?.toUpperCase() ?? 'SALARIED';
  const mode: 'SALARIED' | 'HOURLY' = modeRaw === 'HOURLY' ? 'HOURLY' : 'SALARIED';

  return {
    employee_name_norm: employee,
    period_month: period,
    mode,
    base_amount: parseNumeric(apiRow['base_amount']),
    base_rate: parseNumeric(apiRow['base_rate']),
    ot_weekday_rate: parseNumeric(apiRow['ot_weekday_rate']),
    ot_weekend_rate: parseNumeric(apiRow['ot_weekend_rate']),
    ot_weekday_multiplier: parseNumeric(apiRow['ot_weekday_multiplier']),
    ot_weekend_multiplier: parseNumeric(apiRow['ot_weekend_multiplier']),
    allowances_json: toRecord(apiRow['allowances_json']),
    deductions_json: toRecord(apiRow['deductions_json']),
    social_security_json: toRecord(apiRow['social_security_json']),
    tax_json: toRecord(apiRow['tax_json']),
    valid_from: toNullableString(apiRow['valid_from']),
    valid_to: toNullableString(apiRow['valid_to']),
    source_file: toNullableString(apiRow['source_file']),
    source_sheet: toNullableString(apiRow['source_sheet']),
    snapshot_hash: toNullableString(apiRow['snapshot_hash']),
    raw_snapshot: toRecord(apiRow['raw_snapshot'])
  };
}

export async function fetchPolicySnapshots(wsId: string): Promise<PolicyRow[]> {
  const data = await apiFetch<{ items?: Array<Record<string, unknown>> }>(`/api/workspaces/${wsId}/policy`);
  return (data.items ?? [])
    .map((item) => normalisePolicyRow(item))
    .filter((item): item is PolicyRow => item !== null);
}

export type PayrollResult = {
  employee_name_norm: string;
  period_month: string;
  gross_pay: number;
  net_pay: number;
  base_pay: number;
  ot_pay: number;
  allowances_sum?: number;
  deductions_sum?: number;
  social_security_personal?: number;
  tax?: number;
  snapshot_hash?: string | null;
  source_files?: string[];
};

const toNumber = (value: unknown): number => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

function parsePayrollResults(items: Array<Record<string, unknown>>): PayrollResult[] {
  return items.map((item) => ({
    employee_name_norm: String(item['employee_name_norm'] ?? ''),
    period_month: String(item['period_month'] ?? ''),
    gross_pay: toNumber(item['gross_pay']),
    net_pay: toNumber(item['net_pay']),
    base_pay: toNumber(item['base_pay']),
    ot_pay: toNumber(item['ot_pay']),
    allowances_sum: toNumber(item['allowances_sum']),
    deductions_sum: toNumber(item['deductions_sum']),
    social_security_personal: toNumber(item['social_security_personal']),
    tax: toNumber(item['tax']),
    snapshot_hash: (item['snapshot_hash'] as string | null | undefined) ?? null,
    source_files: Array.isArray(item['source_files'])
      ? item['source_files'].map((value) => String(value))
      : undefined
  }));
}

export async function triggerPayrollCalculation(
  wsId: string,
  payload: { period: string; selected?: string[] }
): Promise<{ period: string; items: PayrollResult[] }> {
  const data = await apiFetch<{ period?: string; items?: Array<Record<string, unknown>> }>(
    `/api/workspaces/${wsId}/calc`,
    {
      method: 'POST',
      body: JSON.stringify(payload)
    }
  );

  const period = typeof data.period === 'string' && data.period ? data.period : payload.period;
  const items = parsePayrollResults(Array.isArray(data.items) ? data.items : []);
  return { period, items };
}

export async function fetchPayrollResults(wsId: string, period: string): Promise<PayrollResult[]> {
  const data = await apiFetch<{ items?: Array<Record<string, unknown>> }>(
    `/api/workspaces/${wsId}/results?period=${encodeURIComponent(period)}`
  );

  return parsePayrollResults(Array.isArray(data.items) ? data.items : []);
}
