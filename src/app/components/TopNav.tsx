import { Cpu, Zap, Palette, Languages } from 'lucide-react';
import { useTheme, ColorTheme } from '../contexts/ThemeContext';
import { useLocale } from '../contexts/LocaleContext';
import { Button } from './ui/button';

const themeIcons: Record<ColorTheme, string> = {
  cyan: '🔷',
  purple: '🟣',
  emerald: '🟢',
  amber: '🟡',
  rose: '🔴',
};

export function TopNav() {
  const { theme, setTheme, colors } = useTheme();
  const { locale, setLocale, t } = useLocale();
  const themeKeys = Object.keys(themeIcons) as ColorTheme[];

  const handleCycleTheme = () => {
    const idx = themeKeys.indexOf(theme);
    const next = themeKeys[(idx + 1) % themeKeys.length];
    setTheme(next);
  };

  return (
    <div className="h-14 bg-[#111827]/95 border-b border-white/10 shadow-[0_8px_24px_rgba(2,6,23,0.45)] flex items-center px-6">
      <div className="flex items-center gap-3">
        <div className="relative">
          <Cpu className="size-7" style={{ color: colors.primary }} />
          <Zap className="size-3 absolute -bottom-0.5 -right-0.5" style={{ color: colors.accent }} />
        </div>
        <div>
          <h1 className="font-semibold text-lg text-white tracking-tight">AI4Math-Evolving</h1>
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-400">{t('nav.subtitle')}</p>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <div className="flex rounded-md border border-white/10 bg-[#1e293b]/45 p-[2px] text-[10px] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <button
            type="button"
            className={`rounded px-2 py-0.5 leading-5 transition-colors ${locale === 'zh' ? 'bg-white/12 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            onClick={() => setLocale('zh')}
          >
            {t('nav.langZh')}
          </button>
          <button
            type="button"
            className={`rounded px-2 py-0.5 leading-5 transition-colors ${locale === 'en' ? 'bg-white/12 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            onClick={() => setLocale('en')}
          >
            {t('nav.langEn')}
          </button>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 border-white/10 bg-[#1e293b]/50 hover:bg-[#1e293b] transition-colors"
          onClick={handleCycleTheme}
          title={t('nav.themeTooltip')}
        >
          <Palette className="size-4" style={{ color: colors.primary }} />
          <span className="text-xs text-gray-400">
            {t('nav.themePrefix')}
            {themeIcons[theme]} {t(`theme.${theme}`)}
          </span>
        </Button>
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400">
          <Languages className="size-3.5 opacity-70" />
          {t('nav.openCodeIntegration')}
        </div>
        <div className="size-2 rounded-full bg-emerald-500 animate-pulse shrink-0" title="SSE" />
      </div>
    </div>
  );
}
