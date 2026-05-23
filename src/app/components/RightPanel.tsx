import { useState, useEffect, useRef } from 'react';
import { Play, Square, Activity, BarChart2, Settings, FileText, Zap, Copy, Bot, Database } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ScrollArea } from './ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { motion } from 'motion/react';
import { useTheme } from '../contexts/ThemeContext';
import { useLocale } from '../contexts/LocaleContext';
import { isMarkdownFile, renderCodeHtml, renderMarkdownHtml } from './right-panel/previewRender';
import { ScenarioBuilderTab } from './scenario-builder/ScenarioBuilderTab';

interface LogEntry {
  timestamp: string;
  generation: number;
  population: number;
  bestFitness: number;
  metrics?: Record<string, number>;
  topCode: string;
  outputFile: string;
  rawText?: string;
  isRaw?: boolean;
  eventType?: string;
  message?: string;
  runId?: string;
  phase?: string;
  dedupeKey?: string;
  sourceLine?: string;
  channel?: 'agent_response' | 'system_log';
  origin?: string;
  confidence?: 'high' | 'medium' | 'low';
  receivedAt?: number;
}

interface FilePreviewPayload {
  title: string;
  path: string;
  content: string;
  truncated: boolean;
  downloadUrl: string;
  sourceType: 'project' | 'output';
  projectName: string;
  runId?: string;
}

interface OutputUpdatedPayload {
  projectName: string;
  runId: string;
}

interface OutputRunRow {
  projectName: string;
  runId: string;
  outputDir: string;
  mtime: number;
  bestCombined: number | null;
  primaryMetricName?: string | null;
  primaryMetricValue?: number | null;
  fitnessKey?: string | null;
  allMetrics?: Record<string, number>;
}

interface AnalysisHistoryItem {
  id: string;
  createdAt: string;
  model: string;
  focus: string;
  preview: string;
  downloadUrl: string;
}

interface TrendPoint {
  iteration: number;
  metrics: Record<string, number>;
  fitnessKey?: string | null;
  fitnessValue?: number | null;
}

interface VisualizationStatus {
  running: boolean;
  mode: string;
  host: string;
  port: number;
  url: string;
  projectName: string;
  runId: string;
  outputDir: string;
  startedAt: number;
}

interface VisualizationTarget {
  projectName: string;
  runId: string;
}

function buildRunKey(projectName: string, runId: string): string {
  return `${projectName}::${runId}`;
}

function normalizeOutputPath(rawPath: string): string {
  const p = String(rawPath || '').replaceAll('\\', '/');
  const marker = '/server_data/';
  const idx = p.indexOf(marker);
  if (idx >= 0) return p.slice(idx + marker.length);
  return p;
}

function shortenPathForDisplay(pathLike: string, keepHead = 2, keepTail = 2): string {
  const normalized = normalizeOutputPath(pathLike);
  const parts = normalized.split('/').filter(Boolean);
  if (parts.length <= keepHead + keepTail + 1) return normalized;
  const head = parts.slice(0, keepHead).join('/');
  const tail = parts.slice(-keepTail).join('/');
  return `${head}/.../${tail}`;
}

function formatShortTime(unixSeconds: number): string {
  const d = new Date(unixSeconds * 1000);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${mm}-${dd} ${hh}:${mi}`;
}

function pickYamlRaw(text: string, key: string, section?: string): string | null {
  if (!text) return null;
  if (section) {
    const sectionMatch = text.match(new RegExp(`^${section}:\\s*$`, 'm'));
    if (!sectionMatch || sectionMatch.index == null) return null;
    const after = text.slice(sectionMatch.index + sectionMatch[0].length);
    const sectionBody = after.split(/\n(?=\S)/, 1)[0] ?? after;
    const m = sectionBody.match(new RegExp(`^\\s+${key}:\\s*(.+)\\s*$`, 'm'));
    return m ? m[1].trim() : null;
  }
  const m = text.match(new RegExp(`^${key}:\\s*(.+)\\s*$`, 'm'));
  return m ? m[1].trim() : null;
}

function applyConfigDefaults(
  prev: {
    evolutionObject: string;
    populationSize: string;
    generations: string;
    checkpointInterval: string;
    numIslands: string;
    mutationRate: string;
    evaluatorTimeout: string;
    parallelEvaluations: string;
    diffBasedEvolution: boolean;
    archiveSize: string;
    eliteSelectionRatio: string;
    exploitationRatio: string;
    similarityThreshold: string;
    targetObjective: string;
  },
  yamlText: string,
  projectName: string
) {
  const fromYaml = (key: string, section?: string) => pickYamlRaw(yamlText, key, section);
  const boolFromYaml = (key: string, section?: string): boolean | null => {
    const raw = (fromYaml(key, section) || '').toLowerCase();
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    return null;
  };
  return {
    ...prev,
    evolutionObject: projectName,
    generations: fromYaml('max_iterations') || prev.generations,
    checkpointInterval: fromYaml('checkpoint_interval') || prev.checkpointInterval,
    populationSize: fromYaml('population_size', 'database') || prev.populationSize,
    archiveSize: fromYaml('archive_size', 'database') || prev.archiveSize,
    numIslands: fromYaml('num_islands', 'database') || prev.numIslands,
    mutationRate: fromYaml('mutation_rate', 'database') || prev.mutationRate,
    eliteSelectionRatio: fromYaml('elite_selection_ratio', 'database') || prev.eliteSelectionRatio,
    exploitationRatio: fromYaml('exploitation_ratio', 'database') || prev.exploitationRatio,
    similarityThreshold: fromYaml('similarity_threshold', 'database') || prev.similarityThreshold,
    evaluatorTimeout: fromYaml('timeout', 'evaluator') || prev.evaluatorTimeout,
    parallelEvaluations: fromYaml('parallel_evaluations', 'evaluator') || prev.parallelEvaluations,
    diffBasedEvolution: boolFromYaml('diff_based_evolution') ?? prev.diffBasedEvolution,
  };
}

function runIdToShortTime(runId: string): string | null {
  const m = runId.match(/^run_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (!m) return null;
  const [, _yyyy, mm, dd, hh, mi] = m;
  return `${mm}-${dd} ${hh}:${mi}`;
}

function displayRunTime(run: OutputRunRow): string {
  return runIdToShortTime(run.runId) || formatShortTime(run.mtime);
}

function stripAnsi(raw: string): string {
  return raw.replace(/\u001b\[[0-9;]*m/g, '');
}

function normalizeRawLogLine(raw: string): string {
  return stripAnsi(raw).replace(/\s+/g, ' ').trim();
}

function isAgentNarrationLine(text: string): boolean {
  const s = String(text || '').trim();
  if (!s) return false;
  const patterns = [
    // English agent narration patterns
    /^let me\b/i,
    /^i need to\b/i,
    /^now i need to\b/i,
    /^now i('| a)m\b/i,
    /^the user\b/i,
    /^according to\b/i,
    /^based on\b/i,
    /^i('ll| will)\b/i,
    /^first,?\s/i,
    /^next,?\s/i,
    /^finally,?\s/i,
    /^this (should|will|is)\b/i,
    /^here('s| is)\b/i,
    /^looking at\b/i,
    /^checking\b/i,
    /^running\b/i,
    // Chinese agent narration patterns - common openings
    /^openEvolve 任务/,
    /^执行摘要/,
    /^关键日志/,
    /^最佳程序指标/,
    /^输出位置/,
    /^根据规则/,
    /^根据要求/,
    /^命令启动后/,
    /^结束时/,
    /^让我/,
    /^我需要/,
    /^现在执行/,
    /^现在我需要/,
    /^现在/,
    /^这应该/,
    /^这是/,
    /^这表明/,
    /^这说明/,
    /^可以看到/,
    /^看起来/,
    /^接下来/,
    /^首先/,
    /^然后/,
    /^最后/,
    /^任务/,
    /^运行/,
    /^已经/,
    /^正在/,
    /^开始/,
    /^完成/,
    /^成功/,
    /^失败/,
    /^检查/,
    /^查看/,
    /^分析/,
    /^发现/,
    /^结果/,
    /^总结/,
    /^综上/,
    /^因此/,
    /^所以/,
    /^由于/,
    /^目前/,
    /^当前/,
    /^下面/,
    /^以下/,
    /^以上/,
    /^如[上下]/,
    /^请注意/,
    /^注意/,
    /^提示/,
    /^备注/,
    /^说明/,
    // Markdown formatting patterns
    /^\d+\.\s/,
    /^\|.*\|$/,
    /^\*\*.*\*\*$/,
    /^-\s/,
    /^✱\s/,
    /^#+\s/,
    /^>\s/,
    /^```/,
  ];
  return patterns.some((p) => p.test(s));
}

function normalizeMonitorChannel(v: unknown): 'agent_response' | 'system_log' | undefined {
  const s = String(v || '').trim().toLowerCase();
  if (s === 'agent_response' || s === 'system_log') return s;
  return undefined;
}

function normalizeMonitorConfidence(v: unknown): 'high' | 'medium' | 'low' | undefined {
  const s = String(v || '').trim().toLowerCase();
  if (s === 'high' || s === 'medium' || s === 'low') return s;
  return undefined;
}

const NON_FITNESS_METRIC_KEYS = new Set([
  'best',
  'avg',
  'average',
  'diversity',
  'gen',
  'generation',
  'iter',
  'iteration',
  'parent',
  'total',
  'checkpoint',
  'checkpoint_interval',
  'population',
]);

function shouldHideRawLogLine(line: string): boolean {
  if (!line) return true;
  const importantPatterns = [
    /\bIteration\s+\d+\s*:/i,
    /\bat iteration\s+\d+\b/i,
    /\bSaved checkpoint\b/i,
    /\bcheckpoint interval\b/i,
    /\bNew best\b/i,
    /\bbest[_\s-]*fitness\b/i,
    /\bcombined_score\b/i,
    /\bDONE\b/i,
    /\bERROR\b/i,
    /\bTraceback\b/i,
    /\bException\b/i,
    /\bfailed\b/i,
    /\bshutdown request\b/i,
    /早停|提前停止|中止|失败|异常/,
  ];
  if (importantPatterns.some((p) => p.test(line))) return false;

  const noisyPatterns = [
    /^!\s*agent\s+".*"\s+is a subagent.*fallback/i,
    /^>\s*build\s*[·.-]/i,
    /^[•*-]\s*执行\s*OpenEvolve/i,
    /^我将使用\s*OpenEvolve/i,
    /Initialized OpenAI LLM/i,
    /Initialized LLM ensemble/i,
    /Initialized prompt sampler/i,
    /Set custom templates/i,
    /Initialized program database/i,
    /Successfully loaded evaluation function/i,
    /Initialized evaluator with evaluator\.py/i,
    /Initialized process parallel controller/i,
    /Set max .* tasks per child/i,
    /Started process pool/i,
    /Using island-based evolution/i,
    /Island Status/i,
    /Island\s+\d+:\s+\d+\s+programs,\s+best=/i,
    /New MAP-Elites cell occupied/i,
    /Loaded database metadata/i,
    /Loaded feature_stats/i,
    /Reconstructed islands/i,
    /Loaded database with \d+ programs/i,
    /Loading checkpoint from/i,
    /Checkpoint loaded successfully/i,
    /Skipping initial program addition/i,
    /Sampled model:/i,
    /^.*httpx.*HTTP Request: POST .*\/chat\/completions/i,
    /输入路径[:：]/,
    /输出目录[:：]/,
    /最优程序路径[:：]/,
    /评价信息[:：]/,
    /^INFO\s+\d{4}-\d{2}-\d{2}T.*\sservice=bus\b/i,
    /^INFO\s+\d{4}-\d{2}-\d{2}T.*\sservice=tool\.registry\b/i,
    /^INFO\s+\d{4}-\d{2}-\d{2}T.*\sservice=session\b/i,
    /^INFO\s+\d{4}-\d{2}-\d{2}T.*\sservice=permission\b/i,
    /^INFO\s+\d{4}-\d{2}-\d{2}T.*\sservice=llm\b/i,
    /^INFO\s+\d{4}-\d{2}-\d{2}T.*\sservice=bash-tool\b/i,
    /^\[DEBUG\]/i,
  ];
  return noisyPatterns.some((p) => p.test(line));
}

function extractObservedIteration(line: string): number | null {
  const patterns = [
    /\bIteration\s+(\d+)\s*:/i,
    /\bat iteration\s+(\d+)\b/i,
    /New best solution found at iteration\s+(\d+)/i,
    /Saved checkpoint at iteration\s+(\d+)/i,
    /Checkpoint interval reached at iteration\s+(\d+)/i,
  ];
  for (const p of patterns) {
    const m = line.match(p);
    if (m && m[1]) {
      const n = parseInt(m[1], 10);
      if (Number.isFinite(n) && n >= 0) return n;
    }
  }
  return null;
}

function pickPrimaryMetric(run: OutputRunRow): { name: string; value: number | null } {
  const fitnessName = (run.fitnessKey || '').trim();
  if (fitnessName && run.allMetrics && typeof run.allMetrics[fitnessName] === 'number') {
    return { name: fitnessName, value: run.allMetrics[fitnessName] };
  }
  if (typeof run.primaryMetricValue === 'number' && Number.isFinite(run.primaryMetricValue)) {
    return { name: run.primaryMetricName || 'metric', value: run.primaryMetricValue };
  }
  if (typeof run.bestCombined === 'number' && Number.isFinite(run.bestCombined)) {
    return { name: run.primaryMetricName || run.fitnessKey || 'score', value: run.bestCombined };
  }
  return { name: 'metric', value: null };
}

function parseMetricsFromRaw(rawText: string): Record<string, number> {
  const out: Record<string, number> = {};
  const pairRegex = /([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
  let match = pairRegex.exec(rawText);
  while (match) {
    const key = String(match[1] || '').trim();
    const keyLower = key.toLowerCase();
    const val = Number(match[2]);
    // Only keep likely fitness metrics; drop structural counters from raw logs.
    if (key && Number.isFinite(val) && !NON_FITNESS_METRIC_KEYS.has(keyLower)) {
      out[key] = val;
    }
    match = pairRegex.exec(rawText);
  }
  return out;
}

function pickFitnessFromMetrics(metrics: Record<string, number>): { key: string; value: number } | null {
  if (typeof metrics.combined_score === 'number' && Number.isFinite(metrics.combined_score)) {
    return { key: 'combined_score', value: metrics.combined_score };
  }
  if (typeof metrics.bestFitness === 'number' && Number.isFinite(metrics.bestFitness)) {
    return { key: 'bestFitness', value: metrics.bestFitness };
  }
  if (typeof metrics.score === 'number' && Number.isFinite(metrics.score)) {
    return { key: 'score', value: metrics.score };
  }
  for (const [k, v] of Object.entries(metrics)) {
    if (typeof v === 'number' && Number.isFinite(v)) return { key: k, value: v };
  }
  return null;
}

function formatMetricValue(v: number | null | undefined, fixed = 6): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return 'N/A';
  return v.toFixed(fixed);
}

function getMetricColorByRank(index: number): string {
  if (index === 0) return 'text-emerald-300';
  if (index === 1) return 'text-cyan-300';
  if (index === 2) return 'text-violet-300';
  return 'text-slate-300';
}

function buildSimpleLineDiff(beforeText: string, afterText: string, maxLines = 220): string {
  const a = (beforeText || '').split('\n');
  const b = (afterText || '').split('\n');
  const out: string[] = [];
  const maxLen = Math.max(a.length, b.length);
  for (let i = 0; i < maxLen; i += 1) {
    const left = a[i];
    const right = b[i];
    if (left === right) continue;
    if (typeof left === 'string') out.push(`- ${left}`);
    if (typeof right === 'string') out.push(`+ ${right}`);
    if (out.length >= maxLines) break;
  }
  if (out.length === 0) return 'No textual differences detected.';
  if (out.length >= maxLines) out.push('... (diff truncated)');
  return out.join('\n');
}

function toMinuteRunId(runId: string): string {
  const m = runId.match(/^run_(\d{8})_(\d{4})(?:\d{2})?(?:_[a-zA-Z0-9]+)?$/);
  if (m) return `run_${m[1]}_${m[2]}`;
  return runId.length > 18 ? runId.slice(0, 18) : runId;
}

export function RightPanel() {
  const MAX_MONITOR_LOGS = 500;
  const MAX_ANALYSIS_HISTORY = 200;
  const { colors } = useTheme();
  const { t, locale } = useLocale();
  const timeLocale = locale === 'zh' ? 'zh-CN' : 'en-US';
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentGen, setCurrentGen] = useState(0);
  const [targetGenerations, setTargetGenerations] = useState<number | null>(null);
  const [bestMetrics, setBestMetrics] = useState<Record<string, number>>({});
  const [fitnessKey, setFitnessKey] = useState<string>('combined_score');
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastOutputRefreshAtRef = useRef<number>(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [projects, setProjects] = useState<Array<{ name: string }>>([]);
  const [preview, setPreview] = useState<FilePreviewPayload | null>(null);
  const [editing, setEditing] = useState(false);
  const [draftContent, setDraftContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [outputRuns, setOutputRuns] = useState<OutputRunRow[]>([]);
  const [dashboardProject, setDashboardProject] = useState<string>('all');
  const [analysisRunKey, setAnalysisRunKey] = useState<string>('');
  const [analysisFocus, setAnalysisFocus] = useState<string>('');
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string>('');
  const [analysisText, setAnalysisText] = useState<string>('');
  const [analysisMeta, setAnalysisMeta] = useState<{ model: string; projectName: string; runId: string } | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([]);
  const [trendPoints, setTrendPoints] = useState<TrendPoint[]>([]);
  const [artifactData, setArtifactData] = useState<{
    programId: string | null;
    artifacts: Record<string, unknown>;
    artifactFiles: Array<{ name: string; size: number; isText: boolean; content?: string; truncated?: boolean }>;
    initialProgram: string;
    bestProgram: string;
  } | null>(null);
  const [activeTab, setActiveTab] = useState('monitor');
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [configPath, setConfigPath] = useState('');
  const [configText, setConfigText] = useState('');
  const [configMessage, setConfigMessage] = useState('');
  const [configError, setConfigError] = useState('');
  const [monitorLeftWidth, setMonitorLeftWidth] = useState(() => {
    if (typeof window === 'undefined') return 500;
    return Math.round(Math.min(550, Math.max(360, window.innerWidth * 0.34)));
  });
  const [isMonitorResizing, setIsMonitorResizing] = useState(false);
  const [monitorTopHeight, setMonitorTopHeight] = useState(() => {
    if (typeof window === 'undefined') return 240;
    return Math.round(Math.min(300, Math.max(210, window.innerHeight * 0.28)));
  });
  const [isMonitorVerticalResizing, setIsMonitorVerticalResizing] = useState(false);
  const monitorContainerRef = useRef<HTMLDivElement | null>(null);
  const monitorLeftColumnRef = useRef<HTMLDivElement | null>(null);
  const [visualPromptOpen, setVisualPromptOpen] = useState(false);
  const [visualizationTarget, setVisualizationTarget] = useState<VisualizationTarget | null>(null);
  const [visualizationStatus, setVisualizationStatus] = useState<VisualizationStatus | null>(null);
  const [visualizationLoading, setVisualizationLoading] = useState(false);
  const [visualizationError, setVisualizationError] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [scenarioSessionId, setScenarioSessionId] = useState('');

  const [params, setParams] = useState({
    evolutionObject: '',
    populationSize: '30',
    generations: '10',
    checkpointInterval: '3',
    numIslands: '2',
    mutationRate: '0.1',
    evaluatorTimeout: '30',
    parallelEvaluations: '2',
    diffBasedEvolution: true,
    archiveSize: '10',
    eliteSelectionRatio: '0.2',
    exploitationRatio: '0.7',
    similarityThreshold: '0.99',
    targetObjective: 'minimize'
  });

  const bestFitnessValue =
    (typeof bestMetrics[fitnessKey] === 'number' && Number.isFinite(bestMetrics[fitnessKey]))
      ? bestMetrics[fitnessKey]
      : (pickFitnessFromMetrics(bestMetrics)?.value ?? 0);
  const hasBestMetrics = Object.keys(bestMetrics).length > 0;
  const latestKnownBestRef = useRef<number>(0);

  const activeRunIdRef = useRef<string | null>(null);
  const parseMonitorTimestamp = (value: string): number => {
    const ts = String(value || '').trim();
    if (!ts) return Number.NaN;
    const normalized = ts.includes('T') ? ts : ts.replace(' ', 'T');
    const parsed = Date.parse(normalized);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  };

  const appendMonitorLog = (entry: LogEntry) => {
    const nextEntry: LogEntry = {
      ...entry,
      receivedAt: entry.receivedAt ?? Date.now(),
    };
    setLogs((prev) => {
      const withUpsert = [...prev];
      if (nextEntry.isRaw) {
        const key = `${nextEntry.runId || ''}:${nextEntry.generation}:${nextEntry.rawText || ''}`;
        const exists = withUpsert.some(
          (p) => p.isRaw && `${p.runId || ''}:${p.generation}:${p.rawText || ''}` === key
        );
        if (!exists) withUpsert.push(nextEntry);
      } else {
        const eventType = nextEntry.eventType || 'log';
        const key = nextEntry.dedupeKey || `${nextEntry.runId || ''}:${nextEntry.generation}:${eventType}`;
        const idx = withUpsert.findIndex((p) => {
          if (p.isRaw) return false;
          const pType = p.eventType || 'log';
          const pKey = p.dedupeKey || `${p.runId || ''}:${p.generation}:${pType}`;
          return pKey === key;
        });
        if (idx >= 0) {
          withUpsert[idx] = nextEntry;
        } else {
          withUpsert.push(nextEntry);
        }
      }
      withUpsert.sort((a, b) => {
        const ta = parseMonitorTimestamp(a.timestamp);
        const tb = parseMonitorTimestamp(b.timestamp);
        if (Number.isFinite(ta) && Number.isFinite(tb) && ta !== tb) return ta - tb;
        return (a.receivedAt || 0) - (b.receivedAt || 0);
      });
      if (withUpsert.length <= MAX_MONITOR_LOGS) return withUpsert;

      const structured = withUpsert.filter((x) => !x.isRaw);
      const raw = withUpsert.filter((x) => x.isRaw);
      const keepStructured = structured.slice(-Math.min(320, structured.length));
      const keepRaw = raw.slice(-Math.max(0, MAX_MONITOR_LOGS - keepStructured.length));
      return [...keepStructured, ...keepRaw];
    });
  };

  const rawLogs = logs.filter((log) => log.isRaw);
  const isAgentEventHeuristic = (log: LogEntry): boolean => {
    const source = String(log.sourceLine || '').toLowerCase();
    const line = String(log.message || log.rawText || '');
    if (source.includes('opencode_stdout') && isAgentNarrationLine(line)) return true;
    if (isAgentNarrationLine(line) && !source.includes('openevolve_log')) return true;
    return false;
  };

  const getEffectiveChannel = (log: LogEntry): 'agent_response' | 'system_log' => {
    const channel = normalizeMonitorChannel(log.channel);
    if (channel) return channel;
    return isAgentEventHeuristic(log) ? 'agent_response' : 'system_log';
  };

  const channelTooltip = (log: LogEntry): string => {
    const effective = getEffectiveChannel(log);
    const origin = String(log.origin || log.sourceLine || 'unknown');
    const confidence = String(log.confidence || 'n/a');
    return `channel=${effective} | origin=${origin} | confidence=${confidence}`;
  };

  const monitorIcon = (channel: 'agent_response' | 'system_log') => {
    if (channel === 'agent_response') return <Bot className="mt-0.5 size-3 text-violet-300 shrink-0" />;
    return <FileText className="mt-0.5 size-3 text-sky-300 shrink-0" />;
  };

  useEffect(() => {
    if (!isMonitorResizing) return;
    const onMove = (e: MouseEvent) => {
      if (window.innerWidth < 1024) return;
      const root = monitorContainerRef.current;
      if (!root) return;
      const rect = root.getBoundingClientRect();
      if (rect.width <= 0) return;
      const separatorPx = 1;
      const leftMinPx = Math.max(240, Math.min(320, rect.width * 0.24));
      const rightMinPx = Math.min(680, Math.max(460, rect.width * 0.45));
      const maxByRight = Math.max(leftMinPx, rect.width - rightMinPx - separatorPx);
      const raw = e.clientX - rect.left;
      const clamped = Math.min(maxByRight, Math.max(leftMinPx, raw));
      setMonitorLeftWidth(clamped);
    };
    const onUp = () => setIsMonitorResizing(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isMonitorResizing]);

  useEffect(() => {
    if (!isMonitorVerticalResizing) return;
    const onMove = (e: MouseEvent) => {
      if (window.innerWidth < 1024) return;
      const root = monitorLeftColumnRef.current;
      if (!root) return;
      const rect = root.getBoundingClientRect();
      if (rect.height <= 0) return;
      const separatorPx = 2;
      const bottomMinPx = Math.max(200, Math.min(280, rect.height * 0.42));
      const topMinPx = Math.max(150, Math.min(220, rect.height * 0.32));
      const maxByBottom = Math.max(topMinPx, rect.height - bottomMinPx - separatorPx);
      const raw = e.clientY - rect.top;
      const clamped = Math.min(maxByBottom, Math.max(topMinPx, raw));
      setMonitorTopHeight(clamped);
    };
    const onUp = () => setIsMonitorVerticalResizing(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isMonitorVerticalResizing]);

  useEffect(() => {
    if (window.innerWidth < 1024) return;
    const clampMonitorLayout = () => {
      const horizontalRoot = monitorContainerRef.current;
      if (horizontalRoot) {
        const rect = horizontalRoot.getBoundingClientRect();
        if (rect.width > 0) {
          const separatorPx = 1;
          const leftMinPx = Math.max(240, Math.min(320, rect.width * 0.24));
          const rightMinPx = Math.min(680, Math.max(460, rect.width * 0.45));
          const maxByRight = Math.max(leftMinPx, rect.width - rightMinPx - separatorPx);
          setMonitorLeftWidth((prev) => Math.min(maxByRight, Math.max(leftMinPx, prev)));
        }
      }

      const verticalRoot = monitorLeftColumnRef.current;
      if (verticalRoot) {
        const rect = verticalRoot.getBoundingClientRect();
        if (rect.height > 0) {
          const separatorPx = 2;
          const bottomMinPx = Math.max(200, Math.min(280, rect.height * 0.42));
          const topMinPx = Math.max(150, Math.min(220, rect.height * 0.32));
          const maxByBottom = Math.max(topMinPx, rect.height - bottomMinPx - separatorPx);
          setMonitorTopHeight((prev) => Math.min(maxByBottom, Math.max(topMinPx, prev)));
        }
      }
    };

    const rafId = window.requestAnimationFrame(clampMonitorLayout);
    window.addEventListener('resize', clampMonitorLayout);
    return () => {
      window.cancelAnimationFrame(rafId);
      window.removeEventListener('resize', clampMonitorLayout);
    };
  }, []);

  const connectRunEventSource = (runId: string, projectName: string) => {
    if (eventSourceRef.current) {
      try { eventSourceRef.current.close(); } catch { /* ignore */ }
      eventSourceRef.current = null;
    }

    activeRunIdRef.current = runId;
    setActiveRunId(runId);
    setIsRunning(true);
    window.dispatchEvent(new CustomEvent('evolve-run-state', { detail: { running: true, runId } }));

    const es = new EventSource(`/api/runs/${runId}/events`);
    eventSourceRef.current = es;
    const structuredTypes = new Set([
      'log',
      'started',
      'iteration_completed',
      'metrics',
      'new_best',
      'checkpoint_saved',
      'run_summary',
    ]);

    es.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const msgType = String(msg.type || '');
        if (structuredTypes.has(msgType)) {
          const genVal = Number(msg.generation || 0);
          const displayGen = genVal > 0 ? genVal : currentGen;
          const parsedMetrics = (msg.metrics && typeof msg.metrics === 'object')
            ? Object.fromEntries(
                Object.entries(msg.metrics as Record<string, unknown>)
                  .filter(([, v]) => typeof v === 'number' && Number.isFinite(v as number))
                  .map(([k, v]) => [k, Number(v)])
              )
            : {};
          const fitMeta = pickFitnessFromMetrics(parsedMetrics);
          const hasMetricsScore = msgType === 'metrics' && !!fitMeta;
          const inheritedBest = latestKnownBestRef.current > 0 ? latestKnownBestRef.current : bestFitnessValue;
          const eventFitness = Number(msg.bestFitness || fitMeta?.value || 0);
          const bestEntryFitness = Number(
            Math.max(inheritedBest || 0, eventFitness || 0)
          );
          if (hasMetricsScore && bestEntryFitness > 0) {
            latestKnownBestRef.current = bestEntryFitness;
          } else if (bestEntryFitness > 0 && latestKnownBestRef.current <= 0) {
            latestKnownBestRef.current = bestEntryFitness;
          }
          const entry: LogEntry = {
            timestamp: String(msg.timestamp || new Date().toLocaleTimeString(timeLocale, { hour12: false })),
            generation: displayGen,
            population: Number(msg.population || 0),
            bestFitness: bestEntryFitness,
            metrics: parsedMetrics,
            topCode: String(msg.topCode || ''),
            outputFile: String(msg.outputFile || ''),
            eventType: msgType,
            message: String(msg.message || ''),
            runId: String(msg.runId || runId),
            phase: String(msg.phase || ''),
            dedupeKey: String(msg.dedupeKey || ''),
            sourceLine: String(msg.sourceLine || ''),
            channel: normalizeMonitorChannel(msg.channel),
            origin: String(msg.origin || ''),
            confidence: normalizeMonitorConfidence(msg.confidence),
          };
          appendMonitorLog(entry);
          if (genVal > 0) {
            setCurrentGen((g) => Math.max(g, genVal));
          }
          if (fitMeta?.key) {
            setFitnessKey(fitMeta.key);
          }
          setBestMetrics((prev) => {
            const next = { ...prev };
            for (const [k, v] of Object.entries(parsedMetrics)) {
              if (typeof v !== 'number' || !Number.isFinite(v)) continue;
              const old = next[k];
              if (typeof old !== 'number' || !Number.isFinite(old) || v > old) {
                next[k] = v;
              }
            }
            if (fitMeta && (typeof next[fitMeta.key] !== 'number' || fitMeta.value > next[fitMeta.key])) {
              next[fitMeta.key] = fitMeta.value;
            }
            return next;
          });
          const now = Date.now();
          if (now - lastOutputRefreshAtRef.current >= 1200) {
            lastOutputRefreshAtRef.current = now;
            const payload: OutputUpdatedPayload = {
              projectName,
              runId,
            };
            window.dispatchEvent(new CustomEvent('evolve-output-updated', { detail: payload }));
          }
        } else if (msg.type === 'raw') {
          const rawText = normalizeRawLogLine(String(msg.text || ''));
          if (!rawText) return;
          const rawSource = String(msg.source || '');
          const now = Date.now();
          if (now - lastOutputRefreshAtRef.current >= 1200) {
            lastOutputRefreshAtRef.current = now;
            const payload: OutputUpdatedPayload = {
              projectName,
              runId,
            };
            window.dispatchEvent(new CustomEvent('evolve-output-updated', { detail: payload }));
          }
          if (rawSource !== 'openevolve_log' && shouldHideRawLogLine(rawText)) return;
          const obsIter = extractObservedIteration(rawText);
          if (obsIter != null) {
            setCurrentGen((g) => Math.max(g, obsIter));
          }
          // Raw channel is text-only for monitor rendering.
          // Do not parse raw numbers into dashboard metrics to avoid log-number interference.
          const entry: LogEntry = {
            timestamp: String(msg.timestamp || new Date().toLocaleTimeString(timeLocale, { hour12: false })),
            generation: obsIter ?? currentGen,
            population: 0,
            bestFitness: latestKnownBestRef.current > 0 ? latestKnownBestRef.current : bestFitnessValue,
            metrics: {},
            topCode: '',
            outputFile: '',
            rawText,
            isRaw: true,
            runId: String(msg.runId || runId),
            eventType: 'raw',
            message: rawText,
            sourceLine: rawSource,
            channel: normalizeMonitorChannel(msg.channel),
            origin: String(msg.origin || rawSource),
            confidence: normalizeMonitorConfidence(msg.confidence),
          };
          appendMonitorLog(entry);
        } else if (msg.type === 'done') {
          activeRunIdRef.current = null;
          setIsRunning(false);
          setVisualizationTarget({ projectName, runId });
          setVisualPromptOpen(true);
          setVisualizationError('');
          window.dispatchEvent(new CustomEvent('evolve-run-state', { detail: { running: false, runId } }));
          try { es.close(); } catch { /* ignore */ }
          window.dispatchEvent(new Event('evolve-projects-updated'));
        }
      } catch (e) {
        console.error(e);
      }
    };

    es.onerror = () => {
      activeRunIdRef.current = null;
      setIsRunning(false);
      window.dispatchEvent(new CustomEvent('evolve-run-state', { detail: { running: false, runId } }));
      try { es.close(); } catch { /* ignore */ }
    };
  };

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const res = await fetch('/api/projects');
        if (!res.ok) throw new Error(`GET /api/projects failed: ${res.status}`);
        const data = await res.json();
        const list = (data.projects || []) as Array<{ name: string }>;
        setProjects(list);
        setParams((prev) => {
          if (list.length === 0) return { ...prev, evolutionObject: '' };
          const stillValid = list.some((p) => p.name === prev.evolutionObject);
          if (stillValid) return prev;
          return { ...prev, evolutionObject: list[0].name };
        });
      } catch (err) {
        console.error(err);
        setProjects([]);
      }
    };
    loadProjects();
    const onProjectsUpdated = () => {
      loadProjects();
    };
    window.addEventListener('evolve-projects-updated', onProjectsUpdated);
    return () => {
      window.removeEventListener('evolve-projects-updated', onProjectsUpdated);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadVisualizationStatus = async () => {
    const res = await fetch('/api/outputs/visualization/status');
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `status failed: ${res.status}`);
    setVisualizationStatus({
      running: Boolean(data.running),
      mode: String(data.mode || 'single'),
      host: String(data.host || '127.0.0.1'),
      port: Number(data.port || 8088),
      url: String(data.url || ''),
      projectName: String(data.projectName || ''),
      runId: String(data.runId || ''),
      outputDir: String(data.outputDir || ''),
      startedAt: Number(data.startedAt || 0),
    });
  };

  useEffect(() => {
    loadVisualizationStatus().catch(() => {
      setVisualizationStatus(null);
    });
    const onRefresh = () => {
      loadVisualizationStatus().catch(() => {
        setVisualizationStatus(null);
      });
    };
    window.addEventListener('evolve-projects-updated', onRefresh);
    return () => {
      window.removeEventListener('evolve-projects-updated', onRefresh);
    };
  }, []);

  useEffect(() => {
    if (!analysisRunKey && outputRuns.length > 0) {
      const first = outputRuns[0];
      setAnalysisRunKey(buildRunKey(first.projectName, first.runId));
    }
  }, [analysisRunKey, outputRuns]);

  useEffect(() => {
    if (outputRuns.length === 0) {
      setVisualizationTarget(null);
      return;
    }
    const first = outputRuns[0];
    setVisualizationTarget((prev) => {
      if (!prev) {
        return { projectName: first.projectName, runId: first.runId };
      }
      const exists = outputRuns.some(
        (r) => r.projectName === prev.projectName && r.runId === prev.runId
      );
      return exists ? prev : { projectName: first.projectName, runId: first.runId };
    });
  }, [outputRuns]);

  const loadAnalysisHistory = async (projectName: string, runId: string) => {
    const res = await fetch(`/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}/analyses`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `load history failed: ${res.status}`);
    const items = ((data.items || []) as AnalysisHistoryItem[]).slice(0, MAX_ANALYSIS_HISTORY);
    setAnalysisHistory(items);
  };

  const loadTrend = async (projectName: string, runId: string) => {
    const res = await fetch(`/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}/trend`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `load trend failed: ${res.status}`);
    const points = Array.isArray(data.points) ? data.points : [];
    const safe: TrendPoint[] = points
      .map((p: any) => {
        const metrics = (p?.metrics && typeof p.metrics === 'object')
          ? Object.fromEntries(
              Object.entries(p.metrics as Record<string, unknown>)
                .filter(([, v]) => typeof v === 'number' && Number.isFinite(v as number))
                .map(([k, v]) => [k, Number(v)])
            )
          : {};
        return {
          iteration: Number(p?.iteration || 0),
          metrics,
          fitnessKey: typeof p?.fitnessKey === 'string' ? p.fitnessKey : null,
          fitnessValue: typeof p?.fitnessValue === 'number' ? p.fitnessValue : null,
        };
      })
      .filter((p) => Number.isFinite(p.iteration) && p.iteration > 0);
    setTrendPoints(safe);
  };

  const loadArtifacts = async (projectName: string, runId: string) => {
    const res = await fetch(`/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}/artifacts`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `load artifacts failed: ${res.status}`);
    setArtifactData({
      programId: typeof data.programId === 'string' ? data.programId : null,
      artifacts: data.artifacts && typeof data.artifacts === 'object' ? data.artifacts : {},
      artifactFiles: Array.isArray(data.artifactFiles) ? data.artifactFiles : [],
      initialProgram: String(data.initialProgram || ''),
      bestProgram: String(data.bestProgram || ''),
    });
  };

  useEffect(() => {
    const selected = outputRuns.find((r) => buildRunKey(r.projectName, r.runId) === analysisRunKey);
    if (!selected) {
      setAnalysisHistory([]);
      setTrendPoints([]);
      setArtifactData(null);
      return;
    }
    loadAnalysisHistory(selected.projectName, selected.runId).catch((e) => {
      console.error(e);
      setAnalysisHistory([]);
    });
    loadTrend(selected.projectName, selected.runId).catch((e) => {
      console.error(e);
      setTrendPoints([]);
    });
    loadArtifacts(selected.projectName, selected.runId).catch((e) => {
      console.error(e);
      setArtifactData(null);
    });
  }, [analysisRunKey, outputRuns]);

  const loadProjectConfig = async (projectName: string) => {
    if (!projectName) return;
    setConfigLoading(true);
    setConfigError('');
    setConfigMessage('');
    const candidates = ['config.yaml', 'config_default.yaml', 'config.yml'];
    try {
      let loaded = false;
      for (const relPath of candidates) {
        const res = await fetch(
          `/api/projects/${encodeURIComponent(projectName)}/file?path=${encodeURIComponent(relPath)}&maxBytes=262144`
        );
        if (!res.ok) continue;
        const data = await res.json().catch(() => ({}));
        const loadedText = String(data?.content || '');
        setConfigPath(relPath);
        setConfigText(loadedText);
        setParams((prev) => applyConfigDefaults(prev, loadedText, projectName));
        loaded = true;
        break;
      }
      if (!loaded) {
        setConfigPath('');
        setConfigText('');
        setConfigError(t('right.configNotFound'));
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('right.loadConfigFailed');
      setConfigError(msg);
    } finally {
      setConfigLoading(false);
    }
  };

  const loadMetricSchema = async (projectName: string) => {
    if (!projectName) return;
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(projectName)}/metrics-schema`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) return;
      const key = String(data?.fitnessKey || '').trim();
      if (key) {
        setFitnessKey(key);
      }
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    if (!params.evolutionObject) {
      setConfigPath('');
      setConfigText('');
      setConfigError('');
      setConfigMessage('');
      return;
    }
    loadMetricSchema(params.evolutionObject).catch(() => {});
    loadProjectConfig(params.evolutionObject).catch((e) => console.error(e));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.evolutionObject]);

  useEffect(() => {
    const loadOutputs = async () => {
      try {
        const res = await fetch('/api/outputs');
        if (!res.ok) throw new Error(`GET /api/outputs failed: ${res.status}`);
        const data = await res.json();
        setOutputRuns((data.runs || []) as OutputRunRow[]);
      } catch (err) {
        console.error(err);
        setOutputRuns([]);
      }
    };

    loadOutputs();
    const onRefresh = () => loadOutputs();
    window.addEventListener('evolve-projects-updated', onRefresh);
    return () => {
      window.removeEventListener('evolve-projects-updated', onRefresh);
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs.length]);

  useEffect(() => {
    const onPreview = (evt: Event) => {
      const custom = evt as CustomEvent<FilePreviewPayload>;
      if (custom.detail) {
        setPreview(custom.detail);
        setDraftContent(custom.detail.content || '');
        setEditing(false);
      }
    };
    window.addEventListener('evolve-file-preview', onPreview as EventListener);
    return () => {
      window.removeEventListener('evolve-file-preview', onPreview as EventListener);
    };
  }, []);

  useEffect(() => {
    const stopRunOnUnload = () => {
      const rid = activeRunIdRef.current;
      if (!rid) return;
      const url = `/api/runs/${encodeURIComponent(rid)}/stop`;
      try {
        // Prefer Beacon for tab close / refresh.
        const payload = new Blob(['{}'], { type: 'application/json' });
        if (navigator.sendBeacon) {
          navigator.sendBeacon(url, payload);
        }
      } catch {
        /* ignore */
      }
      // Keepalive fetch as secondary path for browsers/environments where beacon is dropped.
      try {
        void fetch(url, { method: 'POST', keepalive: true }).catch(() => ({}));
      } catch {
        /* ignore */
      }
      if (eventSourceRef.current) {
        try { eventSourceRef.current.close(); } catch { /* ignore */ }
        eventSourceRef.current = null;
      }
      activeRunIdRef.current = null;
    };

    const onBeforeUnload = () => stopRunOnUnload();
    const onPageHide = () => stopRunOnUnload();

    window.addEventListener('beforeunload', onBeforeUnload);
    window.addEventListener('pagehide', onPageHide);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
      window.removeEventListener('pagehide', onPageHide);
    };
  }, []);

  const handleStart = async () => {
    if (!params.evolutionObject) return;

    setLogs([]);
    setCurrentGen(0);
    const planned = parseInt(params.generations, 10);
    setTargetGenerations(Number.isFinite(planned) && planned > 0 ? planned : null);
    setBestMetrics({});
    setFitnessKey('combined_score');
    latestKnownBestRef.current = 0;
    setIsRunning(true);

    if (eventSourceRef.current) {
      try { eventSourceRef.current.close(); } catch { /* ignore */ }
      eventSourceRef.current = null;
    }
    setActiveRunId(null);

    const iterations = parseInt(params.generations, 10);
    const checkpointInterval = parseInt(params.checkpointInterval, 10);
    const numIslands = parseInt(params.numIslands, 10);
    const populationSize = parseInt(params.populationSize, 10);
    const evaluatorTimeout = parseInt(params.evaluatorTimeout, 10);
    const parallelEvaluations = parseInt(params.parallelEvaluations, 10);
    const mutationRate = parseFloat(params.mutationRate);
    const archiveSize = parseInt(params.archiveSize, 10);
    const eliteSelectionRatio = parseFloat(params.eliteSelectionRatio);
    const exploitationRatio = parseFloat(params.exploitationRatio);
    const similarityThreshold = parseFloat(params.similarityThreshold);
    const res = await fetch('/api/runs/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        projectName: params.evolutionObject,
        iterations: Number.isFinite(iterations) ? iterations : 10,
        checkpointInterval:
          Number.isFinite(checkpointInterval) && checkpointInterval > 0 ? checkpointInterval : 3,
        numIslands:
          Number.isFinite(numIslands) && numIslands > 0 ? numIslands : 2,
        populationSize:
          Number.isFinite(populationSize) && populationSize > 0 ? populationSize : 30,
        evaluatorTimeout:
          Number.isFinite(evaluatorTimeout) && evaluatorTimeout > 0 ? evaluatorTimeout : 30,
        parallelEvaluations:
          Number.isFinite(parallelEvaluations) && parallelEvaluations > 0 ? parallelEvaluations : 2,
        mutationRate:
          Number.isFinite(mutationRate) && mutationRate >= 0 && mutationRate <= 1
            ? mutationRate
            : 0.1,
        diffBasedEvolution: params.diffBasedEvolution,
        archiveSize: Number.isFinite(archiveSize) && archiveSize > 0 ? archiveSize : 10,
        eliteSelectionRatio:
          Number.isFinite(eliteSelectionRatio) && eliteSelectionRatio >= 0 && eliteSelectionRatio <= 1
            ? eliteSelectionRatio
            : 0.2,
        exploitationRatio:
          Number.isFinite(exploitationRatio) && exploitationRatio >= 0 && exploitationRatio <= 1
            ? exploitationRatio
            : 0.7,
        similarityThreshold:
          Number.isFinite(similarityThreshold) && similarityThreshold >= 0 && similarityThreshold <= 1
            ? similarityThreshold
            : 0.99,
      }),
    });

    if (!res.ok) {
      setIsRunning(false);
      const err = await res.json().catch(() => ({}));
      alert(err?.error || t('right.startFailed'));
      return;
    }

    const data = await res.json();
    const runId = String(data.runId || '');
    connectRunEventSource(runId, params.evolutionObject);
  };

  const handleStop = async () => {
    setIsRunning(false);

    const runId = activeRunId;
    if (!runId) return;
    activeRunIdRef.current = null;
    window.dispatchEvent(new CustomEvent('evolve-run-state', { detail: { running: false, runId } }));
    await fetch(`/api/runs/${runId}/stop`, { method: 'POST' }).catch(() => ({}));
    window.setTimeout(() => {
      if (eventSourceRef.current) {
        try { eventSourceRef.current.close(); } catch { /* ignore */ }
        eventSourceRef.current = null;
      }
      window.dispatchEvent(new Event('evolve-projects-updated'));
    }, 800);
  };

  if (preview) {
    const previewHtml = isMarkdownFile(preview.path)
      ? renderMarkdownHtml(preview.content || '')
      : renderCodeHtml(preview.content || '', preview.path || preview.title);

    const handleSave = async () => {
      if (!preview) return;
      setSaving(true);
      try {
        let url = '';
        if (preview.sourceType === 'project') {
          url = `/api/projects/${encodeURIComponent(preview.projectName)}/file`;
        } else {
          url = `/api/outputs/${encodeURIComponent(preview.projectName)}/${encodeURIComponent(preview.runId || '')}/file`;
        }
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: preview.path, content: draftContent }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err?.error || `save failed: ${res.status}`);
        }
        setPreview({ ...preview, content: draftContent, truncated: false });
        setEditing(false);
      } catch (e) {
        const msg = e instanceof Error ? e.message : t('right.saveFailed');
        alert(msg);
      } finally {
        setSaving(false);
      }
    };

    const copyPreviewPath = async () => {
      const value = preview.title || preview.path;
      try {
        await navigator.clipboard.writeText(value);
      } catch {
        const ta = document.createElement('textarea');
        ta.value = value;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      window.alert(t('right.pathCopied'));
    };

    return (
      <div className="h-full flex-1 min-h-0 min-w-0 flex flex-col bg-[#0f172a]/80">
        <div className="flex-1 min-h-0 p-4">
          <div className="h-full rounded-lg border border-white/10 bg-[#0f172a]/85 flex flex-col overflow-hidden">
            <div className="border-b border-white/10 px-3 py-2 flex items-start justify-between gap-2">
              <div className="min-w-0 max-w-full break-all text-[11px] text-slate-400" title={preview.title}>
                {preview.title}
              </div>
              <div className="shrink-0 flex items-center gap-2">
                <button
                  className="oe-ghost-btn rounded px-2 py-1 text-[11px]"
                  onClick={() => copyPreviewPath().catch(console.error)}
                >
                  <span className="inline-flex items-center gap-1">
                    <Copy className="size-3" />
                    {t('right.copyPath')}
                  </span>
                </button>
                <a
                  href={preview.downloadUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="oe-ghost-btn rounded px-2 py-1 text-[11px]"
                >
                  {t('right.download')}
                </a>
                {!editing && (
                  <button
                    className="oe-ghost-btn rounded px-2 py-1 text-[11px]"
                    onClick={() => {
                      setDraftContent(preview.content || '');
                      setEditing(true);
                    }}
                  >
                    {t('right.edit')}
                  </button>
                )}
                {editing && (
                  <>
                    <button
                      className="oe-primary-soft-btn rounded px-2 py-1 text-[11px] disabled:opacity-60"
                      onClick={handleSave}
                      disabled={saving}
                    >
                      {saving ? t('right.saving') : t('right.save')}
                    </button>
                    <button
                      className="oe-ghost-btn rounded px-2 py-1 text-[11px]"
                      onClick={() => {
                        setDraftContent(preview.content || '');
                        setEditing(false);
                      }}
                    >
                      {t('right.cancel')}
                    </button>
                  </>
                )}
                <button
                  className="oe-ghost-btn rounded px-2 py-1 text-[11px]"
                  onClick={() => setPreview(null)}
                >
                  {t('right.closePreview')}
                </button>
              </div>
            </div>
            {editing ? (
              <textarea
                className="flex-1 min-h-0 w-full bg-transparent px-3 py-3 text-[12px] leading-6 text-slate-200 font-mono whitespace-pre outline-none resize-none"
                value={draftContent}
                onChange={(e) => setDraftContent(e.target.value)}
                spellCheck={false}
              />
            ) : (
              <div
                className="preview-renderer flex-1 min-h-0 overflow-auto px-3 py-3 text-[13px] leading-6 text-slate-100"
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            )}
            {preview.truncated && (
              <div className="border-t border-white/10 px-3 py-2 text-[11px] text-slate-500">
                {t('right.fileTooLarge')}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  const projectOptions = Array.from(new Set(outputRuns.map((r) => r.projectName)));
  const filteredRuns = outputRuns.filter((r) => dashboardProject === 'all' || r.projectName === dashboardProject);
  const latestRuns = filteredRuns.slice(0, 8);
  const metricNames = Array.from(
    new Set(
      latestRuns.flatMap((r) => {
        if (r.allMetrics && Object.keys(r.allMetrics).length > 0) {
          return Object.keys(r.allMetrics);
        }
        const primary = pickPrimaryMetric(r);
        return primary.value != null ? [primary.name] : [];
      })
    )
  );
  const effectiveFitnessKey =
    metricNames.includes(fitnessKey)
      ? fitnessKey
      : metricNames.includes('combined_score')
        ? 'combined_score'
        : (metricNames[0] || 'combined_score');
  const metricRows = latestRuns
    .map((r) => {
      const val = r.allMetrics?.[effectiveFitnessKey];
      if (typeof val === 'number' && Number.isFinite(val)) {
        return { ...r, metricName: effectiveFitnessKey, metricValue: val };
      }
      const primary = pickPrimaryMetric(r);
      return { ...r, metricName: primary.name, metricValue: primary.value };
    })
    .filter((r) => typeof r.metricValue === 'number' && Number.isFinite(r.metricValue)) as Array<
      OutputRunRow & { metricName: string; metricValue: number }
    >;
  const latestMetric = metricRows[0];
  const bestMetric = metricRows.reduce<(typeof latestMetric) | null>((acc, r) => {
    if (!acc) return r;
    return r.metricValue > acc.metricValue ? r : acc;
  }, null);
  const avgMetric = metricRows.length > 0 ? metricRows.reduce((s, r) => s + r.metricValue, 0) / metricRows.length : null;
  const improvement = metricRows.length >= 2 ? metricRows[0].metricValue - metricRows[metricRows.length - 1].metricValue : null;
  const trendData = trendPoints.map((p) => ({ iteration: p.iteration, ...(p.metrics || {}) }));
  const multiRunCompareData = metricRows
    .slice()
    .reverse()
    .map((r, idx) => ({
      order: idx + 1,
      runId: toMinuteRunId(r.runId),
      runTime: displayRunTime(r),
      metricName: r.metricName,
      metricValue: r.metricValue,
      projectName: r.projectName,
    }));
  const selectedAnalysisRun = outputRuns.find((r) => buildRunKey(r.projectName, r.runId) === analysisRunKey) || null;
  const bestProgramDiff = artifactData
    ? buildSimpleLineDiff(artifactData.initialProgram || '', artifactData.bestProgram || '')
    : '';
  const latestOutputRun = outputRuns[0] || null;
  const effectiveVisualizationTarget: VisualizationTarget | null =
    visualizationTarget || (latestOutputRun ? { projectName: latestOutputRun.projectName, runId: latestOutputRun.runId } : null);
  const visualizationTargetKey = effectiveVisualizationTarget
    ? buildRunKey(effectiveVisualizationTarget.projectName, effectiveVisualizationTarget.runId)
    : '';

  const handleStartVisualization = async (openPromptAfter = false) => {
    const target = effectiveVisualizationTarget;
    if (!target) {
      setVisualizationError(t('right.visualNoRun'));
      return;
    }
    setVisualizationLoading(true);
    setVisualizationError('');
    try {
      const res = await fetch(
        `/api/outputs/${encodeURIComponent(target.projectName)}/${encodeURIComponent(target.runId)}/visualization/start`,
        { method: 'POST' }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.error || `start visualization failed: ${res.status}`);
      }
      const nextStatus: VisualizationStatus = {
        running: Boolean(data.running),
        mode: String(data.mode || 'single'),
        host: String(data.host || '127.0.0.1'),
        port: Number(data.port || 8088),
        url: String(data.url || ''),
        projectName: String(data.projectName || target.projectName),
        runId: String(data.runId || target.runId),
        outputDir: String(data.outputDir || ''),
        startedAt: Number(data.startedAt || 0),
      };
      setVisualizationStatus(nextStatus);
      setVisualizationTarget({ projectName: nextStatus.projectName, runId: nextStatus.runId });
      if (nextStatus.url) {
        window.open(nextStatus.url, '_blank', 'noopener,noreferrer');
      }
      if (openPromptAfter) {
        setVisualPromptOpen(false);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('right.visualStartFailed');
      setVisualizationError(msg);
    } finally {
      setVisualizationLoading(false);
    }
  };

  const handleAnalyzeRun = async () => {
    if (!selectedAnalysisRun) return;
    setAnalysisLoading(true);
    setAnalysisError('');
    try {
      const res = await fetch(
        `/api/outputs/${encodeURIComponent(selectedAnalysisRun.projectName)}/${encodeURIComponent(selectedAnalysisRun.runId)}/analyze`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            focus: analysisFocus.trim(),
            maxBytes: 65536,
          }),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.error || `analyze failed: ${res.status}`);
      }
      setAnalysisText(String(data.analysis || ''));
      setAnalysisMeta({
        model: String(data.model || ''),
        projectName: String(data.projectName || selectedAnalysisRun.projectName),
        runId: String(data.runId || selectedAnalysisRun.runId),
      });
      await loadAnalysisHistory(selectedAnalysisRun.projectName, selectedAnalysisRun.runId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'analysis failed';
      setAnalysisError(msg);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleDeleteAnalysis = async (item: AnalysisHistoryItem) => {
    if (!selectedAnalysisRun) return;
    const ok = window.confirm(t('right.confirmDeleteAnalysis', { id: item.id }));
    if (!ok) return;
    const res = await fetch(
      `/api/outputs/${encodeURIComponent(selectedAnalysisRun.projectName)}/${encodeURIComponent(selectedAnalysisRun.runId)}/analyses/${encodeURIComponent(item.id)}`,
      { method: 'DELETE' }
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data?.error || `delete failed: ${res.status}`);
    }
    await loadAnalysisHistory(selectedAnalysisRun.projectName, selectedAnalysisRun.runId);
  };

  const handleViewAnalysis = async (item: AnalysisHistoryItem) => {
    if (!selectedAnalysisRun) return;
    const res = await fetch(
      `/api/outputs/${encodeURIComponent(selectedAnalysisRun.projectName)}/${encodeURIComponent(selectedAnalysisRun.runId)}/analyses/${encodeURIComponent(item.id)}?raw=1`
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data?.error || `load analysis failed: ${res.status}`);
    }
    setAnalysisText(String(data.analysis || ''));
    setAnalysisMeta({
      model: String(data.model || ''),
      projectName: String(data.projectName || selectedAnalysisRun.projectName),
      runId: String(data.runId || selectedAnalysisRun.runId),
    });
    setAnalysisError('');
  };

  const handleSaveConfig = async () => {
    if (!params.evolutionObject || !configPath) return;
    setConfigSaving(true);
    setConfigError('');
    setConfigMessage('');
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(params.evolutionObject)}/file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: configPath, content: configText }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.error || `save failed: ${res.status}`);
      }
      setConfigMessage(t('right.configSaved', { path: configPath }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('right.saveFailed');
      setConfigError(msg);
    } finally {
      setConfigSaving(false);
    }
  };

  return (
    <div className="h-full flex-1 min-h-0 min-w-0 flex flex-col bg-[#0f172a]/80">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 min-h-0 flex flex-col">
        <TabsList className="w-full justify-start rounded-none border-b border-white/10 bg-[#111827]/90 px-2.5 h-10 overflow-x-auto gap-1">
          <TabsTrigger 
            value="monitor" 
            className="gap-1.5 rounded-md border border-transparent px-3 py-1 text-[12px] font-medium transition-all duration-200 hover:border-white/20 hover:bg-white/5 data-[state=active]:border-white/20 data-[state=active]:bg-white/10 data-[state=active]:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_6px_16px_rgba(2,6,23,0.35)]"
            style={{ 
              ['--active-color' as any]: colors.primary
            }}
          >
            <Activity className="size-3.5" />
            {t('right.tab.monitor')}
          </TabsTrigger>
          <TabsTrigger 
            value="dashboard" 
            className="gap-1.5 rounded-md border border-transparent px-3 py-1 text-[12px] font-medium transition-all duration-200 hover:border-white/20 hover:bg-white/5 data-[state=active]:border-white/20 data-[state=active]:bg-white/10 data-[state=active]:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_6px_16px_rgba(2,6,23,0.35)]"
            style={{ 
              ['--active-color' as any]: colors.primary
            }}
          >
            <BarChart2 className="size-3.5" />
            {t('right.tab.dashboard')}
          </TabsTrigger>
          <TabsTrigger 
            value="results" 
            className="gap-1.5 rounded-md border border-transparent px-3 py-1 text-[12px] font-medium transition-all duration-200 hover:border-white/20 hover:bg-white/5 data-[state=active]:border-white/20 data-[state=active]:bg-white/10 data-[state=active]:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_6px_16px_rgba(2,6,23,0.35)]"
            style={{ 
              ['--active-color' as any]: colors.primary
            }}
          >
            <FileText className="size-3.5" />
            {t('right.tab.results')}
          </TabsTrigger>
          <TabsTrigger 
            value="config" 
            className="gap-1.5 rounded-md border border-transparent px-3 py-1 text-[12px] font-medium transition-all duration-200 hover:border-white/20 hover:bg-white/5 data-[state=active]:border-white/20 data-[state=active]:bg-white/10 data-[state=active]:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_6px_16px_rgba(2,6,23,0.35)]"
            style={{ 
              ['--active-color' as any]: colors.primary
            }}
          >
            <Settings className="size-3.5" />
            {t('right.tab.config')}
          </TabsTrigger>
          <TabsTrigger
            value="scenario"
            className="gap-1.5 rounded-md border border-transparent px-3 py-1 text-[12px] font-medium transition-all duration-200 hover:border-white/20 hover:bg-white/5 data-[state=active]:border-white/20 data-[state=active]:bg-white/10 data-[state=active]:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_6px_16px_rgba(2,6,23,0.35)]"
            style={{
              ['--active-color' as any]: colors.primary
            }}
          >
            <Database className="size-3.5" />
            {t('right.tab.scenario')}
          </TabsTrigger>
        </TabsList>

        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <TabsContent value="monitor" className="flex-1 min-h-0 m-0 p-3 overflow-hidden">
            <div
              ref={monitorContainerRef}
              className="h-full min-h-0 grid grid-cols-1 lg:[grid-template-columns:var(--monitor-left)_2px_minmax(0,1fr)] lg:gap-0"
              style={{ ['--monitor-left' as any]: `${monitorLeftWidth}px` }}
            >
              <div
                ref={monitorLeftColumnRef}
                className="min-h-0 min-w-0 grid pr-1 lg:[grid-template-rows:var(--monitor-top)_4px_minmax(0,1fr)]"
                style={{ ['--monitor-top' as any]: `${monitorTopHeight}px` }}
              >
                <div className="min-h-0 h-full grid grid-cols-1 xl:[grid-template-columns:minmax(0,0.75fr)_minmax(0,1.25fr)] gap-2.5 pb-1">
                  <motion.div
                    className={`min-w-0 h-full min-h-0 bg-gradient-to-br border border-white/10 rounded-xl p-3 shadow-[0_10px_30px_rgba(2,6,23,0.35)] ${colors.gradient} flex flex-col items-center justify-center text-center`}
                    style={{ boxShadow: '0 8px 24px rgba(2, 6, 23, 0.42)' }}
                    animate={isRunning ? { scale: [1, 1.02, 1] } : {}}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Zap className="size-3.5" style={{ color: colors.primary }} />
                      <span className="text-xs font-semibold text-cyan-200 tracking-[0.12em]">{t('right.observedProgress')}</span>
                    </div>
                    <div className="text-[30px] leading-none font-semibold font-mono text-cyan-300">{currentGen}</div>
                    {targetGenerations != null && (
                      <div className="mt-1 text-xs leading-snug text-slate-300">
                        {t('right.targetProgressNote', { n: targetGenerations })}
                      </div>
                    )}
                  </motion.div>

                  <motion.div
                    className={`min-w-0 h-full min-h-0 bg-gradient-to-br from-emerald-600/10 to-emerald-900/20 border border-white/10 rounded-xl p-3 shadow-[0_10px_30px_rgba(2,6,23,0.35)] flex flex-col ${hasBestMetrics ? '' : 'items-center justify-center text-center'}`}
                    animate={isRunning ? { scale: [1, 1.02, 1] } : {}}
                    transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Activity className="size-3.5 text-emerald-400" />
                      <span className="text-sm font-semibold text-emerald-200 uppercase tracking-[0.12em]">{t('right.bestScore')}</span>
                    </div>
                    <div className="text-[34px] leading-none font-semibold text-emerald-300 font-mono">{bestFitnessValue.toFixed(3)}</div>
                    {hasBestMetrics && (
                      <div className="mt-2 flex-1 min-h-0 rounded-lg border border-white/10 bg-[#0b1220]/65 p-1.5 space-y-1 overflow-y-auto oe-scrollbar">
                        {Object.entries(bestMetrics)
                          .sort(([a], [b]) => (a === fitnessKey ? -1 : b === fitnessKey ? 1 : a.localeCompare(b)))
                          .map(([name, value], idx) => (
                            <div key={name} className="flex items-center justify-between gap-2 text-[13px] leading-6 font-mono">
                              <span className={`truncate ${name === fitnessKey ? 'text-emerald-200' : 'text-slate-400'}`}>{name}</span>
                              <span className={name === fitnessKey ? 'text-emerald-300' : getMetricColorByRank(idx)}>{formatMetricValue(value, 4)}</span>
                            </div>
                          ))}
                      </div>
                    )}
                  </motion.div>
                </div>

                <div
                  role="separator"
                  aria-orientation="horizontal"
                  className={`hidden lg:block mt-0.5 cursor-row-resize rounded-sm transition-colors ${
                    isMonitorVerticalResizing ? 'bg-emerald-400/70' : 'bg-white/20 hover:bg-emerald-400/50'
                  }`}
                  onMouseDown={() => setIsMonitorVerticalResizing(true)}
                  title={t('app.resizeSeparator')}
                />

                <div className="min-h-0 overflow-y-auto oe-scrollbar pr-1">
                  <div className="border border-white/10 rounded-xl bg-[#111827]/90 p-3 shadow-[0_8px_24px_rgba(2,6,23,0.28)]">
                    <div className="mb-2.5 flex items-center gap-2 border-b border-white/8 pb-2">
                      <div className="size-1.5 rounded-full" style={{ backgroundColor: colors.accent }}></div>
                      <h3 className="text-[10px] font-semibold tracking-[0.14em] uppercase text-slate-400">{t('right.controlPanel')}</h3>
                    </div>

                    <div className="space-y-2">
                    <div>
                      <Label htmlFor="evo-object" className="text-[11px] text-gray-400 mb-1.5">{t('right.selectEvolveObject')}</Label>
                      <Select value={params.evolutionObject} onValueChange={(value) => setParams({ ...params, evolutionObject: value })}>
                        <SelectTrigger id="evo-object" className="h-7 bg-gray-900 border-gray-700 rounded-md text-[13px] focus:ring-2 focus:ring-[var(--oe-primary)]">
                          <SelectValue placeholder={t('right.chooseProject')} />
                        </SelectTrigger>
                        <SelectContent className="text-[13px]">
                          {projects.map((p) => (
                            <SelectItem key={p.name} value={p.name}>
                              {p.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label htmlFor="pop-size" className="text-[11px] text-gray-400 mb-1.5">{t('right.populationSize')}</Label>
                        <Input
                          id="pop-size"
                          type="number"
                          min={1}
                          value={params.populationSize}
                          onChange={(e) => setParams({ ...params, populationSize: e.target.value })}
                          className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                        />
                      </div>
                      <div>
                        <Label htmlFor="mutation" className="text-[11px] text-gray-400 mb-1.5">{t('right.mutationRate')}</Label>
                        <Input
                          id="mutation"
                          type="number"
                          step="0.01"
                          value={params.mutationRate}
                          onChange={(e) => setParams({ ...params, mutationRate: e.target.value })}
                          className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label htmlFor="num-islands" className="text-[11px] text-gray-400 mb-1.5">{t('right.numIslands')}</Label>
                        <Input
                          id="num-islands"
                          type="number"
                          min={1}
                          value={params.numIslands}
                          onChange={(e) => setParams({ ...params, numIslands: e.target.value })}
                          className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                        />
                        {t('right.numIslandsHelp') && (
                          <div className="mt-1 text-[10px] text-slate-500 leading-snug">
                            {t('right.numIslandsHelp')}
                          </div>
                        )}
                      </div>
                      <div>
                        <Label htmlFor="evaluator-timeout" className="text-[11px] text-gray-400 mb-1.5">
                          {t('right.evaluatorTimeout')}
                        </Label>
                        <Input
                          id="evaluator-timeout"
                          type="number"
                          min={1}
                          value={params.evaluatorTimeout}
                          onChange={(e) => setParams({ ...params, evaluatorTimeout: e.target.value })}
                          className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                        />
                      </div>
                    </div>

                    <details
                      className="rounded-md border border-white/10 bg-slate-900/35 px-2.5 py-2"
                      open={advancedOpen}
                      onToggle={(e) => setAdvancedOpen((e.currentTarget as HTMLDetailsElement).open)}
                    >
                      <summary className="cursor-pointer select-none text-[11px] font-semibold text-slate-300">
                        {t('right.advancedParams')}
                      </summary>
                      <div className="mt-2.5 space-y-2">
                        <div>
                          <Label htmlFor="archive-size" className="text-[11px] text-gray-400 mb-1.5">
                            {t('right.archiveSize')}
                          </Label>
                          <Input
                            id="archive-size"
                            type="number"
                            min={1}
                            value={params.archiveSize}
                            onChange={(e) => setParams({ ...params, archiveSize: e.target.value })}
                            className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <Label htmlFor="elite-selection-ratio" className="text-[11px] text-gray-400 mb-1.5">
                              {t('right.eliteSelectionRatio')}
                            </Label>
                            <Input
                              id="elite-selection-ratio"
                              type="number"
                              min={0}
                              max={1}
                              step="0.01"
                              value={params.eliteSelectionRatio}
                              onChange={(e) => setParams({ ...params, eliteSelectionRatio: e.target.value })}
                              className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                            />
                          </div>
                          <div>
                            <Label htmlFor="exploitation-ratio" className="text-[11px] text-gray-400 mb-1.5">
                              {t('right.exploitationRatio')}
                            </Label>
                            <Input
                              id="exploitation-ratio"
                              type="number"
                              min={0}
                              max={1}
                              step="0.01"
                              value={params.exploitationRatio}
                              onChange={(e) => setParams({ ...params, exploitationRatio: e.target.value })}
                              className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                            />
                          </div>
                        </div>
                        <div>
                          <Label htmlFor="similarity-threshold" className="text-[11px] text-gray-400 mb-1.5">
                            {t('right.similarityThreshold')}
                          </Label>
                          <Input
                            id="similarity-threshold"
                            type="number"
                            min={0}
                            max={1}
                            step="0.01"
                            value={params.similarityThreshold}
                            onChange={(e) => setParams({ ...params, similarityThreshold: e.target.value })}
                            className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                          />
                        </div>
                      </div>
                    </details>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label htmlFor="parallel-evaluations" className="text-[11px] text-gray-400 mb-1.5">
                          {t('right.parallelEvaluations')}
                        </Label>
                        <Input
                          id="parallel-evaluations"
                          type="number"
                          min={1}
                          value={params.parallelEvaluations}
                          onChange={(e) => setParams({ ...params, parallelEvaluations: e.target.value })}
                          className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                        />
                      </div>
                      <div>
                        <Label htmlFor="diff-based-evolution" className="text-[11px] text-gray-400 mb-1.5">
                          {t('right.diffBasedEvolution')}
                        </Label>
                        <Select
                          value={params.diffBasedEvolution ? 'true' : 'false'}
                          onValueChange={(value) =>
                            setParams({ ...params, diffBasedEvolution: value === 'true' })
                          }
                        >
                          <SelectTrigger id="diff-based-evolution" className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="text-[13px]">
                            <SelectItem value="true">{t('right.enabled')}</SelectItem>
                            <SelectItem value="false">{t('right.disabled')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                      <Label htmlFor="generations" className="text-[11px] text-gray-400 mb-1.5">{t('right.targetGenerations')}</Label>
                      <Input
                        id="generations"
                        type="number"
                        value={params.generations}
                        onChange={(e) => setParams({ ...params, generations: e.target.value })}
                        className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                      />
                      {t('right.generationsHelp') && (
                        <div className="mt-1 text-[10px] text-slate-500 leading-snug">{t('right.generationsHelp')}</div>
                      )}
                      </div>
                      <div>
                        <Label htmlFor="checkpoint-interval" className="text-[11px] text-gray-400 mb-1.5">
                          {t('right.checkpointInterval')}
                        </Label>
                        <Input
                          id="checkpoint-interval"
                          type="number"
                          min={1}
                          value={params.checkpointInterval}
                          onChange={(e) => setParams({ ...params, checkpointInterval: e.target.value })}
                          className="h-8 bg-gray-900 border-gray-700 rounded-md text-sm focus:ring-2 focus:ring-[var(--oe-primary)] font-mono"
                        />
                        {t('right.checkpointIntervalHelp') && (
                          <div className="mt-1 text-[10px] text-slate-500 leading-snug">
                            {t('right.checkpointIntervalHelp')}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <Button
                        onClick={handleStart}
                        disabled={isRunning || !params.evolutionObject}
                        className="group relative overflow-hidden border border-white/20 text-white gap-2 h-9 text-[11px] font-bold rounded-md transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110 hover:shadow-[0_10px_20px_rgba(15,118,110,0.3)] active:translate-y-0 active:scale-[0.99] disabled:translate-y-0 disabled:scale-100 disabled:opacity-50 disabled:shadow-none"
                        style={{
                          backgroundImage: 'linear-gradient(92deg, var(--oe-primary) 0%, color-mix(in srgb, var(--oe-primary) 62%, var(--oe-accent)) 54%, var(--oe-accent) 100%)',
                          boxShadow: '0 8px 18px color-mix(in srgb, var(--oe-primary) 24%, transparent)',
                        }}
                      >
                        <Play className="size-3.5" />
                        {t('right.startEvolution')}
                      </Button>
                      <Button
                        onClick={handleStop}
                        disabled={!isRunning}
                        className="h-9 gap-2 text-[11px] font-semibold border transition-all duration-200 bg-rose-500/85 border-rose-300/35 text-white hover:bg-rose-500 hover:-translate-y-0.5 hover:shadow-[0_10px_20px_rgba(244,63,94,0.3)] active:translate-y-0 active:scale-[0.99] disabled:translate-y-0 disabled:scale-100 disabled:shadow-none disabled:border-white/20 disabled:bg-transparent disabled:text-slate-500"
                      >
                        <Square className="size-3.5" />
                        {t('right.stop')}
                      </Button>
                    </div>
                    <div className="rounded-lg border border-cyan-400/25 bg-cyan-500/5 px-3 py-2.5 space-y-2">
                      <div className="text-[11px] font-semibold text-cyan-200">{t('right.visualCardTitle')}</div>
                      <div>
                        <Label htmlFor="visual-target-run" className="text-[11px] text-gray-400 mb-1.5">
                          {t('right.visualTargetLabel')}
                        </Label>
                        <Select
                          value={visualizationTargetKey}
                          onValueChange={(value) => {
                            const [projectName, runId] = value.split('::');
                            if (!projectName || !runId) return;
                            setVisualizationTarget({ projectName, runId });
                          }}
                          disabled={outputRuns.length === 0}
                        >
                          <SelectTrigger id="visual-target-run" className="h-7 bg-gray-900 border-gray-700 rounded-md text-[12px] focus:ring-2 focus:ring-[var(--oe-primary)]">
                            <SelectValue placeholder={t('right.visualTargetPlaceholder')} />
                          </SelectTrigger>
                          <SelectContent
                            className="text-[12px]"
                            side="top"
                            sideOffset={4}
                            avoidCollisions={false}
                          >
                            {outputRuns.map((r) => (
                              <SelectItem key={buildRunKey(r.projectName, r.runId)} value={buildRunKey(r.projectName, r.runId)}>
                                {r.projectName} / {toMinuteRunId(r.runId)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="text-[10px] leading-5 text-slate-400 break-all">
                        {effectiveVisualizationTarget
                          ? t('right.visualTargetRun', {
                              project: effectiveVisualizationTarget.projectName,
                              run: toMinuteRunId(effectiveVisualizationTarget.runId),
                            })
                          : t('right.visualNoRun')}
                      </div>
                      <div className="text-[10px] leading-5 text-slate-500 break-all">
                        {visualizationStatus?.running && visualizationStatus.url
                          ? t('right.visualServiceRunning', { url: visualizationStatus.url })
                          : t('right.visualServiceNotRunning')}
                      </div>
                      {visualizationError && (
                        <div className="text-[10px] leading-5 text-rose-300 break-all">
                          {visualizationError}
                        </div>
                      )}
                      <Button
                        onClick={() => handleStartVisualization(false)}
                        disabled={!effectiveVisualizationTarget || visualizationLoading}
                        className="h-8 w-full text-[11px] font-semibold"
                      >
                        {visualizationLoading ? t('right.visualStarting') : t('right.visualStartOpen')}
                      </Button>
                    </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                role="separator"
                aria-orientation="vertical"
                className={`hidden lg:block cursor-col-resize rounded-sm transition-colors ${
                  isMonitorResizing ? 'bg-emerald-400/70' : 'bg-white/20 hover:bg-emerald-400/50'
                }`}
                onMouseDown={() => setIsMonitorResizing(true)}
                title={t('app.resizeSeparator')}
              />

              <div className="min-w-0 min-h-[360px] bg-[#111827]/90 border border-white/10 rounded-xl overflow-hidden shadow-[0_12px_34px_rgba(2,6,23,0.35)] flex flex-col">
              <div className="bg-[#1e293b]/70 border-b border-white/10 px-4 py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`size-2 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-gray-600'}`}></div>
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-[0.16em]">{t('right.liveMonitor')}</span>
                </div>
                {isRunning && (
                  <span className="text-xs font-mono" style={{ color: 'var(--oe-primary-light)' }}>{t('right.processing')}</span>
                )}
              </div>
              
              <div ref={scrollRef} className="flex-1 overflow-y-auto font-mono text-xs oe-scrollbar">
                  {rawLogs.length === 0 && !isRunning && (
                    <div className="text-slate-500 text-center py-12">
                      {t('right.monitorEmpty')}
                    </div>
                  )}
                  {rawLogs.map((log, idx) => {
                    const channel = getEffectiveChannel(log);
                    const markdownHtml = channel === 'agent_response'
                      ? renderMarkdownHtml(String(log.rawText || log.message || ''))
                      : '';
                    return (
                      <motion.div
                        key={`raw-main-${log.dedupeKey || `${log.timestamp}-${idx}`}`}
                        initial={{ opacity: 0, x: -12 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.2 }}
                        className="border-b border-slate-900/80 px-4 py-2 bg-[#0b1220]/80"
                      >
                        <div
                          className="text-[11px] leading-5 text-slate-300 grid items-start gap-x-2"
                          style={{ gridTemplateColumns: '20px 128px minmax(0, 1fr)' }}
                        >
                          <span title={channelTooltip(log)}>
                            {monitorIcon(channel)}
                          </span>
                          <span className="text-slate-500 shrink-0 tabular-nums">{log.timestamp}</span>
                          {channel === 'agent_response' ? (
                            <div
                              className="preview-renderer min-w-0 text-[11px] leading-5 text-slate-200 break-words"
                              dangerouslySetInnerHTML={{ __html: markdownHtml }}
                            />
                          ) : (
                            <span className="min-w-0 break-all">{log.rawText}</span>
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
              </div>
              </div>
            </div>

          </TabsContent>

          <TabsContent value="dashboard" className="flex-1 m-0 p-6 overflow-y-auto">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-400">{t('right.dashboardTitle')}</div>
                  <div className="mt-1 text-sm text-slate-500">{t('right.dashboardSubtitle')}</div>
                </div>
                <div className="w-[240px]">
                  <Select value={dashboardProject} onValueChange={setDashboardProject}>
                    <SelectTrigger className="bg-gray-900 border-gray-700 rounded-md focus:ring-2 focus:ring-[var(--oe-primary)]">
                      <SelectValue placeholder={t('right.selectProject')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('right.allProjects')}</SelectItem>
                      {projectOptions.map((name) => (
                        <SelectItem key={name} value={name}>
                          {name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="rounded-lg border border-white/10 bg-[#111827]/80 px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{t('right.latestMetric')}</div>
                  <div className="mt-2 text-slate-200 font-mono text-sm break-all">
                    {latestMetric ? `${latestMetric.metricName} = ${latestMetric.metricValue.toFixed(6)}` : t('right.noNumericMetrics')}
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-[#111827]/80 px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{t('right.bestRecent')}</div>
                  <div className="mt-2 text-emerald-300 font-mono text-sm break-all">
                    {bestMetric ? `${bestMetric.metricName} = ${bestMetric.metricValue.toFixed(6)}` : t('right.noNumericMetrics')}
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-[#111827]/80 px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{t('right.avgDelta')}</div>
                  <div className="mt-2 text-slate-200 font-mono text-sm">
                    {avgMetric != null ? avgMetric.toFixed(6) : 'N/A'}
                    <span className="text-slate-500"> / </span>
                    <span className={improvement != null ? (improvement >= 0 ? 'text-emerald-300' : 'text-rose-300') : 'text-slate-500'}>
                      {improvement != null ? `${improvement >= 0 ? '+' : ''}${improvement.toFixed(6)}` : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                  单次 Run 内趋势
                </div>
                <div className="h-[260px] px-3 py-2">
                  {trendData.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-sm text-slate-500">
                      {t('right.noTrendData')}
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="iteration" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#0f172a',
                            border: '1px solid rgba(148,163,184,0.25)',
                            color: '#e2e8f0',
                            fontSize: 12,
                          }}
                        />
                        <Legend />
                        {metricNames.slice(0, 6).map((name, idx) => (
                          <Line
                            key={name}
                            type="monotone"
                            dataKey={name}
                            stroke={idx % 2 === 0 ? '#34d399' : '#38bdf8'}
                            strokeWidth={name === effectiveFitnessKey ? 2.4 : 1.4}
                            dot={false}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                  多 Run 对比（最近 {latestRuns.length} 次）
                </div>
                <div className="h-[260px] px-3 py-2">
                  {multiRunCompareData.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-sm text-slate-500">
                      {t('right.noRunData')}
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={multiRunCompareData} margin={{ top: 10, right: 20, left: 0, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="runId" stroke="#94a3b8" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={48} />
                        <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <Tooltip
                          formatter={(value: number, _name: string, payload: any) => [
                            typeof value === 'number' ? value.toFixed(6) : value,
                            payload?.payload?.metricName || effectiveFitnessKey,
                          ]}
                          labelFormatter={(_label, payload) => {
                            const p = payload?.[0]?.payload;
                            if (!p) return '';
                            return `${p.projectName} / ${p.runId} (${p.runTime})`;
                          }}
                          contentStyle={{
                            backgroundColor: '#0f172a',
                            border: '1px solid rgba(148,163,184,0.25)',
                            color: '#e2e8f0',
                            fontSize: 12,
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="metricValue"
                          stroke="#a78bfa"
                          strokeWidth={2.2}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                  {t('right.recentRuns')}
                </div>
                <div className="max-h-[320px] overflow-y-auto">
                  {latestRuns.length === 0 ? (
                    <div className="px-4 py-8 text-center text-slate-500 text-sm">{t('right.noRunData')}</div>
                  ) : (
                    latestRuns.map((r) => {
                      const metricEntries = Object.entries(r.allMetrics || {});
                      const fallbackMetric = pickPrimaryMetric(r);
                      return (
                        <div key={`${r.projectName}-${r.runId}`} className="border-b border-slate-800/80 px-4 py-3 last:border-b-0">
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                            <span className="text-cyan-300 font-semibold">{r.projectName}</span>
                            <span className="text-slate-600">/</span>
                            <span className="text-violet-300 font-mono">{toMinuteRunId(r.runId)}</span>
                            <span className="text-slate-600">·</span>
                            <span className="text-slate-400">{displayRunTime(r)}</span>
                          </div>
                          <div className="mt-1 text-xs font-mono flex flex-wrap items-center gap-x-3 gap-y-1">
                            {metricEntries.length > 0 ? (
                              metricEntries.map(([k, v]) => (
                                <span key={`${r.runId}-${k}`} className={k === (r.fitnessKey || effectiveFitnessKey) ? 'text-emerald-300' : 'text-slate-400'}>
                                  {k}={formatMetricValue(v, 6)}
                                </span>
                              ))
                            ) : (
                              <span className={fallbackMetric.value != null ? 'text-emerald-300' : 'text-slate-500'}>
                                {fallbackMetric.name}={fallbackMetric.value != null ? fallbackMetric.value.toFixed(6) : t('right.noNumericMetrics')}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="results" className="flex-1 m-0 p-6 overflow-y-auto">
            <div className="space-y-4">
              <div className="rounded-lg border border-white/10 bg-[#111827]/80 p-4 space-y-3">
                <div className="text-xs uppercase tracking-[0.16em] text-slate-400">{t('right.llmAnalysis')}</div>
                <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_auto] gap-3">
                  <Select value={analysisRunKey} onValueChange={setAnalysisRunKey}>
                    <SelectTrigger className="bg-gray-900 border-gray-700 rounded-md focus:ring-2 focus:ring-[var(--oe-primary)]">
                      <SelectValue placeholder={t('right.selectRunToAnalyze')} />
                    </SelectTrigger>
                    <SelectContent>
                      {outputRuns.map((r) => (
                        <SelectItem key={buildRunKey(r.projectName, r.runId)} value={buildRunKey(r.projectName, r.runId)}>
                          {r.projectName} / {toMinuteRunId(r.runId)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder={t('right.analysisFocusPlaceholder')}
                    value={analysisFocus}
                    onChange={(e) => setAnalysisFocus(e.target.value)}
                    className="bg-gray-900 border-gray-700 rounded-md focus:ring-2 focus:ring-[var(--oe-primary)]"
                  />
                  <Button
                    onClick={handleAnalyzeRun}
                    disabled={!selectedAnalysisRun || analysisLoading}
                    className="min-w-[140px] font-semibold"
                  >
                    {analysisLoading ? t('right.analyzing') : t('right.analyze')}
                  </Button>
                </div>
              </div>

              {analysisError && (
                <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200 break-all">
                  {analysisError}
                </div>
              )}

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 flex items-center justify-between gap-2">
                  <div className="text-xs uppercase tracking-[0.14em] text-slate-400">{t('right.analysisOutput')}</div>
                  <div className="flex items-center gap-2">
                    {analysisMeta && (
                      <div className="text-[11px] text-slate-500 break-all">
                        {analysisMeta.model} · {analysisMeta.projectName} / {toMinuteRunId(analysisMeta.runId)}
                      </div>
                    )}
                    {(analysisText || analysisMeta) && (
                      <button
                        className="oe-ghost-btn rounded px-2 py-1 text-[11px]"
                        onClick={() => {
                          setAnalysisText('');
                          setAnalysisMeta(null);
                        }}
                        title={t('right.closeAnalysisOutput')}
                      >
                        {t('right.close')}
                      </button>
                    )}
                  </div>
                </div>
                <div className="max-h-[420px] overflow-auto px-4 py-3">
                  {analysisText ? (
                    <pre className="whitespace-pre-wrap text-sm leading-6 text-slate-200 font-mono">{analysisText}</pre>
                  ) : (
                    <div className="text-slate-500 text-sm py-8 text-center">
                      {t('right.analysisEmptyHint')}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                  {t('right.artifacts')}
                </div>
                <div className="max-h-[320px] overflow-auto px-4 py-3 space-y-3">
                  {!artifactData || (Object.keys(artifactData.artifacts).length === 0 && artifactData.artifactFiles.length === 0) ? (
                    <div className="text-slate-500 text-sm">{t('right.noArtifacts')}</div>
                  ) : (
                    <>
                      {artifactData.programId && (
                        <div className="text-[11px] text-slate-500 font-mono">
                          programId: <span className="text-slate-300">{artifactData.programId}</span>
                        </div>
                      )}
                      {Object.keys(artifactData.artifacts).length > 0 && (
                        <pre className="text-[11px] leading-5 text-slate-200 bg-[#0f172a] border border-white/10 rounded p-2 overflow-auto">
                          {JSON.stringify(artifactData.artifacts, null, 2)}
                        </pre>
                      )}
                      {artifactData.artifactFiles.length > 0 && (
                        <div className="space-y-2">
                          {artifactData.artifactFiles.map((f) => (
                            <div key={f.name} className="border border-white/10 rounded p-2 bg-[#0b1220]/70">
                              <div className="text-[11px] font-mono text-slate-300 break-all">{f.name}</div>
                              <div className="text-[10px] text-slate-500">{f.size} bytes</div>
                              {f.isText && (
                                <pre className="mt-1 text-[10px] leading-5 text-slate-200 max-h-32 overflow-auto whitespace-pre-wrap">
                                  {String(f.content || '')}
                                </pre>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                  {t('right.bestProgramDiff')}
                </div>
                <div className="max-h-[320px] overflow-auto px-4 py-3">
                  <pre className="whitespace-pre-wrap text-[11px] leading-5 text-slate-200 font-mono">
                    {bestProgramDiff || t('right.noDiffData')}
                  </pre>
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <div className="border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                  {t('right.analysisHistory')}
                </div>
                <div className="max-h-[260px] overflow-auto">
                  {analysisHistory.length === 0 ? (
                    <div className="px-4 py-6 text-sm text-slate-500 text-center">{t('right.noAnalysisHistory')}</div>
                  ) : (
                    analysisHistory.map((item) => (
                      <div key={item.id} className="border-b border-slate-800/80 px-4 py-3 last:border-b-0">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-xs text-slate-300 font-mono break-all">{item.id}</div>
                            <div className="mt-1 text-[11px] text-slate-500 break-all">
                              {item.createdAt} · {item.model}
                            </div>
                            {item.focus && (
                              <div className="mt-1 text-[11px] text-cyan-300 break-all">focus: {item.focus}</div>
                            )}
                            {item.preview && (
                              <div className="mt-1 text-[11px] text-slate-400 break-all">{item.preview}</div>
                            )}
                          </div>
                          <div className="shrink-0 flex items-center gap-2">
                            <button
                              className="rounded border border-cyan-400/30 px-2 py-1 text-[11px] text-cyan-300 hover:bg-cyan-500/10"
                              onClick={() => handleViewAnalysis(item).catch((e) => alert(e.message))}
                            >
                              {t('right.view')}
                            </button>
                            <a
                              href={item.downloadUrl}
                              className="rounded border border-white/15 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/5"
                            >
                              {t('right.download')}
                            </a>
                            <button
                              className="rounded border border-rose-400/30 px-2 py-1 text-[11px] text-rose-300 hover:bg-rose-500/10"
                              onClick={() => handleDeleteAnalysis(item).catch((e) => alert(e.message))}
                            >
                              {t('right.delete')}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="config" className="flex-1 m-0 p-6 overflow-y-auto">
            <div className="space-y-4">
              <div className="rounded-lg border border-white/10 bg-[#111827]/80 p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.16em] text-slate-400">{t('right.configEditor')}</div>
                    <div className="mt-1 text-sm text-slate-500 break-all">
                      {t('right.project')}: {params.evolutionObject || t('right.noProjectSelected')}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      disabled={!params.evolutionObject || configLoading}
                      onClick={() => loadProjectConfig(params.evolutionObject).catch((e) => console.error(e))}
                    >
                      {configLoading ? t('right.loading') : t('right.reload')}
                    </Button>
                    <Button
                      disabled={!params.evolutionObject || !configPath || configSaving || configLoading}
                      onClick={handleSaveConfig}
                    >
                      {configSaving ? t('right.saving') : t('right.save')}
                    </Button>
                  </div>
                </div>

                <div className="text-xs text-slate-500 break-all">
                  {t('right.file')}: {configPath || t('right.noConfigFound')}
                </div>

                {configError && (
                  <div className="rounded border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200 break-all">
                    {configError}
                  </div>
                )}
                {configMessage && (
                  <div className="rounded border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
                    {configMessage}
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-white/10 bg-[#111827]/80 overflow-hidden">
                <textarea
                  className="w-full min-h-[620px] bg-transparent px-4 py-3 text-sm leading-6 text-slate-200 font-mono outline-none resize-y"
                  spellCheck={false}
                  value={configText}
                  onChange={(e) => setConfigText(e.target.value)}
                  placeholder={t('right.configPlaceholder')}
                  disabled={!params.evolutionObject || !configPath || configLoading}
                />
              </div>
            </div>
          </TabsContent>
          <TabsContent value="scenario" className="flex-1 m-0 p-0 overflow-y-auto">
            <ScenarioBuilderTab
              persistedSessionId={scenarioSessionId}
              onSessionIdChange={setScenarioSessionId}
              onProjectCreated={() => {
                loadProjects().catch((e) => console.error(e));
                window.dispatchEvent(new Event('evolve-projects-updated'));
              }}
            />
          </TabsContent>
        </div>
      </Tabs>

      <Dialog open={visualPromptOpen} onOpenChange={setVisualPromptOpen}>
        <DialogContent className="bg-[#0f172a] border-white/15 text-slate-100">
          <DialogHeader>
            <DialogTitle>{t('right.visualPromptTitle')}</DialogTitle>
            <DialogDescription className="text-slate-300">
              {t('right.visualPromptDesc')}
            </DialogDescription>
          </DialogHeader>
          {effectiveVisualizationTarget && (
            <div className="rounded border border-white/10 bg-[#111827]/80 px-3 py-2 text-xs text-slate-300 break-all">
              {t('right.visualTargetRun', {
                project: effectiveVisualizationTarget.projectName,
                run: toMinuteRunId(effectiveVisualizationTarget.runId),
              })}
            </div>
          )}
          {visualizationError && (
            <div className="rounded border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200 break-all">
              {visualizationError}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setVisualPromptOpen(false)}>
              {t('right.visualLater')}
            </Button>
            <Button
              onClick={() => handleStartVisualization(true)}
              disabled={!effectiveVisualizationTarget || visualizationLoading}
            >
              {visualizationLoading ? t('right.visualStarting') : t('right.visualConfirmStart')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}