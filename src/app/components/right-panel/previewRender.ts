import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import python from 'highlight.js/lib/languages/python';
import yaml from 'highlight.js/lib/languages/yaml';
import json from 'highlight.js/lib/languages/json';
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import bash from 'highlight.js/lib/languages/bash';
import xml from 'highlight.js/lib/languages/xml';
import markdown from 'highlight.js/lib/languages/markdown';

hljs.registerLanguage('python', python);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('json', json);
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('markdown', markdown);

function getFileExtension(pathLike: string): string {
  const file = String(pathLike || '').split('/').pop() || '';
  const idx = file.lastIndexOf('.');
  return idx >= 0 ? file.slice(idx + 1).toLowerCase() : '';
}

export function isMarkdownFile(pathLike: string): boolean {
  const ext = getFileExtension(pathLike);
  return ext === 'md' || ext === 'markdown';
}

function toHljsLanguage(pathLike: string): string | undefined {
  const ext = getFileExtension(pathLike);
  if (ext === 'py') return 'python';
  if (ext === 'yml' || ext === 'yaml') return 'yaml';
  if (ext === 'json') return 'json';
  if (ext === 'js' || ext === 'mjs' || ext === 'cjs') return 'javascript';
  if (ext === 'ts' || ext === 'tsx') return 'typescript';
  if (ext === 'sh' || ext === 'bash' || ext === 'zsh') return 'bash';
  if (ext === 'html' || ext === 'xml' || ext === 'svg') return 'xml';
  if (ext === 'md' || ext === 'markdown') return 'markdown';
  return undefined;
}

function escapeHtml(content: string): string {
  return content.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

export function renderCodeHtml(content: string, pathLike: string): string {
  try {
    const lang = toHljsLanguage(pathLike);
    const escaped = escapeHtml(content || '');
    if (!lang) return DOMPurify.sanitize(`<pre><code>${escaped}</code></pre>`);
    const highlighted = hljs.highlight(content || '', { language: lang, ignoreIllegals: true }).value;
    return DOMPurify.sanitize(`<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`);
  } catch {
    return DOMPurify.sanitize(`<pre><code>${escapeHtml(content || '')}</code></pre>`);
  }
}

export function renderMarkdownHtml(content: string): string {
  try {
    const html = marked.parse(content || '', { breaks: true, gfm: true });
    if (typeof html === 'string' && html.trim()) return DOMPurify.sanitize(html);
    return DOMPurify.sanitize(`<pre><code>${escapeHtml(content || '')}</code></pre>`);
  } catch {
    return DOMPurify.sanitize(`<pre><code>${escapeHtml(content || '')}</code></pre>`);
  }
}
