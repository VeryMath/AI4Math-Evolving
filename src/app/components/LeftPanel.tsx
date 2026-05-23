import { type ChangeEvent, useEffect, useRef, useState } from 'react';
import {
  ChevronRight,
  ChevronDown,
  Upload,
  FolderOpen,
  FileCode2,
  Settings,
  FileText,
  Terminal,
  Folder,
  File,
  TrendingUp,
  BarChart3,
  Eye,
  Download,
  Trash2,
  Search,
  Copy,
} from 'lucide-react';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import * as Collapsible from '@radix-ui/react-collapsible';
import { useTheme } from '../contexts/ThemeContext';
import { useLocale } from '../contexts/LocaleContext';

interface FileNode {
  name: string;
  type: 'file' | 'folder';
  extension?: string;
  children?: FileNode[];
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

interface FlatTreeEntry {
  path: string;
  isDir: boolean;
  size: number;
}

interface PreviewState {
  title: string;
  path: string;
  content: string;
  truncated: boolean;
  downloadUrl: string;
  sourceType: 'project' | 'output';
  projectName: string;
  runId?: string;
}

function runKey(projectName: string, runId: string): string {
  return `${projectName}-${runId}`;
}

function sameOutputRuns(a: OutputRunRow[], b: OutputRunRow[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  const mapB = new Map<string, OutputRunRow>();
  for (const r of b) {
    mapB.set(`${r.projectName}::${r.runId}`, r);
  }
  for (const x of a) {
    const y = mapB.get(`${x.projectName}::${x.runId}`); 
    if (!y) return false;
    if (
      x.projectName !== y.projectName ||
      x.runId !== y.runId ||
      x.bestCombined !== y.bestCombined ||
      x.primaryMetricName !== y.primaryMetricName ||
      x.primaryMetricValue !== y.primaryMetricValue ||
      x.fitnessKey !== y.fitnessKey ||
      JSON.stringify(x.allMetrics || {}) !== JSON.stringify(y.allMetrics || {})
    ) {
      return false;
    }
  }
  return true;
}

function sameTreeEntries(a: FileNode[], b: FileNode[]): boolean {
  if (a === b) return true;
  return JSON.stringify(a) === JSON.stringify(b);
}

function formatShortTimestamp(unixSeconds: number): string {
  const d = new Date(unixSeconds * 1000);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${mm}-${dd} ${hh}:${mi}`;
}

function runIdToShortTimestamp(runId: string): string | null {
  const m = /^run_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/.exec(runId);
  if (!m) return null;
  const [, _yyyy, mm, dd, hh, mi] = m;
  return `${mm}-${dd} ${hh}:${mi}`;
}

function displayRunTimestamp(run: OutputRunRow): string {
  return runIdToShortTimestamp(run.runId) || formatShortTimestamp(run.mtime);
}

function formatRunLabelToMinute(runId: string): string {
  const m = /^run_(\d{8})_(\d{4})(?:\d{2})?(?:_.+)?$/.exec(runId);
  if (!m) return runId;
  return `run_${m[1]}_${m[2]}`;
}

function formatPrimaryMetric(r: OutputRunRow, noMetricLabel: string): { label: string; value: string; ok: boolean } {
  const fitnessName = (r.fitnessKey || '').trim();
  if (fitnessName && r.allMetrics && typeof r.allMetrics[fitnessName] === 'number' && Number.isFinite(r.allMetrics[fitnessName])) {
    return { label: fitnessName, value: r.allMetrics[fitnessName].toFixed(6), ok: true };
  }
  const name = (r.primaryMetricName || '').trim();
  const value = r.primaryMetricValue;
  if (name && typeof value === 'number' && Number.isFinite(value)) {
    return { label: name, value: value.toFixed(6), ok: true };
  }
  if (typeof r.bestCombined === 'number' && Number.isFinite(r.bestCombined)) {
    return { label: fitnessName || name || 'score', value: r.bestCombined.toFixed(6), ok: true };
  }
  return { label: 'metric', value: noMetricLabel, ok: false };
}

function formatAllMetricsTooltip(r: OutputRunRow): string {
  const entries = Object.entries(r.allMetrics || {});
  if (entries.length === 0) return '';
  return entries
    .map(([k, v]) => `${k} = ${Number.isFinite(v) ? v.toFixed(6) : String(v)}`)
    .join('\n');
}

function getFileIcon(extension?: string, isDir?: boolean) {
  if (isDir) return <Folder className="size-4 text-amber-300" />;
  switch (extension) {
    case 'py':
      return <FileCode2 className="size-4 text-sky-300" />;
    case 'yaml':
      return <Settings className="size-4 text-violet-300" />;
    case 'md':
      return <FileText className="size-4 text-slate-300" />;
    case 'sh':
      return <Terminal className="size-4 text-emerald-300" />;
    case 'evolve':
      return <TrendingUp className="size-4 text-cyan-300" />;
    case 'png':
      return <BarChart3 className="size-4 text-pink-300" />;
    default:
      return <File className="size-4 text-slate-300" />;
  }
}

function buildTree(entries: FlatTreeEntry[]): FileNode[] {
  const root: FileNode = { name: '__root__', type: 'folder', children: [] };
  for (const entry of entries) {
    const parts = entry.path.split('/').filter(Boolean);
    let cursor = root;
    parts.forEach((part, idx) => {
      const isLast = idx === parts.length - 1;
      if (!cursor.children) cursor.children = [];
      let child = cursor.children.find((c) => c.name === part && c.type === (isLast && !entry.isDir ? 'file' : 'folder'));
      if (!child) {
        child = {
          name: part,
          type: isLast && !entry.isDir ? 'file' : 'folder',
          extension: isLast && !entry.isDir ? part.split('.').pop() : undefined,
          children: isLast && !entry.isDir ? undefined : [],
        };
        cursor.children.push(child);
      }
      cursor = child;
    });
  }
  return (root.children || []).sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

function FileTreeItem({
  node,
  depth,
  fullPath,
  onPreview,
  onDownload,
  alwaysShowActions = false,
}: {
  node: FileNode;
  depth: number;
  fullPath: string;
  onPreview: (path: string) => void;
  onDownload: (path: string) => void;
  alwaysShowActions?: boolean;
}) {
  const { t } = useLocale();
  const [isOpen, setIsOpen] = useState(false);
  const currentPath = fullPath ? `${fullPath}/${node.name}` : node.name;
  const indent = `${12 + depth * 14}px`;

  if (node.type === 'file') {
    return (
      <div
        className="group flex items-center justify-between gap-2 py-1.5 pr-2 hover:bg-[#243244]/65 cursor-pointer rounded text-sm"
        style={{ paddingLeft: indent }}
      >
        <div className="min-w-0 flex items-center gap-2 overflow-hidden">
          {getFileIcon(node.extension)}
          <div className="max-w-full text-slate-300 font-mono text-xs break-all" title={currentPath}>
            {node.name}
          </div>
        </div>
        <div className={`flex items-center gap-1 transition-opacity ${alwaysShowActions ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
          <button
            className="p-1 rounded hover:bg-slate-700/70"
            onClick={(e) => {
              e.stopPropagation();
              onPreview(currentPath);
            }}
            title={t('left.preview')}
          >
            <Eye className="size-3 text-slate-300" />
          </button>
          <button
            className="p-1 rounded hover:bg-slate-700/70"
            onClick={(e) => {
              e.stopPropagation();
              onDownload(currentPath);
            }}
            title={t('left.download')}
          >
            <Download className="size-3 text-slate-300" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <Collapsible.Root open={isOpen} onOpenChange={setIsOpen}>
      <Collapsible.Trigger
        className="flex items-center gap-2 py-1.5 hover:bg-[#243244]/65 cursor-pointer rounded text-sm w-full"
        style={{ paddingLeft: indent }}
      >
        {isOpen ? <ChevronDown className="size-3 text-gray-400" /> : <ChevronRight className="size-3 text-gray-400" />}
        {getFileIcon(undefined, true)}
        <span className="text-slate-300 font-mono text-xs">{node.name}</span>
      </Collapsible.Trigger>
      <Collapsible.Content>
        {node.children?.map((child, idx) => (
          <FileTreeItem
            key={idx}
            node={child}
            depth={depth + 1}
            fullPath={currentPath}
            onPreview={onPreview}
            onDownload={onDownload}
            alwaysShowActions={alwaysShowActions}
          />
        ))}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}

function ProjectFolder({
  project,
  onLoadTree,
  onPreview,
  onDownload,
  onDeleteProject,
}: {
  project: { name: string; files: FileNode[] };
  onLoadTree: (name: string) => void;
  onPreview: (projectName: string, path: string) => void;
  onDownload: (projectName: string, path: string) => void;
  onDeleteProject: (projectName: string) => void;
}) {
  const { t } = useLocale();
  const [isOpen, setIsOpen] = useState(false);
  const handleOpenChange = (nextOpen: boolean) => {
    setIsOpen(nextOpen);
    if (nextOpen) onLoadTree(project.name);
  };

  return (
    <Collapsible.Root open={isOpen} onOpenChange={handleOpenChange} className="mb-1">
      <div className="flex items-center gap-2 px-3 py-2 hover:bg-[#243244]/70 rounded w-full">
        <Collapsible.Trigger className="flex min-w-0 flex-1 items-center gap-2 text-left cursor-pointer">
          {isOpen ? <ChevronDown className="size-4 text-gray-400" /> : <ChevronRight className="size-4 text-gray-400" />}
          <FolderOpen className="size-4 text-cyan-300" />
          <span className="truncate text-slate-200 font-mono text-sm">{project.name}</span>
        </Collapsible.Trigger>
        <button
          className="rounded border border-rose-400/30 p-1 text-rose-300 hover:bg-rose-500/10"
          title={t('left.deleteProject')}
          onClick={(e) => {
            e.stopPropagation();
            onDeleteProject(project.name);
          }}
        >
          <Trash2 className="size-3" />
        </button>
      </div>
      <Collapsible.Content className="mt-1">
        {project.files.map((file, idx) => (
          <FileTreeItem
            key={idx}
            node={file}
            depth={1}
            fullPath=""
            onPreview={(path) => onPreview(project.name, path)}
            onDownload={(path) => onDownload(project.name, path)}
          />
        ))}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}

export function LeftPanel({ widthPercent = 27 }: { widthPercent?: number }) {
  const { colors } = useTheme();
  const { t } = useLocale();
  const [projects, setProjects] = useState<Array<{ name: string; files: FileNode[] }>>([]);
  const [outputRuns, setOutputRuns] = useState<OutputRunRow[]>([]);
  const [projectTrees, setProjectTrees] = useState<Record<string, FileNode[]>>({});
  const [outputTrees, setOutputTrees] = useState<Record<string, FileNode[]>>({});
  const [outputTreeLoading, setOutputTreeLoading] = useState<Record<string, boolean>>({});
  const [outputTreeError, setOutputTreeError] = useState<Record<string, string>>({});
  const [openRunKey, setOpenRunKey] = useState<string | null>(null);
  const [didAutoOpenRun, setDidAutoOpenRun] = useState(false);
  const [outputFilter, setOutputFilter] = useState('');
  const [selectedRunKeys, setSelectedRunKeys] = useState<Set<string>>(new Set());
  const [batchBusy, setBatchBusy] = useState(false);
  const [isRunActive, setIsRunActive] = useState(false);
  const [outputsGuideTip, setOutputsGuideTip] = useState<{ x: number; y: number } | null>(null);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const openRunKeyRef = useRef<string | null>(null);
  const outputRunsRef = useRef<OutputRunRow[]>([]);

  const emitPreview = (payload: PreviewState) => {
    window.dispatchEvent(new CustomEvent('evolve-file-preview', { detail: payload }));
  };

  const loadProjects = async () => {
    const res = await fetch('/api/projects');
    if (!res.ok) throw new Error(`GET /api/projects failed: ${res.status}`);
    const data = await res.json();
    setProjects(data.projects || []);
  };

  const loadOutputs = async () => {
    const res = await fetch('/api/outputs');
    if (!res.ok) throw new Error(`GET /api/outputs failed: ${res.status}`);
    const data = await res.json();
    const next = (data.runs || []) as OutputRunRow[];
    setOutputRuns((prev) => (sameOutputRuns(prev, next) ? prev : next));
  };

  const fetchProjectTree = async (projectName: string) => {
    if (projectTrees[projectName]) return;
    const res = await fetch(`/api/projects/${encodeURIComponent(projectName)}/tree?maxDepth=6`);
    if (!res.ok) throw new Error(`GET project tree failed: ${res.status}`);
    const data = await res.json();
    const tree = buildTree((data.files || []) as FlatTreeEntry[]);
    setProjectTrees((prev) => ({ ...prev, [projectName]: tree }));
  };

  const deleteProject = async (projectName: string) => {
    const ok = window.confirm(t('left.confirmDeleteProject', { name: projectName }));
    if (!ok) return;
    const res = await fetch(`/api/projects/${encodeURIComponent(projectName)}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error || `delete project failed: ${res.status}`);
    }
    setProjectTrees((prev) => {
      const next = { ...prev };
      delete next[projectName];
      return next;
    });
    await loadProjects();
    await loadOutputs();
  };

  const deleteOutputRun = async (projectName: string, runId: string) => {
    const ok = window.confirm(t('left.confirmDeleteOutput', { project: projectName, run: runId }));
    if (!ok) return;
    const res = await fetch(`/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error || `delete output failed: ${res.status}`);
    }
    const key = runKey(projectName, runId);
    setOutputTrees((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    if (openRunKey === key) setOpenRunKey(null);
    setSelectedRunKeys((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
    await loadOutputs();
    window.dispatchEvent(new Event('evolve-projects-updated'));
  };

  const fetchOutputTree = async (
    projectName: string,
    runId: string,
    runKey: string,
    force = false,
    silent = false
  ) => {
    if (!force && outputTrees[runKey]) return;
    if (!silent) {
      setOutputTreeLoading((prev) => ({ ...prev, [runKey]: true }));
    }
    setOutputTreeError((prev) => ({ ...prev, [runKey]: '' }));
    try {
      const res = await fetch(`/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}/tree?maxDepth=6`);
      if (!res.ok) throw new Error(`GET output tree failed: ${res.status}`);
      const data = await res.json();
      const tree = buildTree((data.files || []) as FlatTreeEntry[]);
      setOutputTrees((prev) => {
        const current = prev[runKey] || [];
        if (sameTreeEntries(current, tree)) return prev;
        return { ...prev, [runKey]: tree };
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setOutputTreeError((prev) => ({ ...prev, [runKey]: message }));
    } finally {
      if (!silent) {
        setOutputTreeLoading((prev) => ({ ...prev, [runKey]: false }));
      }
    }
  };

  const previewProjectFile = async (projectName: string, path: string) => {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectName)}/file?path=${encodeURIComponent(path)}&maxBytes=131072`
    );
    if (!res.ok) throw new Error(`GET project file failed: ${res.status}`);
    const data = await res.json();
    const downloadUrl = `/api/projects/${encodeURIComponent(projectName)}/download?path=${encodeURIComponent(path)}`;
    emitPreview({
      title: `${projectName} / ${path}`,
      path,
      content: data.content || '',
      truncated: Boolean(data.truncated),
      downloadUrl,
      sourceType: 'project',
      projectName,
    });
  };

  const previewOutputFile = async (projectName: string, runId: string, path: string) => {
    const res = await fetch(
      `/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}/file?path=${encodeURIComponent(path)}&maxBytes=131072`
    );
    if (!res.ok) throw new Error(`GET output file failed: ${res.status}`);
    const data = await res.json();
    const downloadUrl = `/api/outputs/${encodeURIComponent(projectName)}/${encodeURIComponent(runId)}/download?path=${encodeURIComponent(path)}`;
    emitPreview({
      title: `${projectName} / ${runId} / ${path}`,
      path,
      content: data.content || '',
      truncated: Boolean(data.truncated),
      downloadUrl,
      sourceType: 'output',
      projectName,
      runId,
    });
  };

  const downloadByUrl = (url: string) => {
    const a = document.createElement('a');
    a.href = url;
    a.rel = 'noopener noreferrer';
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const copyText = async (value: string, label = 'runId') => {
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
    window.alert(t('left.copied', { label }));
  };

  const q = outputFilter.trim().toLowerCase();
  const filteredOutputRuns = outputRuns.filter((r) => {
    if (!q) return true;
    const metric = formatPrimaryMetric(r, t('left.noNumericMetrics'));
    const haystack = [
      r.projectName,
      r.runId,
      formatRunLabelToMinute(r.runId),
      metric.label,
      metric.value,
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(q);
  });
  const filteredRunKeys = filteredOutputRuns.map((r) => runKey(r.projectName, r.runId));
  const selectedFilteredCount = filteredRunKeys.filter((k) => selectedRunKeys.has(k)).length;
  const allFilteredSelected = filteredRunKeys.length > 0 && selectedFilteredCount === filteredRunKeys.length;

  useEffect(() => {
    const refresh = () => {
      loadProjects().catch((err) => {
        console.error(err);
        setProjects([]);
      });
      loadOutputs().catch((err) => {
        console.error(err);
        setOutputRuns([]);
      });
    };
    refresh();
    window.addEventListener('evolve-projects-updated', refresh);
    return () => {
      window.removeEventListener('evolve-projects-updated', refresh);
    };
  }, []);

  useEffect(() => {
    openRunKeyRef.current = openRunKey;
  }, [openRunKey]);

  useEffect(() => {
    outputRunsRef.current = outputRuns;
  }, [outputRuns]);

  useEffect(() => {
    const onRunState = (evt: Event) => {
      const custom = evt as CustomEvent<{ running?: boolean }>;
      const running = Boolean(custom.detail?.running);
      setIsRunActive(running);
      if (!running) {
        loadOutputs().catch((err) => console.error(err));
      }
    };
    window.addEventListener('evolve-run-state', onRunState as EventListener);
    return () => {
      window.removeEventListener('evolve-run-state', onRunState as EventListener);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!isRunActive) return;
      loadOutputs().catch((err) => console.error(err));
      const opened = openRunKeyRef.current;
      if (opened) {
        const target = outputRunsRef.current.find((r) => `${r.projectName}-${r.runId}` === opened);
        if (target) {
          fetchOutputTree(target.projectName, target.runId, opened, true, true).catch((err) => console.error(err));
        }
      }
    }, 3000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunActive]);

  useEffect(() => {
    const onOutputUpdated = (evt: Event) => {
      const custom = evt as CustomEvent<{ projectName: string; runId: string }>;
      const projectName = custom.detail?.projectName;
      const runId = custom.detail?.runId;
      if (!projectName || !runId) return;
      const key = `${projectName}-${runId}`;
      // checkpoint 持续生成时静默刷新，避免显示 loading 引起的闪动
      fetchOutputTree(projectName, runId, key, true, true).catch((err) => console.error(err));
      loadOutputs().catch((err) => console.error(err));
    };
    window.addEventListener('evolve-output-updated', onOutputUpdated as EventListener);
    return () => {
      window.removeEventListener('evolve-output-updated', onOutputUpdated as EventListener);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (outputRuns.length === 0) {
      setOpenRunKey(null);
      setDidAutoOpenRun(false);
      return;
    }
    if (!didAutoOpenRun && !openRunKey) {
      setDidAutoOpenRun(true);
    }
  }, [outputRuns, openRunKey, didAutoOpenRun]);

  useEffect(() => {
    const valid = new Set(outputRuns.map((r) => runKey(r.projectName, r.runId)));
    setSelectedRunKeys((prev) => {
      if (prev.size === 0) return prev;
      let changed = false;
      const next = new Set<string>();
      for (const k of prev) {
        if (valid.has(k)) next.add(k);
        else changed = true;
      }
      return changed ? next : prev;
    });
  }, [outputRuns]);

  const toggleRunSelected = (projectName: string, runId: string, checked: boolean) => {
    const key = runKey(projectName, runId);
    setSelectedRunKeys((prev) => {
      const next = new Set(prev);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const toggleAllFilteredSelected = (checked: boolean) => {
    setSelectedRunKeys((prev) => {
      const next = new Set(prev);
      if (checked) {
        for (const key of filteredRunKeys) next.add(key);
      } else {
        for (const key of filteredRunKeys) next.delete(key);
      }
      return next;
    });
  };

  const batchDownloadSelected = async () => {
    const picked = filteredOutputRuns.filter((r) => selectedRunKeys.has(runKey(r.projectName, r.runId)));
    if (picked.length === 0) return;
    setBatchBusy(true);
    try {
      for (const r of picked) {
        downloadByUrl(`/api/outputs/${encodeURIComponent(r.projectName)}/${encodeURIComponent(r.runId)}/archive`);
        await new Promise((resolve) => window.setTimeout(resolve, 120));
      }
    } finally {
      setBatchBusy(false);
    }
  };

  const batchDeleteSelected = async () => {
    const picked = filteredOutputRuns.filter((r) => selectedRunKeys.has(runKey(r.projectName, r.runId)));
    if (picked.length === 0) return;
    const ok = window.confirm(t('left.confirmDeleteSelectedOutputs', { count: String(picked.length) }));
    if (!ok) return;
    setBatchBusy(true);
    try {
      for (const r of picked) {
        const res = await fetch(
          `/api/outputs/${encodeURIComponent(r.projectName)}/${encodeURIComponent(r.runId)}`,
          { method: 'DELETE' }
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err?.error || `delete output failed: ${res.status}`);
        }
      }
      setSelectedRunKeys((prev) => {
        const next = new Set(prev);
        for (const r of picked) next.delete(runKey(r.projectName, r.runId));
        return next;
      });
      await loadOutputs();
      window.dispatchEvent(new Event('evolve-projects-updated'));
    } finally {
      setBatchBusy(false);
    }
  };

  const handleUploadClick = () => {
    uploadInputRef.current?.click();
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.zip')) {
      alert(t('left.alertZipOnly'));
      return;
    }

    const suggested = file.name.replace(/\.zip$/i, '');
    const projectName = window.prompt(t('left.promptProjectName'), suggested) || suggested;

    const form = new FormData();
    form.append('zip', file);
    form.append('projectName', projectName);

    const res = await fetch('/api/projects/upload', {
      method: 'POST',
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err?.error || t('left.uploadFailed'));
      return;
    }

    await loadProjects();
    window.dispatchEvent(new Event('evolve-projects-updated'));
    // 清空 input，避免同一个文件再次上传不触发 change
    if (uploadInputRef.current) uploadInputRef.current.value = '';
  };

  return (
    <div
      className="h-full min-w-[clamp(140px,11vw,180px)] max-w-[48%] min-h-0 bg-[#111827]/95 border-r border-white/10 shadow-[12px_0_32px_rgba(2,6,23,0.45)] flex flex-col"
      style={{ width: `${widthPercent}%` }}
    >
      <div className="px-4 pt-4 pb-2 space-y-2 border-b border-white/10">
        <Button
          className="w-full text-slate-100 text-xs gap-2 border border-white/10 bg-[#1e293b]/85 hover:bg-[#27364a] active:scale-[0.99] transition-all"
          onClick={handleUploadClick}
        >
          <Upload className="size-4" />
          {t('left.uploadButton')}
        </Button>
        <div className="group relative inline-flex">
          <span className="rounded border border-white/15 bg-[#0f172a]/70 px-2 py-0.5 text-[10px] text-slate-400">
            {t('left.uploadHintLabel')}
          </span>
          <div className="pointer-events-none absolute left-0 top-full z-20 mt-1 w-[320px] rounded border border-white/15 bg-[#0b1220]/95 p-2 text-[10px] leading-relaxed text-slate-300 opacity-0 shadow-xl transition-opacity duration-150 group-hover:opacity-100 whitespace-normal break-words">
            <p>{t('left.uploadHint1')}</p>
            <p className="mt-1">
              <span className="text-slate-300">{t('left.uploadHint2')}</span>
            </p>
            <p className="mt-1 text-slate-400">{t('left.uploadHint3')}</p>
          </div>
        </div>
      </div>

      <input
        ref={uploadInputRef}
        type="file"
        accept=".zip"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-4 pb-4 pt-2">
          {/* Evolution Objects Section */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3 px-2">
              <div className="size-2 rounded-full" style={{ backgroundColor: colors.primary, boxShadow: '0 0 8px color-mix(in srgb, var(--oe-primary) 55%, transparent)' }}></div>
              <h3 className="text-xs font-semibold tracking-[0.16em] uppercase text-slate-200">
                {t('left.sectionEvolutionObjects')}
              </h3>
              <span className="text-[10px] font-medium text-slate-300">{t('left.sectionInputsTag')}</span>
            </div>
            <div className="space-y-1">
              {projects.map((project) => (
                <ProjectFolder
                  key={project.name}
                  project={{ ...project, files: projectTrees[project.name] || project.files }}
                  onLoadTree={(name) => fetchProjectTree(name).catch((err) => console.error(err))}
                  onPreview={(projectName, path) => previewProjectFile(projectName, path).catch((err) => alert(err.message))}
                  onDownload={(projectName, path) =>
                    downloadByUrl(`/api/projects/${encodeURIComponent(projectName)}/download?path=${encodeURIComponent(path)}`)
                  }
                  onDeleteProject={(name) => deleteProject(name).catch((err) => alert(err.message))}
                />
              ))}
              {projects.length === 0 && (
                <div className="text-gray-500 text-xs py-2 text-center">{t('left.evolutionObjectsEmpty')}</div>
              )}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3 px-2">
              <div className="size-2 rounded-full" style={{ backgroundColor: 'var(--oe-primary)', boxShadow: '0 0 8px color-mix(in srgb, var(--oe-primary) 55%, transparent)' }}></div>
              <h3 className="text-xs font-semibold tracking-[0.16em] uppercase text-slate-200">
                {t('left.sectionEvolutionOutputs')}
              </h3>
              <span className="text-[10px] font-medium text-slate-300">{t('left.sectionResultsTag')}</span>
              <button
                type="button"
                className="rounded border border-white/15 bg-[#0f172a]/70 px-2 py-0.5 text-[10px] text-slate-400 transition-colors hover:text-slate-200"
                onMouseEnter={(e) => setOutputsGuideTip({ x: e.clientX + 12, y: e.clientY + 14 })}
                onMouseMove={(e) => setOutputsGuideTip({ x: e.clientX + 12, y: e.clientY + 14 })}
                onMouseLeave={() => setOutputsGuideTip(null)}
              >
                {t('left.outputsGuideLabel')}
              </button>
            </div>
            <div className="px-2 mb-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-1/2 size-3 -translate-y-1/2 text-slate-500" />
                <input
                  value={outputFilter}
                  onChange={(e) => setOutputFilter(e.target.value)}
                  placeholder={t('left.searchPlaceholder')}
                  className="h-7 w-full rounded border border-white/10 bg-[#0f172a]/70 pl-7 pr-2 text-[11px] text-slate-200 outline-none focus:border-[color:var(--oe-primary)]"
                />
              </div>
            </div>
            <div className="px-2 mb-3 rounded-lg border border-cyan-400/25 bg-gradient-to-r from-cyan-500/10 to-transparent p-2">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label className="flex items-center gap-1.5 text-[10px] font-medium text-slate-200">
                  <input
                    type="checkbox"
                    className="size-3 rounded border-white/30 bg-[#0b1220]"
                    checked={allFilteredSelected}
                    onChange={(e) => toggleAllFilteredSelected(e.target.checked)}
                    disabled={filteredRunKeys.length === 0 || batchBusy}
                  />
                  <span>{t('left.selectAllOutputs')}</span>
                </label>
                <span className="rounded-full border border-white/15 bg-[#0b1220]/70 px-1.5 py-0.5 text-[9px] text-slate-300">
                  {t('left.selectedCount', { count: String(selectedRunKeys.size) })}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  className="h-7 flex-1 text-[10px] gap-1 font-semibold border border-cyan-300/30 bg-cyan-500/20 text-cyan-100 hover:bg-cyan-500/30"
                  onClick={() => batchDownloadSelected().catch((err) => alert(err.message))}
                  disabled={selectedRunKeys.size === 0 || batchBusy}
                >
                  <Download className="size-2.5" />
                  {t('left.batchDownload')}
                </Button>
                <Button
                  className="h-7 flex-1 text-[10px] gap-1 font-semibold border border-rose-400/40 bg-rose-500/15 text-rose-200 hover:bg-rose-500/25"
                  onClick={() => batchDeleteSelected().catch((err) => alert(err.message))}
                  disabled={selectedRunKeys.size === 0 || batchBusy}
                >
                  <Trash2 className="size-2.5" />
                  {t('left.batchDelete')}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              {filteredOutputRuns.map((r) => (
                <Collapsible.Root
                  key={runKey(r.projectName, r.runId)}
                  open={openRunKey === runKey(r.projectName, r.runId)}
                  onOpenChange={(open) => {
                    const key = runKey(r.projectName, r.runId);
                    setOpenRunKey(open ? key : null);
                    if (open) fetchOutputTree(r.projectName, r.runId, key).catch((err) => console.error(err));
                  }}
                >
                  <div className="rounded border border-white/10 bg-[#0f172a]/70 px-2.5 py-2 text-left">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            className="mt-0.5 size-3.5 rounded border-white/30 bg-[#0b1220]"
                            checked={selectedRunKeys.has(runKey(r.projectName, r.runId))}
                            disabled={batchBusy}
                            onChange={(e) => toggleRunSelected(r.projectName, r.runId, e.target.checked)}
                          />
                          <div
                            className="font-mono text-[11px] text-emerald-300/90 whitespace-nowrap overflow-hidden text-ellipsis max-w-[180px]"
                            title={r.projectName}
                          >
                            {r.projectName}
                          </div>
                        </div>
                      </div>
                      <div className="shrink-0 flex items-center gap-1">
                        <Collapsible.Trigger className="oe-primary-soft-btn rounded px-1.5 py-1 text-[10px] font-semibold transition-colors">
                          {openRunKey === runKey(r.projectName, r.runId) ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                        </Collapsible.Trigger>
                        <button
                          className="oe-ghost-btn rounded p-1"
                          title={t('left.copyRunId')}
                          onClick={(e) => {
                            e.stopPropagation();
                            copyText(formatRunLabelToMinute(r.runId), 'runId').catch(console.error);
                          }}
                        >
                          <Copy className="size-3" />
                        </button>
                        <button
                          className="oe-ghost-btn rounded p-1"
                          title={t('left.downloadArchive')}
                          onClick={(e) => {
                            e.stopPropagation();
                            downloadByUrl(
                              `/api/outputs/${encodeURIComponent(r.projectName)}/${encodeURIComponent(r.runId)}/archive`
                            );
                          }}
                        >
                          <Download className="size-3" />
                        </button>
                        <button
                          className="oe-danger-ghost-btn rounded p-1"
                          title={t('left.deleteOutput')}
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteOutputRun(r.projectName, r.runId).catch((err) => alert(err.message));
                          }}
                        >
                          <Trash2 className="size-3" />
                        </button>
                      </div>
                    </div>
                    <div className="mt-1 text-[10px] text-slate-500">
                      {(() => {
                        const metric = formatPrimaryMetric(r, t('left.noNumericMetrics'));
                        return (
                          <div className="space-y-0.5">
                            <div className="text-cyan-300">{displayRunTimestamp(r)}</div>
                            <div className="flex flex-wrap items-center gap-x-1 gap-y-0.5" title={formatAllMetricsTooltip(r)}>
                              <span className="text-slate-400">combined_score</span>
                              <span className="text-slate-700">:</span>
                              <span className={metric.ok ? 'text-emerald-300 font-semibold text-[11px] break-all' : 'text-slate-500 break-all'}>
                                {metric.value}
                              </span>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                    <Collapsible.Content className="mt-2 border-t border-white/10 pt-2">
                      {outputTreeLoading[runKey(r.projectName, r.runId)] && (
                        <div className="px-2 py-2 text-[11px] text-slate-500">{t('left.loadingFiles')}</div>
                      )}
                      {outputTreeError[runKey(r.projectName, r.runId)] && (
                        <div className="px-2 py-2 text-[11px] text-rose-300">
                          {t('left.failedLoadFiles')} {outputTreeError[runKey(r.projectName, r.runId)]}
                        </div>
                      )}
                      {!outputTreeLoading[runKey(r.projectName, r.runId)] &&
                        !outputTreeError[runKey(r.projectName, r.runId)] &&
                        (outputTrees[runKey(r.projectName, r.runId)] || []).length === 0 && (
                          <div className="px-2 py-2 text-[11px] text-slate-500">{t('left.noFilesFound')}</div>
                        )}
                      {(outputTrees[runKey(r.projectName, r.runId)] || []).map((node, idx) => (
                        <FileTreeItem
                          key={idx}
                          node={node}
                          depth={1}
                          fullPath=""
                          alwaysShowActions={true}
                          onPreview={(path) => previewOutputFile(r.projectName, r.runId, path).catch((err) => alert(err.message))}
                          onDownload={(path) =>
                            downloadByUrl(
                              `/api/outputs/${encodeURIComponent(r.projectName)}/${encodeURIComponent(r.runId)}/download?path=${encodeURIComponent(path)}`
                            )
                          }
                        />
                      ))}
                    </Collapsible.Content>
                  </div>
                </Collapsible.Root>
              ))}
              {filteredOutputRuns.length === 0 && (
                <div className="text-gray-500 text-xs py-2 text-center">{t('left.outputsEmpty')}</div>
              )}
            </div>
          </div>

        </div>
      </ScrollArea>
      {outputsGuideTip && (
        <div
          className="pointer-events-none fixed z-[9999] w-[320px] max-w-[min(320px,calc(100vw-1rem))] rounded border border-white/15 bg-[#0b1220]/95 p-2 text-[10px] leading-relaxed text-slate-300 shadow-xl whitespace-normal break-words"
          style={{ left: outputsGuideTip.x, top: outputsGuideTip.y }}
        >
          <p>{t('left.outputsGuide1')}</p>
          <p className="mt-1 text-slate-400">{t('left.outputsGuide2')}</p>
        </div>
      )}
    </div>
  );
}