'use client';

import Link from 'next/link';
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { WorkflowStepper } from '../components/WorkflowStepper';
import {
  PayrollResult,
  RequirementStatus,
  WorkspaceProgress,
  WorkspaceSummary,
  WorkflowStep,
  createWorkspace,
  fetchPayrollResults,
  fetchWorkspaceProgress,
  listWorkspaces,
  triggerPayrollCalculation,
  updateWorkspaceCheckpoint,
  uploadWorkspaceFiles
} from '../features/workspaces/services';

const DEFAULT_STEPS = [
  {
    id: 'workspace_setup',
    label: '创建工作区',
    description: '选择计薪月份以初始化工作区。',
    status: 'pending' as const
  },
  {
    id: 'upload_timesheets',
    label: '上传工时与计薪基础',
    description: '上传工时明细或汇总表，生成事实数据。',
    status: 'pending' as const
  },
  {
    id: 'upload_policy',
    label: '上传口径与花名册',
    description: '导入薪酬口径与花名册，补齐口径快照。',
    status: 'blocked' as const
  },
  {
    id: 'review_data',
    label: '审查解析质量',
    description: '核对低置信度记录与口径差异。',
    status: 'blocked' as const
  },
  {
    id: 'run_payroll',
    label: '执行计薪并导出',
    description: '触发计算并下载结果文件。',
    status: 'blocked' as const
  }
];

const JOB_STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  processing: '解析中',
  pending: '待执行',
  queued: '排队中',
  failed: '失败',
  error: '失败'
};

const JOB_STATUS_COLORS: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  processing: 'bg-amber-100 text-amber-700',
  pending: 'bg-slate-100 text-slate-600',
  queued: 'bg-blue-100 text-blue-700',
  failed: 'bg-red-100 text-red-700',
  error: 'bg-red-100 text-red-700'
};

const TEMPLATE_GUIDE_BY_STEP: Record<
  string,
  Array<{ label: string; schema: string; description: string; optional?: boolean }>
> = {
  upload_timesheets: [
    {
      label: '员工工时明细',
      schema: 'timesheet_personal',
      description: '逐日或逐班次的打卡明细，系统会汇总为标准化工时事实记录。'
    },
    {
      label: '班组工时汇总（可选）',
      schema: 'timesheet_aggregate',
      description: '按部门/班组的月度汇总，用于交叉核对确认工时。',
      optional: true
    }
  ],
  upload_policy: [
    {
      label: '员工花名册',
      schema: 'roster_sheet',
      description: '提供社保个人/公司比例与基数范围，自动合并到口径快照中。'
    },
    {
      label: '薪酬口径与参数',
      schema: 'policy_sheet',
      description: '填写基本工资或时薪、加班费率、津贴扣款等字段，生成完整薪酬口径。'
    }
  ]
};

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 2
});

function currentMonth(): string {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
}

function RequirementList({ items }: { items?: RequirementStatus[] }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-slate-500">暂无要求，请先创建工作区。</p>;
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-700">{item.label}</span>
                {item.optional && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">可选</span>}
                {item.auto_inferred && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">自动识别</span>
                )}
              </div>
              <p className="text-xs text-slate-500">{item.description}</p>
              {item.status === 'completed' && (
                <p className="text-xs text-slate-400">
                  最新文件：{item.filename ?? '—'}
                  {item.updated_at ? ` · 更新时间：${new Date(item.updated_at).toLocaleString('zh-CN', { hour12: false })}` : ''}
                </p>
              )}
            </div>
            <span
              className={`rounded-full px-2 py-1 text-xs font-medium ${
                item.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
              }`}
            >
              {item.status === 'completed' ? '已完成' : '待上传'}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function Home() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [workspaceMessage, setWorkspaceMessage] = useState<string | null>(null);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [newWorkspaceMonth, setNewWorkspaceMonth] = useState(currentMonth());

  const [progress, setProgress] = useState<WorkspaceProgress | null>(null);
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [loadingProgress, setLoadingProgress] = useState(false);

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  const [calcPeriod, setCalcPeriod] = useState('');
  const [calcEmployees, setCalcEmployees] = useState('');
  const [calcMessage, setCalcMessage] = useState<string | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcResults, setCalcResults] = useState<PayrollResult[]>([]);

  const refreshWorkspaces = useCallback(async () => {
    const list = await listWorkspaces();
    setWorkspaces(list);
    if (!selectedWorkspace && list.length > 0) {
      setSelectedWorkspace(list[0].ws_id);
    }
  }, [selectedWorkspace]);

  useEffect(() => {
    refreshWorkspaces().catch((error) => {
      setWorkspaceMessage(error instanceof Error ? error.message : '加载工作区失败');
    });
  }, [refreshWorkspaces]);

  const loadProgress = async (workspaceId: string) => {
    if (!workspaceId) {
      setProgress(null);
      return;
    }
    setLoadingProgress(true);
    try {
      const data = await fetchWorkspaceProgress(workspaceId);
      setProgress(data);
      const lastStepId = data.steps.length > 0 ? data.steps[data.steps.length - 1]?.id ?? null : null;
      const preferred = data.next_step ?? data.steps.find((step) => step.status !== 'completed')?.id ?? lastStepId;
      setActiveStep((current) => {
        if (current && data.steps.some((step) => step.id === current)) {
          return current;
        }
        return preferred;
      });
      const latestPeriod =
        data.summary.results.periods.length > 0
          ? data.summary.results.periods[data.summary.results.periods.length - 1]
          : undefined;
      setCalcPeriod((prev) => (prev ? prev : latestPeriod ?? data.month));
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : '无法加载流程进度');
      setProgress(null);
    } finally {
      setLoadingProgress(false);
    }
  };

  useEffect(() => {
    if (selectedWorkspace) {
      loadProgress(selectedWorkspace);
    } else {
      setProgress(null);
      setActiveStep(null);
    }
  }, [selectedWorkspace]);

  useEffect(() => {
    setCalcResults([]);
    setCalcMessage(null);
  }, [selectedWorkspace]);

  const stepperData = progress
    ? progress.steps.map((step) => ({
        id: step.id,
        label: step.label,
        description: step.description,
        status: step.status
      }))
    : DEFAULT_STEPS;

  const currentStep: WorkflowStep | null = useMemo(() => {
    if (!progress) {
      return null;
    }
    return progress.steps.find((step) => step.id === activeStep) ?? progress.steps[0] ?? null;
  }, [progress, activeStep]);

  const overallPercent = Math.round((progress?.overall ?? 0) * 100);

  const handleCreateWorkspace = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newWorkspaceMonth) {
      setWorkspaceMessage('请输入工作区月份');
      return;
    }
    setCreatingWorkspace(true);
    setWorkspaceMessage(null);
    try {
      const response = await createWorkspace(newWorkspaceMonth);
      await refreshWorkspaces();
      setSelectedWorkspace(response.ws_id);
      setWorkspaceMessage('工作区创建成功');
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : '创建工作区失败');
    } finally {
      setCreatingWorkspace(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedWorkspace) {
      setUploadMessage('请先选择工作区');
      return;
    }
    if (selectedFiles.length === 0) {
      setUploadMessage('请选择需要上传的文件');
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      const jobs = await uploadWorkspaceFiles(selectedWorkspace, selectedFiles);
      const count = jobs.length || selectedFiles.length;
      setUploadMessage(count > 1 ? `上传成功，${count} 个文件已开始解析` : '上传成功，系统已开始解析');
      setSelectedFiles([]);
      setFileInputKey((key) => key + 1);
      await loadProgress(selectedWorkspace);
    } catch (error) {
      setUploadMessage(error instanceof Error ? `上传失败：${error.message}` : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleToggleReview = async () => {
    if (!progress || !selectedWorkspace) {
      return;
    }
    const reviewStep = progress.steps.find((step) => step.id === 'review_data');
    const checkpointStatus = (reviewStep?.meta?.checkpoint_status as string | undefined) === 'completed' ? 'pending' : 'completed';
    try {
      const data = await updateWorkspaceCheckpoint(selectedWorkspace, 'review_data', checkpointStatus);
      setProgress(data.progress);
      setActiveStep((current) => {
        if (checkpointStatus === 'completed') {
          return current === 'review_data' ? 'run_payroll' : current;
        }
        return 'review_data';
      });
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : '更新审查状态失败');
    }
  };

  const handleTriggerCalc = async () => {
    if (!selectedWorkspace || !calcPeriod) {
      setCalcMessage('请确认工作区与计薪月份');
      return;
    }
    setCalcLoading(true);
    setCalcMessage(null);
    try {
      const selectedEmployees = calcEmployees
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await triggerPayrollCalculation(selectedWorkspace, {
        period: calcPeriod,
        selected: selectedEmployees
      });
      const period = response.period ?? calcPeriod;
      if (period && period !== calcPeriod) {
        setCalcPeriod(period);
      }
      setCalcResults(response.items);
      setCalcMessage(
        response.items.length === 0
          ? '计算任务已执行，但未生成任何结果，请检查输入数据。'
          : `计算完成，生成 ${period ?? calcPeriod} 的 ${response.items.length} 条结果。`
      );
      await loadProgress(selectedWorkspace);
    } catch (error) {
      setCalcMessage(error instanceof Error ? error.message : '触发计算失败');
    } finally {
      setCalcLoading(false);
    }
  };

  const handleRefreshResults = async () => {
    if (!selectedWorkspace || !calcPeriod) {
      setCalcMessage('请确认工作区与计薪月份');
      return;
    }
    setCalcLoading(true);
    setCalcMessage(null);
    try {
      const rows = await fetchPayrollResults(selectedWorkspace, calcPeriod);
      setCalcResults(rows);
      setCalcMessage(
        rows.length === 0
          ? '暂无结果，请确认计算是否完成。'
          : `已载入 ${calcPeriod} 的 ${rows.length} 条结果。`
      );
      await loadProgress(selectedWorkspace);
    } catch (error) {
      setCalcMessage(error instanceof Error ? error.message : '刷新结果失败');
    } finally {
      setCalcLoading(false);
    }
  };

  const jobSummary = progress?.summary.jobs;
  const factsSummary = progress?.summary.facts;
  const policySummary = progress?.summary.policy;
  const resultSummary = progress?.summary.results;

  return (
    <section className="space-y-6">
      <header className="space-y-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-slate-900">流程驾驶舱</h1>
          <p className="text-sm text-slate-600">
            按照系统指引依次完成工作区创建、文件上传、数据审查与工资计算，实时掌握任务进度。
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-600">整体进度</span>
            <span className="font-medium text-primary">{overallPercent}%</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-primary" style={{ width: `${overallPercent}%` }} />
          </div>
        </div>
      </header>

      <WorkflowStepper
        steps={stepperData}
        activeStepId={currentStep?.id ?? null}
        onStepSelect={(stepId) => {
          if (!progress) {
            return;
          }
          const target = progress.steps.find((step) => step.id === stepId);
          if (!target || target.status === 'blocked') {
            return;
          }
          setActiveStep(stepId);
        }}
      />

      <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">四个模板即可完成工资计算</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5">
          <li>
            在「上传工时与计薪基础」中上传 <span className="font-medium">员工工时明细</span>{' '}
            (timesheet_personal)；如有汇总表，可追加 <span className="font-medium">班组工时汇总</span>{' '}
            (timesheet_aggregate)。
          </li>
          <li>
            在「上传口径与花名册」中上传 <span className="font-medium">员工花名册</span>{' '}
            (roster_sheet) 与 <span className="font-medium">薪酬口径与参数</span>{' '}
            (policy_sheet)，系统会自动合并花名册中的社保比例。
          </li>
          <li>完成以上上传后即可触发计算，无需再额外准备 facts/policy CSV。</li>
          <li>若结果为 0，请确认薪酬口径中已填写基本工资/时薪，并核对花名册的社保比例。</li>
        </ol>
        <p className="mt-3 text-xs text-slate-500">
          模板示例位于 <code>samples/templates/</code>，复制后即可直接调试。
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px,1fr]">
        <aside className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">工作区管理</h2>
              <button
                type="button"
                onClick={() => refreshWorkspaces().catch(() => undefined)}
                className="text-xs text-primary hover:text-primary/80"
              >
                刷新
              </button>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-slate-500">选择工作区</span>
                <select
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={selectedWorkspace}
                  onChange={(event) => {
                    setSelectedWorkspace(event.target.value);
                    setUploadMessage(null);
                  }}
                >
                  <option value="">请选择</option>
                  {workspaces.map((workspace) => (
                    <option key={workspace.ws_id} value={workspace.ws_id}>
                      {workspace.ws_id}
                    </option>
                  ))}
                </select>
              </label>
              <form className="space-y-2" onSubmit={handleCreateWorkspace}>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-slate-500">新建工作区（YYYY-MM）</span>
                  <input
                    type="month"
                    value={newWorkspaceMonth}
                    onChange={(event) => setNewWorkspaceMonth(event.target.value)}
                    className="rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <button
                  type="submit"
                  className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={creatingWorkspace}
                >
                  {creatingWorkspace ? '创建中…' : '创建工作区'}
                </button>
              </form>
              {workspaceMessage && <p className="text-xs text-slate-500">{workspaceMessage}</p>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-700">任务状态</h2>
            {jobSummary ? (
              <div className="mt-3 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">总任务</span>
                  <span className="font-medium text-slate-700">{jobSummary.total}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">处理中</span>
                  <span className="font-medium text-slate-700">{jobSummary.pending}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">失败</span>
                  <span className="font-medium text-rose-600">{jobSummary.failed}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(jobSummary.by_status).map(([status, count]) => (
                    <span key={status} className={`rounded-full px-2 py-1 text-xs ${JOB_STATUS_COLORS[status] ?? 'bg-slate-100 text-slate-500'}`}>
                      {JOB_STATUS_LABELS[status] ?? status}: {count}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">选择工作区后可查看任务状态。</p>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-700">数据概览</h2>
            {progress ? (
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="text-slate-500">事实记录</dt>
                  <dd className="font-medium text-slate-700">{factsSummary?.count ?? 0}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-slate-500">低置信度</dt>
                  <dd className="font-medium text-amber-600">{factsSummary?.low_confidence ?? 0}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-slate-500">口径快照</dt>
                  <dd className="font-medium text-slate-700">{policySummary?.count ?? 0}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-slate-500">计算结果</dt>
                  <dd className="font-medium text-slate-700">{resultSummary?.count ?? 0}</dd>
                </div>
              </dl>
            ) : (
              <p className="mt-3 text-sm text-slate-500">等待选择工作区。</p>
            )}
          </div>
        </aside>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          {!selectedWorkspace ? (
            <div className="space-y-3 text-sm text-slate-600">
              <h2 className="text-lg font-semibold text-slate-800">尚未选择工作区</h2>
              <p>请在左侧创建或选择一个计薪月份工作区，系统将根据该工作区引导上传与审查流程。</p>
            </div>
          ) : loadingProgress && !progress ? (
            <p className="text-sm text-slate-500">正在加载流程状态…</p>
          ) : currentStep && progress ? (
            <StepDetail
              step={currentStep}
              workspaceId={selectedWorkspace}
              onUploadFile={handleUpload}
              selectedFiles={selectedFiles}
              setSelectedFiles={setSelectedFiles}
              fileInputKey={fileInputKey}
              uploading={uploading}
              uploadMessage={uploadMessage}
              onToggleReview={handleToggleReview}
              calcPeriod={calcPeriod}
              setCalcPeriod={setCalcPeriod}
              calcEmployees={calcEmployees}
              setCalcEmployees={setCalcEmployees}
              onTriggerCalc={handleTriggerCalc}
              onRefreshResults={handleRefreshResults}
              calcLoading={calcLoading}
              calcMessage={calcMessage}
              calcResults={calcResults}
              progress={progress}
            />
          ) : (
            <p className="text-sm text-slate-500">未能获取流程信息，请稍后重试。</p>
          )}
        </div>
      </div>
    </section>
  );
}

function StepDetail({
  step,
  workspaceId,
  onUploadFile,
  selectedFiles,
  setSelectedFiles,
  fileInputKey,
  uploading,
  uploadMessage,
  onToggleReview,
  calcPeriod,
  setCalcPeriod,
  calcEmployees,
  setCalcEmployees,
  onTriggerCalc,
  onRefreshResults,
  calcLoading,
  calcMessage,
  calcResults,
  progress
}: {
  step: WorkflowStep;
  workspaceId: string;
  onUploadFile: () => void;
  selectedFiles: File[];
  setSelectedFiles: (files: File[]) => void;
  fileInputKey: number;
  uploading: boolean;
  uploadMessage: string | null;
  onToggleReview: () => void;
  calcPeriod: string;
  setCalcPeriod: (value: string) => void;
  calcEmployees: string;
  setCalcEmployees: (value: string) => void;
  onTriggerCalc: () => void;
  onRefreshResults: () => void;
  calcLoading: boolean;
  calcMessage: string | null;
  calcResults: PayrollResult[];
  progress: WorkspaceProgress;
}) {
  if (step.status === 'blocked') {
    return (
      <div className="space-y-3 text-sm text-slate-600">
        <h2 className="text-lg font-semibold text-slate-800">{step.label}</h2>
        <p>该步骤尚未解锁，请按照指引先完成前序步骤。</p>
      </div>
    );
  }

  if (step.id === 'workspace_setup') {
    return (
      <div className="space-y-4 text-sm text-slate-600">
        <h2 className="text-lg font-semibold text-slate-900">创建工作区</h2>
        <p>
          已选择工作区 <span className="font-medium text-primary">{workspaceId}</span>。若需新建其他月份，可在左侧操作栏输入新的 YYYY-MM
          并创建。
        </p>
        <ol className="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <li>1. 创建目标月份的工作区；</li>
          <li>2. 在下一步上传工时明细及花名册；</li>
          <li>3. 每完成一个步骤系统会自动更新右上角的进度。</li>
        </ol>
      </div>
    );
  }

  if (step.id === 'upload_timesheets') {
    const guideItems = TEMPLATE_GUIDE_BY_STEP[step.id] ?? [];
    return (
      <div className="space-y-5 text-sm text-slate-600">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">上传工时与计薪基础</h2>
          <p>优先上传 timesheet_personal 模板的个人工时明细，可选上传 timesheet_aggregate 汇总表以便核对。</p>
        </div>
        <RequirementList items={step.requirements} />
        {guideItems.length > 0 && (
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 text-xs text-slate-600">
            <h3 className="text-sm font-semibold text-blue-700">准备这些文件即可</h3>
            <ul className="mt-2 space-y-1">
              {guideItems.map((item) => (
                <li key={item.schema}>
                  <span className="font-medium text-slate-800">{item.label}</span>
                  <span className="text-slate-500"> · schema: {item.schema}</span>
                  <span className="text-slate-500"> · {item.description}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-slate-500">
              系统会把这些表格自动转写为事实（facts）记录，无需另行上传 `facts` CSV。
            </p>
          </div>
        )}
        <UploadBox
          fileInputKey={fileInputKey}
          selectedFiles={selectedFiles}
          setSelectedFiles={setSelectedFiles}
          uploading={uploading}
          uploadMessage={uploadMessage}
          onUploadFile={onUploadFile}
        />
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-sm font-semibold text-slate-700">提示</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-500">
            <li>支持 Excel、CSV、JSON 模板，系统会自动识别 schema 并登记到对应要求。</li>
            <li>上传完成后可前往「事实浏览」页面过滤查看解析出来的指标。</li>
          </ul>
          <Link href="/facts" className="mt-3 inline-flex items-center text-xs text-primary">
            打开事实数据页面 →
          </Link>
        </div>
      </div>
    );
  }

  if (step.id === 'upload_policy') {
    const guideItems = TEMPLATE_GUIDE_BY_STEP[step.id] ?? [];
    return (
      <div className="space-y-5 text-sm text-slate-600">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">上传口径与花名册</h2>
          <p>上传 roster_sheet 花名册与 policy_sheet 薪酬口径，补齐社保个税及津贴扣款参数。</p>
        </div>
        <RequirementList items={step.requirements} />
        {guideItems.length > 0 && (
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 text-xs text-slate-600">
            <h3 className="text-sm font-semibold text-blue-700">完成这两份模板即可</h3>
            <ul className="mt-2 space-y-1">
              {guideItems.map((item) => (
                <li key={item.schema}>
                  <span className="font-medium text-slate-800">{item.label}</span>
                  <span className="text-slate-500"> · schema: {item.schema}</span>
                  <span className="text-slate-500"> · {item.description}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-slate-500">
              roster_sheet 与 policy_sheet 会自动合并成同一条口径快照，确保薪酬基础与社保比例同时生效，无需再上传 `policy` CSV；若模板中的“月份”
              与工作区不同，系统会以当前工作区月份为准并在快照中保留原始值，避免出现结果为 0 的情况。
            </p>
          </div>
        )}
        <UploadBox
          fileInputKey={fileInputKey}
          selectedFiles={selectedFiles}
          setSelectedFiles={setSelectedFiles}
          uploading={uploading}
          uploadMessage={uploadMessage}
          onUploadFile={onUploadFile}
        />
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-sm font-semibold text-slate-700">完成后检查</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-500">
            <li>核对每位员工的模式、加班倍率、津贴扣款是否完整；</li>
            <li>如需人工调整，可在后端导出的 CSV 中修订后重新上传；</li>
            <li>跳转至「口径快照」页面查看最新口径。</li>
          </ul>
          <Link href="/policy" className="mt-3 inline-flex items-center text-xs text-primary">
            查看口径快照 →
          </Link>
        </div>
      </div>
    );
  }

  if (step.id === 'review_data') {
    const meta = step.meta ?? {};
    const checkpointStatus = meta.checkpoint_status === 'completed';
    const pendingJobs = Number(meta.pending_jobs ?? 0);
    const failedJobs = Number(meta.failed_jobs ?? 0);
    const lowConfidence = Number(meta.low_confidence ?? 0);
    const factsCount = Number(meta.facts_count ?? progress.summary.facts.count ?? 0);
    const policiesCount = Number(meta.policies_count ?? progress.summary.policy.count ?? 0);

    return (
      <div className="space-y-5 text-sm text-slate-600">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">审查解析质量</h2>
          <p>确认事实数据与口径参数准确无误后方可进入计薪。</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">事实层</h3>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{factsCount}</p>
            <p className="text-xs text-slate-500">低置信度记录 {lowConfidence} 条</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">口径</h3>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{policiesCount}</p>
            <p className="text-xs text-slate-500">待处理任务 {pendingJobs} · 失败 {failedJobs}</p>
          </div>
        </div>
        <div className="space-y-2 text-xs text-slate-500">
          <p>建议操作：</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>在事实浏览中筛选置信度 &lt; 0.8 的记录进行核实；</li>
            <li>在口径快照中核对社保个税参数是否完整；</li>
            <li>必要时重新上传修正后的模板。</li>
          </ul>
        </div>
        <button
          type="button"
          onClick={onToggleReview}
          className={`rounded-lg px-4 py-2 text-sm font-medium text-white shadow-sm ${
            checkpointStatus ? 'bg-slate-500 hover:bg-slate-600' : 'bg-primary hover:bg-blue-600'
          }`}
        >
          {checkpointStatus ? '取消审查完成标记' : '标记为已审查'}
        </button>
      </div>
    );
  }

  if (step.id === 'run_payroll') {
    const zeroNet = calcResults.length > 0 && calcResults.every((row) => Math.abs(row.net_pay) < 0.005);
    return (
      <div className="space-y-5 text-sm text-slate-600">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">执行计薪并导出</h2>
          <p>按月份触发计薪计算，稍后可刷新结果并导出至银行与税务系统。</p>
        </div>
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              计薪月份
              <input
                value={calcPeriod}
                onChange={(event) => setCalcPeriod(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700"
                placeholder="2025-01"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500 md:col-span-2">
              指定员工（可选，逗号分隔）
              <input
                value={calcEmployees}
                onChange={(event) => setCalcEmployees(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700"
                placeholder="张三, 李四"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onTriggerCalc}
              disabled={calcLoading}
              className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {calcLoading ? '处理中…' : '触发计算'}
            </button>
            <button
              type="button"
              onClick={onRefreshResults}
              disabled={calcLoading}
              className="inline-flex items-center justify-center rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary shadow-sm hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              刷新结果
            </button>
            <Link href="/calc" className="inline-flex items-center rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
              查看完整导出功能 →
            </Link>
          </div>
          {calcMessage && <p className="text-xs text-slate-500">{calcMessage}</p>}
          {zeroNet && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              <p>检测到本次所有员工的实发金额为 0，通常由以下原因造成：</p>
              <ul className="mt-2 list-disc space-y-1 pl-4">
                <li>薪酬口径模板未填写基本工资或时薪；</li>
                <li>花名册未上传或缺少社保个人比例，导致社保扣款无法计算；</li>
                <li>工时表缺少确认工时/总工时数据，请检查 timesheet 模板中的数值。</li>
              </ul>
            </div>
          )}
        </div>
        <div className="overflow-x-auto rounded-2xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-left">姓名</th>
                <th className="px-3 py-2 text-left">月份</th>
                <th className="px-3 py-2 text-right">应发</th>
                <th className="px-3 py-2 text-right">实发</th>
                <th className="px-3 py-2 text-right">基本</th>
                <th className="px-3 py-2 text-right">加班</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {calcResults.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-slate-500">
                    {calcLoading ? '加载中…' : '等待刷新或生成结果'}
                  </td>
                </tr>
              ) : (
                calcResults.map((row) => (
                  <tr key={`${row.employee_name_norm}-${row.period_month}`}>
                    <td className="px-3 py-2 text-slate-700">{row.employee_name_norm}</td>
                    <td className="px-3 py-2 text-slate-500">{row.period_month}</td>
                    <td className="px-3 py-2 text-right text-slate-700">{currencyFormatter.format(row.gross_pay)}</td>
                    <td className="px-3 py-2 text-right text-slate-700">{currencyFormatter.format(row.net_pay)}</td>
                    <td className="px-3 py-2 text-right text-slate-500">{currencyFormatter.format(row.base_pay)}</td>
                    <td className="px-3 py-2 text-right text-slate-500">{currencyFormatter.format(row.ot_pay)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-sm text-slate-600">
      <h2 className="text-lg font-semibold text-slate-900">{step.label}</h2>
      <p>{step.description}</p>
    </div>
  );
}

function UploadBox({
  fileInputKey,
  selectedFiles,
  setSelectedFiles,
  uploading,
  uploadMessage,
  onUploadFile
}: {
  fileInputKey: number;
  selectedFiles: File[];
  setSelectedFiles: (files: File[]) => void;
  uploading: boolean;
  uploadMessage: string | null;
  onUploadFile: () => void;
}) {
  return (
    <div className="space-y-3 rounded-2xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          key={fileInputKey}
          type="file"
          multiple
          className="max-w-xs text-sm text-slate-600"
          onChange={(event) => {
            const fileList = event.target.files;
            setSelectedFiles(fileList ? Array.from(fileList) : []);
          }}
        />
        <button
          type="button"
          onClick={onUploadFile}
          disabled={uploading}
          className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? '上传中…' : '上传文件'}
        </button>
        {selectedFiles.length > 0 && (
          <span className="text-xs text-slate-500">
            {selectedFiles.map((file) => file.name).join('，')}
          </span>
        )}
      </div>
      <p className="text-xs text-slate-500">上传成功后会自动刷新流程状态。</p>
      {uploadMessage && <p className="text-xs text-slate-500">{uploadMessage}</p>}
    </div>
  );
}
