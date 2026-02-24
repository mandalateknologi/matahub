import { writable } from 'svelte/store';

/**
 * Theme mode options
 * - 'light': Force light theme
 * - 'dark': Force dark theme
 * - 'auto': Use system preference
 */
export type ThemeMode = 'light' | 'dark' | 'auto';

/**
 * Get initial theme from localStorage or default to 'auto'
 */
function getInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'auto';
  
  const stored = localStorage.getItem('atvision-theme');
  if (stored === 'light' || stored === 'dark' || stored === 'auto') {
    return stored;
  }
  
  return 'auto';
}

/**
 * Determine the actual theme to apply based on mode and system preference
 */
function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'auto') {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  }
  return mode;
}

/**
 * Apply theme to document
 */
function applyTheme(mode: ThemeMode): void {
  if (typeof window === 'undefined') return;
  
  const resolvedTheme = resolveTheme(mode);
  const html = document.documentElement;
  
  console.log('applyTheme called with mode:', mode, 'resolved:', resolvedTheme);
  
  if (resolvedTheme === 'dark') {
    html.setAttribute('data-theme', 'dark');
    console.log('Set data-theme to dark');
  } else {
    html.setAttribute('data-theme', 'light');
    console.log('Set data-theme to light');
  }
}

/**
 * Theme store with persistence
 */
function createThemeStore() {
  const { subscribe, set, update } = writable<ThemeMode>(getInitialTheme());

  return {
    subscribe,
    setTheme: (mode: ThemeMode) => {
      console.log('setTheme called with:', mode);
      if (typeof window !== 'undefined') {
        localStorage.setItem('atvision-theme', mode);
        applyTheme(mode);
      }
      set(mode);
    },
    toggle: () => {
      update(current => {
        console.log('toggle called, current:', current);
        const resolved = resolveTheme(current);
        const next: ThemeMode = resolved === 'dark' ? 'light' : 'dark';
        console.log('resolved:', resolved, 'next:', next);
        
        if (typeof window !== 'undefined') {
          localStorage.setItem('atvision-theme', next);
          applyTheme(next);
        }
        return next;
      });
    },
    init: () => {
      const theme = getInitialTheme();
      applyTheme(theme);
      set(theme);
    }
  };
}

export const themeStore = createThemeStore();

/**
 * Initialize theme on app load
 * Call this in your root layout or App.svelte
 */
export function initTheme(): void {
  themeStore.init();
  
  // Listen for system theme changes when in auto mode
  if (typeof window !== 'undefined' && window.matchMedia) {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = () => {
      const stored = localStorage.getItem('atvision-theme');
      if (stored === 'auto') {
        applyTheme('auto');
      }
    };
    
    // Modern browsers
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      // Fallback for older browsers
      mediaQuery.addListener(handleChange);
    }
  }
}
