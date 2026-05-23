import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { messages, type Locale } from '../locales/messages';

const STORAGE_KEY = 'oe-locale';

function readStoredLocale(): Locale | null {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    if (s === 'zh' || s === 'en') return s;
  } catch {
    /* ignore */
  }
  return null;
}

function detectLocale(): Locale {
  const stored = readStoredLocale();
  if (stored) return stored;
  if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('zh')) {
    return 'zh';
  }
  return 'en';
}

function applyPlaceholders(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  let s = template;
  for (const [k, v] of Object.entries(vars)) {
    s = s.replaceAll(`{${k}}`, String(v));
  }
  return s;
}

interface LocaleContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<LocaleContextValue | undefined>(undefined);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      /* ignore */
    }
    document.documentElement.lang = locale === 'zh' ? 'zh-CN' : 'en';
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      const table = messages[locale];
      const raw = table[key] ?? messages.en[key] ?? key;
      return applyPlaceholders(raw, vars);
    },
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error('useLocale must be used within LocaleProvider');
  }
  return ctx;
}
