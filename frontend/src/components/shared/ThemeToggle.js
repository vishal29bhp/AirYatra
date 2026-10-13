import React, { useState, useEffect, createContext, useContext } from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';

// Theme Context
const ThemeContext = createContext();

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

// Theme Provider
export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    // Check localStorage first
    const saved = localStorage.getItem('airyatra_theme');
    if (saved) return saved;
    // Dark is the AirYatra default (theme rules, master prompt C.4); light is opt-in via the toggle.
    return 'dark';
  });

  useEffect(() => {
    // Apply theme to document
    const root = document.documentElement;
    
    if (theme === 'light') {
      root.classList.remove('dark');
      root.classList.add('light');
      root.style.setProperty('--bg-primary', '#F2EEF6');
      root.style.setProperty('--bg-secondary', '#FFFFFF');
      root.style.setProperty('--bg-tertiary', '#E2DCE9');
      root.style.setProperty('--text-primary', '#17111F');
      root.style.setProperty('--text-secondary', '#5A5068');
      root.style.setProperty('--border-color', '#D0C9DA');
    } else {
      root.classList.remove('light');
      root.classList.add('dark');
      root.style.setProperty('--bg-primary', '#17111F');
      root.style.setProperty('--bg-secondary', '#221A2D');
      root.style.setProperty('--bg-tertiary', '#3A3046');
      root.style.setProperty('--text-primary', '#F2EEF6');
      root.style.setProperty('--text-secondary', '#D0C9DA');
      root.style.setProperty('--border-color', '#3A3046');
    }
    
    // Save to localStorage
    localStorage.setItem('airyatra_theme', theme);
  }, [theme]);

  // Listen for system preference changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      const saved = localStorage.getItem('airyatra_theme');
      // Only update if user hasn't set a preference
      if (!saved) {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

// Theme Toggle Button Component
export const ThemeToggle = ({ className = '', showLabel = false }) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`relative p-2 rounded-lg transition-all duration-300 ${
        theme === 'dark' 
          ? 'bg-slate-800 hover:bg-slate-700 text-yellow-400' 
          : 'bg-slate-200 hover:bg-slate-300 text-slate-700'
      } ${className}`}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      <div className="relative w-5 h-5">
        {/* Sun icon */}
        <Sun 
          className={`h-5 w-5 absolute inset-0 transition-all duration-300 ${
            theme === 'dark' 
              ? 'rotate-0 scale-100 opacity-100' 
              : 'rotate-90 scale-0 opacity-0'
          }`}
        />
        {/* Moon icon */}
        <Moon 
          className={`h-5 w-5 absolute inset-0 transition-all duration-300 ${
            theme === 'light' 
              ? 'rotate-0 scale-100 opacity-100' 
              : '-rotate-90 scale-0 opacity-0'
          }`}
        />
      </div>
      {showLabel && (
        <span className="ml-2 text-sm">
          {theme === 'dark' ? 'Dark' : 'Light'}
        </span>
      )}
    </button>
  );
};

// Theme Selector with 3 options (Light, Dark, System)
export const ThemeSelector = ({ className = '' }) => {
  const { theme, setTheme } = useTheme();
  const [systemPreference, setSystemPreference] = useState(
    window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  );

  const options = [
    { value: 'light', icon: Sun, label: 'Light' },
    { value: 'dark', icon: Moon, label: 'Dark' },
    { value: 'system', icon: Monitor, label: 'System' }
  ];

  return (
    <div className={`flex items-center gap-1 p-1 bg-slate-800/50 rounded-lg ${className}`}>
      {options.map(option => {
        const Icon = option.icon;
        const isActive = theme === option.value || 
          (option.value === 'system' && theme === systemPreference);
        
        return (
          <button
            key={option.value}
            onClick={() => setTheme(option.value === 'system' ? systemPreference : option.value)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-all ${
              isActive
                ? 'bg-orange-500 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            <Icon className="h-4 w-4" />
            <span className="hidden sm:inline">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
};

export default ThemeToggle;
