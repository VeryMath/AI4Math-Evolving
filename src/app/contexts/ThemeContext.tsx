import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

export type ColorTheme = 'cyan' | 'purple' | 'emerald' | 'amber' | 'rose';

interface ThemeColors {
  primary: string;
  primaryLight: string;
  primaryDark: string;
  secondary: string;
  accent: string;
  gradient: string;
}

const themeConfig: Record<ColorTheme, ThemeColors> = {
  cyan: {
    primary: '#0f766e',
    primaryLight: '#14b8a6',
    primaryDark: '#115e59',
    secondary: '#1d4ed8',
    accent: '#4f46e5',
    gradient: 'from-teal-700/20 to-indigo-900/20'
  },
  purple: {
    primary: '#a855f7',
    primaryLight: '#c084fc',
    primaryDark: '#9333ea',
    secondary: '#ec4899',
    accent: '#f59e0b',
    gradient: 'from-purple-600/10 to-purple-800/10'
  },
  emerald: {
    primary: '#10b981',
    primaryLight: '#34d399',
    primaryDark: '#059669',
    secondary: '#14b8a6',
    accent: '#06b6d4',
    gradient: 'from-emerald-600/10 to-emerald-800/10'
  },
  amber: {
    primary: '#f59e0b',
    primaryLight: '#fbbf24',
    primaryDark: '#d97706',
    secondary: '#f97316',
    accent: '#ef4444',
    gradient: 'from-amber-600/10 to-amber-800/10'
  },
  rose: {
    primary: '#f43f5e',
    primaryLight: '#fb7185',
    primaryDark: '#e11d48',
    secondary: '#ec4899',
    accent: '#a855f7',
    gradient: 'from-rose-600/10 to-rose-800/10'
  }
};

interface ThemeContextType {
  theme: ColorTheme;
  setTheme: (theme: ColorTheme) => void;
  colors: ThemeColors;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ColorTheme>('cyan');
  const colors = themeConfig[theme];

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--oe-primary', colors.primary);
    root.style.setProperty('--oe-primary-light', colors.primaryLight);
    root.style.setProperty('--oe-primary-dark', colors.primaryDark);
    root.style.setProperty('--oe-secondary', colors.secondary);
    root.style.setProperty('--oe-accent', colors.accent);
    root.style.setProperty('--oe-scrollbar-thumb', `${colors.primary}99`);
    root.style.setProperty('--oe-scrollbar-track', '#0f172a73');
  }, [colors]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, colors }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
