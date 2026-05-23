import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { useLocale } from '../../contexts/LocaleContext';

type GateResult = {
  fit: boolean;
  score: number;
  reasons: string[];
  missingInfo: string[];
  fallbackAdvice: string[];
};

type ScenarioFiles = {
  initialProgram: string;
  evaluator: string;
  configYaml: string;
};

type ValidationReport = {
  ok: boolean;
  errors: Array<{ code: string; message: string; path?: string; line?: number }>;
  warnings: Array<{ code: string; message: string; path?: string; line?: number }>;
  suggestions: string[];
};

type SessionEnvelope = {
  eventType: string;
  sessionId: string;
  timestamp: number;
  seq: number;
  payload: any;
};

type LogEntry = {
  level: 'info' | 'warn' | 'error';
  source: string;
  message: string;
  kind: 'phase' | 'log' | 'raw';
  timestamp: number;
};

type StepState = 'pending' | 'running' | 'done' | 'failed';
type WizardStep = 0 | 1 | 2;
type ScenarioStatusType = 'IDLE' | 'CHECKING' | 'FAILED' | 'PASSED' | 'GENERATED';

const EMPTY_FILES: ScenarioFiles = {
  initialProgram: '',
  evaluator: '',
  configYaml: '',
};

const EMPTY_REPORT: ValidationReport = {
  ok: false,
  errors: [],
  warnings: [],
  suggestions: [],
};

function lineDeltaCount(before: string, after: string): number {
  const a = (before || '').split('\n');
  const b = (after || '').split('\n');
  const maxLen = Math.max(a.length, b.length);
  let changes = 0;
  for (let i = 0; i < maxLen; i += 1) {
    if ((a[i] || '') !== (b[i] || '')) changes += 1;
  }
  return changes;
}

function buildSimpleDiff(before: string, after: string): string {
  const a = (before || '').split('\n');
  const b = (after || '').split('\n');
  const maxLen = Math.max(a.length, b.length);
  const out: string[] = [];
  for (let i = 0; i < maxLen; i += 1) {
    const oldLine = a[i] ?? '';
    const newLine = b[i] ?? '';
    if (oldLine === newLine) continue;
    if (oldLine) out.push(`- ${oldLine}`);
    if (newLine) out.push(`+ ${newLine}`);
    if (out.length > 220) {
      out.push('...diff truncated...');
      break;
    }
  }
  return out.length ? out.join('\n') : '暂无变更';
}

export function ScenarioBuilderTab({
  onProjectCreated,
  persistedSessionId,
  onSessionIdChange,
}: {
  onProjectCreated: () => void;
  persistedSessionId?: string;
  onSessionIdChange?: (sid: string) => void;
}) {
  const { t } = useLocale();
  const [problemDescription, setProblemDescription] = useState('');
  const [objectiveType, setObjectiveType] = useState<'minimize' | 'maximize'>('minimize');
  const [constraints, setConstraints] = useState('');
  const [ioContract, setIoContract] = useState('run_search');
  const [hasAutoEvaluation, setHasAutoEvaluation] = useState(true);
  const [primaryMetric, setPrimaryMetric] = useState('combined_score');
  const [baselineCode, setBaselineCode] = useState('');
  const [projectName, setProjectName] = useState('');
  const [userFeedback, setUserFeedback] = useState('');
  const [gateResult, setGateResult] = useState<GateResult | null>(null);
  const [sessionId, setSessionId] = useState(String(persistedSessionId || ''));
  const [sessionStatus, setSessionStatus] = useState('idle');
  const [currentPhase, setCurrentPhase] = useState('idle');
  const [usedSkill, setUsedSkill] = useState('opencode-scenario-builder');
  const [generationSource, setGenerationSource] = useState<'unknown' | 'opencode' | 'fallback'>('unknown');
  const [generationError, setGenerationError] = useState('');
  const [rawPreview, setRawPreview] = useState('');
  const [changeSummary, setChangeSummary] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logFilter, setLogFilter] = useState<'all' | 'warn' | 'error'>('all');
  const [logAutoFollow, setLogAutoFollow] = useState(true);
  const [baselineOpen, setBaselineOpen] = useState(false);
  const [activePreviewTab, setActivePreviewTab] = useState<'initial' | 'evaluator' | 'config'>('initial');
  const [showDiff, setShowDiff] = useState(false);
  const [files, setFiles] = useState<ScenarioFiles>(EMPTY_FILES);
  const prevFilesRef = useRef<ScenarioFiles>(EMPTY_FILES);
  const [diffBaseFiles, setDiffBaseFiles] = useState<ScenarioFiles>(EMPTY_FILES);
  const [delta, setDelta] = useState({ initial: 0, evaluator: 0, config: 0, total: 0 });
  const [report, setReport] = useState<ValidationReport>(EMPTY_REPORT);
  const [busy, setBusy] = useState(false);
  const [gateChecking, setGateChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [riskConfirm, setRiskConfirm] = useState({
    secret: false,
    metric: false,
    contract: false,
  });
  const esRef = useRef<EventSource | null>(null);
  const logPanelRef = useRef<HTMLDivElement | null>(null);
  const connectedSessionIdRef = useRef('');

  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      connectedSessionIdRef.current = '';
    };
  }, []);

  useEffect(() => {
    const sid = String(persistedSessionId || '');
    if (!sid) return;
    if (sid === sessionId) return;
    setSessionId(sid);
  }, [persistedSessionId, sessionId]);

  const intakePayload = useMemo(
    () => ({
      problemDescription,
      objectiveType,
      constraints,
      ioContract,
      hasAutoEvaluation,
      primaryMetric,
      baselineCode,
    }),
    [problemDescription, objectiveType, constraints, ioContract, hasAutoEvaluation, primaryMetric, baselineCode]
  );

  const runGate = async () => {
    setBusy(true);
    setGateChecking(true);
    setCurrentPhase('validate');
    setError('');
    setMessage('正在执行 Gate 判定...');
    setLogs((prev) => [
      ...prev.slice(-299),
      { level: 'info', source: 'gate', message: '开始 Gate 判定...', kind: 'log', timestamp: Date.now() },
    ]);
    try {
      const res = await fetch('/api/scenarios/gate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intakePayload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || `gate failed: ${res.status}`);
      setGateResult(data as GateResult);
      setMessage((data as GateResult).fit ? 'Gate 判定通过' : 'Gate 判定未通过，请查看失败原因');
      setLogs((prev) => [
        ...prev.slice(-299),
        {
          level: (data as GateResult).fit ? 'info' : 'warn',
          source: 'gate',
          message: (data as GateResult).fit ? 'Gate 判定通过' : `Gate 未通过：${((data as GateResult).missingInfo || []).join(', ') || '信息不足'}`,
          kind: 'log',
          timestamp: Date.now(),
        },
      ]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'gate failed';
      setError(msg);
      setLogs((prev) => [
        ...prev.slice(-299),
        { level: 'error', source: 'gate', message: `Gate 判定失败：${msg}`, kind: 'log', timestamp: Date.now() },
      ]);
    } finally {
      setBusy(false);
      setGateChecking(false);
    }
  };

  const attachSessionEvents = (sid: string) => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    connectedSessionIdRef.current = sid;
    const es = new EventSource(`/api/scenarios/opencode/session/${encodeURIComponent(sid)}/events`);
    esRef.current = es;
    es.onmessage = (evt) => {
      try {
        const data: SessionEnvelope = JSON.parse(evt.data);
        if (data.eventType === 'phase_changed') {
          setSessionStatus(String(data.payload?.phase || 'running'));
          setCurrentPhase(String(data.payload?.phase || 'running'));
          setLogs((prev) => [
            ...prev.slice(-299),
            {
              level: 'info',
              source: 'phase',
              message: String(data.payload?.message || data.payload?.phase || 'phase changed'),
              kind: 'phase',
              timestamp: Number(data.timestamp || Date.now()),
            },
          ]);
        } else if (data.eventType === 'log') {
          const lvl = String(data.payload?.level || 'info').toLowerCase();
          const level: 'info' | 'warn' | 'error' = lvl === 'warn' ? 'warn' : lvl === 'error' ? 'error' : 'info';
          setLogs((prev) => [
            ...prev.slice(-299),
            {
              level,
              source: String(data.payload?.source || 'opencode-skill'),
              message: String(data.payload?.message || '').trim(),
              kind: 'log',
              timestamp: Number(data.timestamp || Date.now()),
            },
          ]);
        } else if (data.eventType === 'draft_files') {
          const next = data.payload?.files || {};
          const nextFiles = {
            initialProgram: String(next.initialProgram || ''),
            evaluator: String(next.evaluator || ''),
            configYaml: String(next.configYaml || ''),
          };
          const prevFiles = prevFilesRef.current;
          const nextDelta = {
            initial: lineDeltaCount(prevFiles.initialProgram, nextFiles.initialProgram),
            evaluator: lineDeltaCount(prevFiles.evaluator, nextFiles.evaluator),
            config: lineDeltaCount(prevFiles.configYaml, nextFiles.configYaml),
            total: 0,
          };
          nextDelta.total = nextDelta.initial + nextDelta.evaluator + nextDelta.config;
          setDelta(nextDelta);
          setDiffBaseFiles(prevFiles);
          prevFilesRef.current = nextFiles;
          setFiles(nextFiles);
          const src = String(data.payload?.generationSource || '').toLowerCase();
          setGenerationSource(src === 'opencode' ? 'opencode' : src === 'fallback' ? 'fallback' : 'unknown');
          setGenerationError(String(data.payload?.generationError || ''));
        } else if (data.eventType === 'validation_report') {
          setReport({
            ok: Boolean(data.payload?.ok),
            errors: Array.isArray(data.payload?.errors) ? data.payload.errors : [],
            warnings: Array.isArray(data.payload?.warnings) ? data.payload.warnings : [],
            suggestions: Array.isArray(data.payload?.suggestions) ? data.payload.suggestions : [],
          });
        } else if (data.eventType === 'session_completed') {
          setSessionStatus('await_user_confirm');
          setCurrentPhase('await_user_confirm');
          setChangeSummary(String(data.payload?.changeSummary || ''));
          setUsedSkill(String(data.payload?.usedSkill || usedSkill));
          const src = String(data.payload?.generationSource || '').toLowerCase();
          setGenerationSource(src === 'opencode' ? 'opencode' : src === 'fallback' ? 'fallback' : 'unknown');
          setGenerationError(String(data.payload?.generationError || ''));
          setMessage(t('right.scenario.sessionCompleted'));
          void loadSessionResult(sid);
          es.close();
          esRef.current = null;
          connectedSessionIdRef.current = '';
        } else if (data.eventType === 'session_failed') {
          setSessionStatus('failed');
          setError(String(data.payload?.errorMessage || t('right.scenario.sessionFailed')));
          es.close();
          esRef.current = null;
          connectedSessionIdRef.current = '';
        }
      } catch {
        setLogs((prev) => [
          ...prev.slice(-299),
          { level: 'info', source: 'system', message: String(evt.data || ''), kind: 'raw', timestamp: Date.now() },
        ]);
      }
    };
    es.onerror = () => {
      es.close();
      if (esRef.current === es) esRef.current = null;
      connectedSessionIdRef.current = '';
    };
  };

  const loadSessionResult = async (sid: string) => {
    try {
      const res = await fetch(`/api/scenarios/opencode/session/${encodeURIComponent(sid)}/result`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) return;
      const result = data?.result || {};
      if (result?.draftFiles) {
        const nextFiles = {
          initialProgram: String(result.draftFiles.initialProgram || ''),
          evaluator: String(result.draftFiles.evaluator || ''),
          configYaml: String(result.draftFiles.configYaml || ''),
        };
        const prevFiles = prevFilesRef.current;
        const nextDelta = {
          initial: lineDeltaCount(prevFiles.initialProgram, nextFiles.initialProgram),
          evaluator: lineDeltaCount(prevFiles.evaluator, nextFiles.evaluator),
          config: lineDeltaCount(prevFiles.configYaml, nextFiles.configYaml),
          total: 0,
        };
        nextDelta.total = nextDelta.initial + nextDelta.evaluator + nextDelta.config;
        setDelta(nextDelta);
        setDiffBaseFiles(prevFiles);
        prevFilesRef.current = nextFiles;
        setFiles(nextFiles);
      }
      if (result?.validationReport) {
        setReport({
          ok: Boolean(result.validationReport.ok),
          errors: Array.isArray(result.validationReport.errors) ? result.validationReport.errors : [],
          warnings: Array.isArray(result.validationReport.warnings) ? result.validationReport.warnings : [],
          suggestions: Array.isArray(result.validationReport.suggestions) ? result.validationReport.suggestions : [],
        });
      }
      setChangeSummary(String(result?.changeSummary || ''));
      setUsedSkill(String(result?.usedSkill || usedSkill));
      const src = String(result?.generationSource || '').toLowerCase();
      setGenerationSource(src === 'opencode' ? 'opencode' : src === 'fallback' ? 'fallback' : 'unknown');
      setGenerationError(String(result?.generationError || ''));
      setRawPreview(String(result?.rawPreview || ''));
    } catch {
      // ignore
    }
  };

  const startSession = async (interactive = false) => {
    setBusy(true);
    setError('');
    setMessage('');
    setCurrentPhase('draft');
    if (!interactive) {
      setLogs([]);
      setFiles(EMPTY_FILES);
      setDiffBaseFiles(EMPTY_FILES);
      setGenerationSource('unknown');
      setGenerationError('');
      setRawPreview('');
      prevFilesRef.current = EMPTY_FILES;
      setDelta({ initial: 0, evaluator: 0, config: 0, total: 0 });
      setReport(EMPTY_REPORT);
    }
    try {
      const res = await fetch('/api/scenarios/opencode/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intake: intakePayload,
          maxAttempts: 3,
          mode: 'draft_and_fix',
          skillName: 'opencode-scenario-builder',
          seedFiles: interactive ? files : undefined,
          userFeedback: userFeedback.trim() || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || `start session failed: ${res.status}`);
      const sid = String(data.sessionId || '');
      if (!sid) throw new Error('missing sessionId');
      setSessionId(sid);
      onSessionIdChange?.(sid);
      setUsedSkill(String(data.usedSkill || 'opencode-scenario-builder'));
      setSessionStatus('running');
      if (interactive) {
        setMessage(t('right.scenario.interactiveStarted'));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'start session failed');
    } finally {
      setBusy(false);
    }
  };

  const createProject = async () => {
    if (!projectName.trim()) {
      setError(t('right.scenario.projectNameRequired'));
      return;
    }
    setCreating(true);
    setError('');
    setMessage('');
    try {
      const res = await fetch('/api/scenarios/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectName: projectName.trim(),
          files,
          allowOverwrite: false,
          sessionId: sessionId || undefined,
          usedSkill,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || `create failed: ${res.status}`);
      setMessage(t('right.scenario.createSuccess', { name: projectName.trim() }));
      onProjectCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'create failed');
    } finally {
      setCreating(false);
    }
  };

  const allRisksConfirmed = riskConfirm.secret && riskConfirm.metric && riskConfirm.contract;
  const filteredLogs = logs.filter((x) => (logFilter === 'all' ? true : x.level === logFilter));
  const isStreamingNow = sessionStatus === 'running' && ['draft', 'fix', 'validate'].includes(currentPhase);
  const hasGeneratedFiles = Boolean(files.initialProgram.trim() || files.evaluator.trim() || files.configYaml.trim());
  const hasValidGeneratedFiles = Boolean(files.initialProgram.trim() && files.evaluator.trim() && files.configYaml.trim());
  const gateFailed = Boolean(gateResult && !gateResult.fit);
  const validationFailed = Boolean(sessionStatus === 'failed' || (sessionStatus !== 'idle' && !report.ok && !isStreamingNow && hasGeneratedFiles));
  const showFailureResultCard = (gateFailed || validationFailed) && !hasGeneratedFiles;

  const scenarioStatus: ScenarioStatusType = useMemo(() => {
    if (isStreamingNow || busy || gateChecking) return 'CHECKING';
    if (hasValidGeneratedFiles) return 'GENERATED';
    // Gate 通过后即进入可生成阶段，不依赖 validation_report（该报告来自生成后流程）
    if (gateResult?.fit) return 'PASSED';
    if (gateFailed || validationFailed || Boolean(error)) return 'FAILED';
    return 'IDLE';
  }, [isStreamingNow, busy, gateChecking, hasValidGeneratedFiles, gateResult, gateFailed, validationFailed, error]);

  const stepDefs = [
    { id: 0 as WizardStep, label: '场景配置' },
    { id: 1 as WizardStep, label: '生成校验' },
    { id: 2 as WizardStep, label: '预览创建' },
  ];

  const previewTitle =
    activePreviewTab === 'initial' ? 'initial_program.py' : activePreviewTab === 'evaluator' ? 'evaluator.py' : 'config.yaml';
  const previewText =
    activePreviewTab === 'initial'
      ? files.initialProgram
      : activePreviewTab === 'evaluator'
        ? files.evaluator
        : files.configYaml;
  const previewBaseText =
    activePreviewTab === 'initial'
      ? diffBaseFiles.initialProgram
      : activePreviewTab === 'evaluator'
        ? diffBaseFiles.evaluator
        : diffBaseFiles.configYaml;
  const previewDiffText = buildSimpleDiff(previewBaseText, previewText);
  const showRiskConfirm = scenarioStatus === 'GENERATED' && gateResult?.fit && hasValidGeneratedFiles;
  const contractTrim = ioContract.trim();
  const contractIsCallExpression = /[()]/.test(contractTrim);
  const contractLabel = contractIsCallExpression ? '运行调用' : '运行入口函数名';
  const idleMissingItems = [
    !problemDescription.trim() ? '问题描述为空' : '',
    !constraints.trim() ? '约束条件未确认' : '',
    !primaryMetric.trim() ? '主指标未确认' : '',
    !ioContract.trim() ? '运行入口函数名为空' : '',
  ].filter(Boolean);
  const canRunGate = idleMissingItems.length === 0;
  const configCompleted = canRunGate;
  const wizardStep: WizardStep = useMemo(() => {
    if (scenarioStatus === 'GENERATED') return 2;
    if (
      scenarioStatus === 'CHECKING' ||
      scenarioStatus === 'FAILED' ||
      scenarioStatus === 'PASSED' ||
      (configCompleted && scenarioStatus !== 'GENERATED')
    ) {
      return 1;
    }
    return 0;
  }, [scenarioStatus, configCompleted]);
  const phaseText =
    scenarioStatus === 'IDLE'
      ? '等待填写'
      : scenarioStatus === 'CHECKING'
        ? currentPhase === 'draft'
          ? '正在 Gate 判定/草案生成'
          : currentPhase === 'fix'
            ? '正在修复迭代'
            : '正在结构校验'
        : scenarioStatus === 'FAILED'
          ? '校验失败'
          : scenarioStatus === 'PASSED'
            ? '已通过'
            : '文件已生成，可预览创建';

  const applyConstraintTag = (tag: string) => {
    setConstraints((prev) => {
      const p = (prev || '').trim();
      if (!p) return tag;
      if (p.includes(tag)) return p;
      return `${p}；${tag}`;
    });
  };

  const autoFixAndRetry = async () => {
    if (!problemDescription.trim()) {
      setProblemDescription('问题背景：\n目标：\n输入：\n输出：\n评价标准：\n已知约束：');
    }
    if (!ioContract.trim()) setIoContract('run_search');
    if (!primaryMetric.trim()) setPrimaryMetric('combined_score');
    if (!constraints.trim()) setConstraints('时间限制：30s；内存限制：2GB；网络：禁止联网');
    if (!hasAutoEvaluation) setHasAutoEvaluation(true);
    await runGate();
  };

  const handleDownloadPreview = () => {
    const blob = new Blob([previewText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = previewTitle;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyPreview = async () => {
    try {
      await navigator.clipboard.writeText(previewText);
      setMessage(`${previewTitle} 已复制到剪贴板`);
    } catch {
      setError('复制失败，请手动复制');
    }
  };

  useEffect(() => {
    const sid = String(sessionId || '').trim();
    if (!sid) return;
    if (connectedSessionIdRef.current === sid && esRef.current) return;
    void loadSessionResult(sid);
    attachSessionEvents(sid);
  }, [sessionId]);

  useEffect(() => {
    if (!logAutoFollow) return;
    const el = logPanelRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [filteredLogs, logAutoFollow]);

  const renderStatusCard = () => {
    if (scenarioStatus === 'IDLE') {
      return (
        <div className="rounded-lg border border-white/10 bg-[#0b1220]/80 px-3 py-2 text-sm text-slate-300">
          <div className="font-semibold">等待填写</div>
          <div className="mt-1 text-xs text-slate-400">请先补全场景配置，再执行 Gate 判定。</div>
        </div>
      );
    }
    if (scenarioStatus === 'CHECKING') {
      return (
        <div className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100">
          <div className="font-semibold">正在判定 / 生成中</div>
          <div className="mt-1 text-xs">OpenCode 正在处理，请查看实时日志。</div>
        </div>
      );
    }
    if (scenarioStatus === 'FAILED') {
      return (
        <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
          <div className="font-semibold">校验未通过</div>
          <div className="mt-1 text-xs">原因：{report.errors[0]?.message || gateResult?.reasons?.[0] || generationError || '缺少可执行信息'}</div>
          <div className="mt-1 text-xs">影响：无法稳定生成 evaluator.py 或计算 combined_score。</div>
          <div className="mt-1 text-xs">下一步：补充契约信息后重新 Gate，或使用“自动修复并重新生成”。</div>
        </div>
      );
    }
    if (scenarioStatus === 'GENERATED') {
      return (
        <div className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
          <div className="font-semibold">文件已生成，可预览创建</div>
          <div className="mt-1 text-xs">三件套已就绪，请检查差异后创建项目。</div>
        </div>
      );
    }
    return (
      <div className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
        <div className="font-semibold">校验通过</div>
      </div>
    );
  };

  const primaryAction = (() => {
    if (scenarioStatus === 'IDLE') {
      return {
        label: '运行 Gate 判定',
        onClick: () => void runGate(),
        disabled: busy || gateChecking || !canRunGate,
      };
    }
    if (scenarioStatus === 'CHECKING') {
      return {
        label: '处理中...',
        onClick: () => undefined,
        disabled: true,
      };
    }
    if (scenarioStatus === 'FAILED') {
      return {
        label: '自动修复并重新生成',
        onClick: () => void autoFixAndRetry(),
        disabled: busy,
      };
    }
    if (scenarioStatus === 'PASSED') {
      return {
        label: '生成场景文件',
        onClick: () => void startSession(false),
        disabled: busy,
      };
    }
    return {
      label: '确认创建项目',
      onClick: () => void createProject(),
      disabled: creating || !showRiskConfirm || !allRisksConfirmed || !projectName.trim(),
    };
  })();

  return (
    <div className="flex-1 m-0 overflow-y-auto bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_40%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.06),transparent_45%)] p-4">
      <div className="mx-auto max-w-[1400px] space-y-4">
        <div className="rounded-xl border border-white/10 bg-[#0b1220]/90 p-4">
          <div className="mb-2 text-xs uppercase tracking-[0.14em] text-slate-400">流程步骤</div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            {stepDefs.map((step, idx) => (
              (() => {
                const isFailed = scenarioStatus === 'FAILED' && step.id === 1;
                const isActive = !isFailed && step.id === wizardStep;
                const isCompleted =
                  !isFailed &&
                  ((step.id === 0 && configCompleted) || (step.id === 1 && scenarioStatus === 'GENERATED'));
                const cls = isFailed
                  ? 'border-orange-400/45 bg-orange-500/15 text-orange-100'
                  : isActive
                    ? 'border-cyan-400/50 bg-cyan-500/20 text-cyan-100'
                    : isCompleted
                      ? 'border-emerald-400/35 bg-emerald-500/12 text-emerald-100'
                      : 'border-white/10 bg-[#111827]/90 text-slate-400';
                return (
              <div
                key={step.id}
                className={`rounded-lg border px-3 py-2 text-xs ${cls}`}
              >
                <div className="font-semibold">{idx + 1}. {step.label}</div>
              </div>
                );
              })()
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 min-[1200px]:grid-cols-[minmax(520px,1.1fr)_minmax(420px,0.9fr)]">
          <div className="space-y-4">
            <div className="rounded-xl border border-white/10 bg-[#111827]/88 p-4 space-y-3">
              <div className="text-xs uppercase tracking-[0.14em] text-slate-400">1. 问题设定</div>
              <Label className="text-xs text-slate-300">问题描述</Label>
              <textarea
                value={problemDescription}
                onChange={(e) => setProblemDescription(e.target.value)}
                className="w-full min-h-[180px] rounded-lg border border-white/10 bg-[#0f172a]/90 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-cyan-400/40"
                placeholder={'问题背景：\n目标：\n输入：\n输出：\n评价标准：\n已知约束：'}
              />
              <Label className="text-xs text-slate-300">约束条件</Label>
              <div className="flex flex-wrap gap-2">
                {['时间限制：30s', '内存限制：2GB', '网络：禁止联网', '依赖：仅允许 numpy / scipy', '随机性：固定 seed'].map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    className="rounded-md border border-white/15 bg-[#0b1220]/80 px-2 py-1 text-[11px] text-slate-300 hover:border-cyan-400/40"
                    onClick={() => applyConstraintTag(tag)}
                  >
                    {tag}
                  </button>
                ))}
              </div>
              <textarea
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                className="w-full min-h-[94px] rounded-lg border border-white/10 bg-[#0f172a]/90 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-cyan-400/40"
                placeholder="可继续补充业务约束..."
              />
            </div>

            <div className="rounded-xl border border-white/10 bg-[#111827]/88 p-4 space-y-3">
              <div className="text-xs uppercase tracking-[0.14em] text-slate-400">2. 评测契约</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-slate-300">目标类型</Label>
                  <div className="mt-1 flex gap-2">
                    <Button variant={objectiveType === 'minimize' ? 'default' : 'outline'} onClick={() => setObjectiveType('minimize')}>
                      最小化
                    </Button>
                    <Button variant={objectiveType === 'maximize' ? 'default' : 'outline'} onClick={() => setObjectiveType('maximize')}>
                      最大化
                    </Button>
                  </div>
                </div>
                <div>
                  <Label className="text-xs text-slate-300">主指标</Label>
                  <Input className="mt-1 rounded-lg border-white/10 bg-[#0f172a]/90" value={primaryMetric} onChange={(e) => setPrimaryMetric(e.target.value)} />
                </div>
              </div>
              <div>
                <Label className="text-xs text-slate-300">{contractLabel}</Label>
                <Input className="mt-1 rounded-lg border-white/10 bg-[#0f172a]/90" value={ioContract} onChange={(e) => setIoContract(e.target.value)} placeholder={contractIsCallExpression ? 'run_search()' : 'run_search'} />
                <div className="mt-1 text-[11px] text-slate-500">Evaluator 调用说明：evaluator 会调用该入口并读取返回结果。</div>
              </div>
              <label className="inline-flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={hasAutoEvaluation} onChange={(e) => setHasAutoEvaluation(e.target.checked)} />
                <span>允许系统自动生成 evaluator.py</span>
              </label>
              <div className="text-xs text-slate-300">
                Baseline（可选）{' '}
                <button type="button" className="text-cyan-300 hover:underline" onClick={() => setBaselineOpen((v) => !v)}>
                  [{baselineOpen ? '收起' : '展开'}]
                </button>
              </div>
              {baselineOpen && (
                <textarea
                  value={baselineCode}
                  onChange={(e) => setBaselineCode(e.target.value)}
                  className="w-full min-h-[120px] rounded-lg border border-white/10 bg-[#0f172a]/90 px-3 py-2 text-sm font-mono text-slate-200 outline-none transition focus:border-cyan-400/40"
                  placeholder={t('right.scenario.baselinePlaceholder')}
                />
              )}
              <div className={`rounded-md px-2 py-1 text-xs ${primaryMetric === 'combined_score' ? 'bg-emerald-500/10 text-emerald-200 border border-emerald-400/20' : 'bg-amber-500/10 text-amber-100 border border-amber-400/20'}`}>
                {primaryMetric === 'combined_score' ? '优化方向与默认主指标一致。' : '建议主指标使用 combined_score，避免与 evaluator 口径不一致。'}
              </div>
            </div>
          </div>

          <div className="space-y-4 min-[1200px]:sticky min-[1200px]:top-20 self-start">
            <div className="rounded-xl border border-white/10 bg-[#111827]/88 p-4 space-y-3 min-[1200px]:h-[calc(100vh-120px)] min-[1200px]:flex min-[1200px]:flex-col">
              <div className="flex items-center justify-between">
                <div className="text-xs uppercase tracking-[0.14em] text-slate-400">3. 状态 + 日志控制台</div>
                <div className="text-[11px] text-slate-500">状态：{scenarioStatus}</div>
              </div>
              <div className="rounded-lg border border-white/10 bg-[#0b1220]/80 px-3 py-2 text-xs text-slate-300">
                <div><span className="text-slate-400">状态：</span>{scenarioStatus}</div>
                <div className="mt-1"><span className="text-slate-400">当前阶段：</span>{phaseText}</div>
              </div>
              {renderStatusCard()}
              {scenarioStatus === 'IDLE' && (
                <div className="rounded-lg border border-white/10 bg-[#0b1220]/80 p-3 text-xs text-slate-300">
                  <div className="font-semibold mb-1">待补全项</div>
                  {idleMissingItems.length === 0 ? <div>已满足 Gate 前置条件。</div> : idleMissingItems.map((x, i) => <div key={i}>- {x}</div>)}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button onClick={primaryAction.onClick} disabled={primaryAction.disabled}>
                  {busy ? t('right.loading') : primaryAction.label}
                </Button>
                {scenarioStatus === 'FAILED' && (
                  <Button variant="outline" onClick={() => setBaselineOpen(true)}>
                    手动编辑评测规则
                  </Button>
                )}
                {scenarioStatus !== 'IDLE' && (
                  <Button variant="outline" onClick={() => startSession(true).catch(() => {})} disabled={busy || !hasGeneratedFiles}>
                    {t('right.scenario.continueInteractive')}
                  </Button>
                )}
              </div>
              {scenarioStatus === 'IDLE' && !canRunGate && (
                <div className="text-[11px] text-amber-300">请先补全场景配置</div>
              )}
              {showFailureResultCard && (
                <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                  <div className="font-semibold">{gateFailed ? 'Gate 判定失败' : '校验未通过'}</div>
                  <div className="mt-2 text-xs">
                    <div className="font-semibold">失败原因：</div>
                    {(gateResult?.missingInfo || report.errors.map((e) => e.message) || ['缺少关键信息']).slice(0, 4).map((x, i) => <div key={i}>- {x}</div>)}
                    <div className="mt-2 font-semibold">影响：</div>
                    <div>- 无法生成可靠 evaluator.py</div>
                    <div>- 无法计算 combined_score</div>
                    <div className="mt-2 font-semibold">建议：</div>
                    <div>- 补全输入输出格式与运行契约</div>
                    <div>- 允许系统生成默认 evaluator</div>
                    <div>- 保持入口函数与契约一致</div>
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" onClick={() => autoFixAndRetry().catch(() => {})}>自动修复并重新生成</Button>
                    <Button size="sm" variant="outline" onClick={() => setBaselineOpen(true)}>手动编辑评测规则</Button>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Button size="sm" variant={logFilter === 'all' ? 'default' : 'outline'} onClick={() => setLogFilter('all')}>{t('right.scenario.logFilterAll')}</Button>
                <Button size="sm" variant={logFilter === 'warn' ? 'default' : 'outline'} onClick={() => setLogFilter('warn')}>{t('right.scenario.logFilterWarn')}</Button>
                <Button size="sm" variant={logFilter === 'error' ? 'default' : 'outline'} onClick={() => setLogFilter('error')}>{t('right.scenario.logFilterError')}</Button>
              </div>
              <div
                ref={logPanelRef}
                onScroll={(e) => {
                  const el = e.currentTarget;
                  const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
                  setLogAutoFollow(distance < 20);
                }}
                className="rounded-lg border border-white/10 bg-[#0b1220]/95 p-2.5 text-xs font-mono text-slate-300 min-h-[240px] max-h-[360px] min-[1200px]:max-h-none min-[1200px]:flex-1 overflow-y-auto"
              >
                {filteredLogs.length === 0 ? <div>{t('right.scenario.noLogs')}</div> : filteredLogs.map((x, i) => (
                  <div key={i} className={`mb-1 ${x.level === 'error' ? 'text-rose-300' : x.level === 'warn' ? 'text-amber-300' : 'text-slate-300'}`}>
                    <span className="text-slate-500">{new Date(x.timestamp || Date.now()).toLocaleTimeString()}</span>
                    <span className="text-slate-500"> [{x.source}] </span>
                    <span>{x.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {gateResult?.fit && hasGeneratedFiles && (
          <div className="rounded-xl border border-white/10 bg-[#111827]/88 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-[0.14em] text-slate-400">4. 预览创建</div>
              <div className="text-[11px] text-slate-500">{changeSummary || '暂无变化摘要'}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant={activePreviewTab === 'initial' ? 'default' : 'outline'} onClick={() => setActivePreviewTab('initial')}>initial_program.py</Button>
              <Button size="sm" variant={activePreviewTab === 'evaluator' ? 'default' : 'outline'} onClick={() => setActivePreviewTab('evaluator')}>evaluator.py</Button>
              <Button size="sm" variant={activePreviewTab === 'config' ? 'default' : 'outline'} onClick={() => setActivePreviewTab('config')}>config.yaml</Button>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <Button size="sm" variant="outline" onClick={() => handleCopyPreview().catch(() => {})}>复制</Button>
              <Button size="sm" variant="outline" onClick={handleDownloadPreview}>下载</Button>
              <Button size="sm" variant="outline" onClick={() => setShowDiff((v) => !v)}>{showDiff ? '查看源码' : '查看 Diff'}</Button>
            </div>
            <div className="rounded-lg border border-white/10 bg-[#0b1220]/80 px-3 py-2 text-xs text-slate-300">
              <div>initial_program.py：+{delta.initial}</div>
              <div>evaluator.py：+{delta.evaluator}</div>
              <div>config.yaml：+{delta.config}</div>
              <div className="font-semibold">总变更：{delta.total || 0}</div>
            </div>
            <pre className="min-h-[360px] max-h-[560px] overflow-auto rounded-lg border border-white/10 bg-[#0f172a]/90 p-3 text-xs text-slate-200 whitespace-pre-wrap">{showDiff ? previewDiffText : previewText || '暂无内容'}</pre>
            <div className="rounded-lg border border-white/10 bg-[#0b1220]/80 px-3 py-2 text-xs text-slate-300">
              <div className="font-semibold">{report.ok ? '校验通过' : '校验未通过'}</div>
              {!report.ok && <div className="mt-1">原因：{report.errors[0]?.message || '未生成有效 evaluator.py'}</div>}
              {!report.ok && <div>下一步：补充评测规则，或允许系统自动生成 evaluator。</div>}
            </div>
            {showRiskConfirm && (
              <div className="rounded-lg border border-amber-300/20 bg-amber-500/10 p-3 text-xs text-amber-100">
                <div className="font-semibold mb-2">创建项目：{projectName || '(未命名)'}</div>
                <label className="flex items-center gap-2"><input type="checkbox" checked={riskConfirm.secret} onChange={(e) => setRiskConfirm((p) => ({ ...p, secret: e.target.checked }))} /><span>config 不含明文密钥</span></label>
                <label className="mt-1 flex items-center gap-2"><input type="checkbox" checked={riskConfirm.metric} onChange={(e) => setRiskConfirm((p) => ({ ...p, metric: e.target.checked }))} /><span>主指标与优化方向一致</span></label>
                <label className="mt-1 flex items-center gap-2"><input type="checkbox" checked={riskConfirm.contract} onChange={(e) => setRiskConfirm((p) => ({ ...p, contract: e.target.checked }))} /><span>入口函数与 evaluator 匹配</span></label>
                <div className="mt-2 flex items-center gap-2">
                  <Input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder={t('right.scenario.projectNamePlaceholder')} className="rounded-lg border-white/10 bg-[#0f172a]/90" />
                  <Button onClick={() => createProject().catch(() => {})} disabled={creating || !allRisksConfirmed || !projectName.trim()}>{creating ? t('right.saving') : '确认创建项目'}</Button>
                </div>
                <div className="mt-1 text-[11px] text-amber-200/80">创建后仍可在项目中修改文件。</div>
              </div>
            )}
          </div>
        )}

        {error && <div className="rounded border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{error}</div>}
        {message && <div className="rounded border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{message}</div>}
      </div>
    </div>
  );
}

