import { useEffect, useRef, useState } from 'react';
import { TopNav } from './components/TopNav';
import { LeftPanel } from './components/LeftPanel';
import { RightPanel } from './components/RightPanel';
import { ThemeProvider } from './contexts/ThemeContext';
import { LocaleProvider, useLocale } from './contexts/LocaleContext';

function AppShell() {
  const { t } = useLocale();
  const [leftWidth, setLeftWidth] = useState(() => {
    if (typeof window === 'undefined') return 18;
    if (window.innerWidth < 1366) return 20;
    if (window.innerWidth < 1800) return 18;
    return 17;
  });
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      const root = containerRef.current;
      if (!root) return;
      const rect = root.getBoundingClientRect();
      if (rect.width <= 0) return;
      const raw = ((e.clientX - rect.left) / rect.width) * 100;
      const rightMinPx = Math.min(700, Math.max(520, rect.width * 0.42));
      const separatorPx = 4;
      const maxByRight = ((rect.width - rightMinPx - separatorPx) / rect.width) * 100;
      const upper = Math.min(48, Math.max(16, maxByRight));
      const clamped = Math.min(upper, Math.max(10, raw));
      setLeftWidth(clamped);
    };
    const onUp = () => setIsResizing(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isResizing]);

  return (
    <div
      className="size-full flex flex-col overflow-hidden bg-[#0f172a]"
      style={{
        backgroundImage:
          'radial-gradient(circle at 15% 0%, rgba(30, 64, 175, 0.2), transparent 42%), radial-gradient(circle at 85% 100%, rgba(15, 118, 110, 0.12), transparent 40%), linear-gradient(180deg, #111827 0%, #0f172a 58%, #0b1220 100%)',
      }}
    >
      <TopNav />
      <div ref={containerRef} className="h-[calc(100vh-56px)] min-h-0 flex overflow-hidden">
        <LeftPanel widthPercent={leftWidth} />
        <div
          role="separator"
          aria-orientation="vertical"
          className={`w-1 cursor-col-resize bg-white/15 hover:bg-emerald-400/55 transition-colors ${isResizing ? 'bg-emerald-400/75' : ''}`}
          onMouseDown={() => setIsResizing(true)}
          title={t('app.resizeSeparator')}
        />
        <RightPanel />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <LocaleProvider>
        <AppShell />
      </LocaleProvider>
    </ThemeProvider>
  );
}