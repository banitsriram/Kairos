/**
 * Time-of-day theming.
 * Sets CSS custom properties on :root based on the current hour.
 * Call applyTheme() once on load and then on each hour boundary.
 *
 * Why CSS variables instead of a JS theme object?
 * CSS variables let every component react to theme changes instantly
 * with zero re-renders — the browser handles it. Much faster than
 * passing theme props down the component tree.
 */

export type Period = 'dawn' | 'morning' | 'afternoon' | 'evening' | 'night'

interface ThemeTokens {
  '--accent':    string
  '--accent-dim': string
  '--bg':        string
  '--bg-panel':  string
  '--bg-hover':  string
  '--text':      string
  '--text-dim':  string
  '--border':    string
  '--period':    string
}

const THEMES: Record<Period, ThemeTokens> = {
  dawn: {
    '--accent':     '#f59e0b',
    '--accent-dim': '#78350f',
    '--bg':         '#0f0a05',
    '--bg-panel':   '#1a1208',
    '--bg-hover':   '#251a0d',
    '--text':       '#fef3c7',
    '--text-dim':   '#92400e',
    '--border':     '#292010',
    '--period':     'dawn',
  },
  morning: {
    '--accent':     '#60a5fa',
    '--accent-dim': '#1e3a5f',
    '--bg':         '#060b14',
    '--bg-panel':   '#0d1626',
    '--bg-hover':   '#111e33',
    '--text':       '#e0f0ff',
    '--text-dim':   '#4a6fa5',
    '--border':     '#0f1f35',
    '--period':     'morning',
  },
  afternoon: {
    '--accent':     '#a78bfa',
    '--accent-dim': '#3b1f6e',
    '--bg':         '#09060f',
    '--bg-panel':   '#120d1e',
    '--bg-hover':   '#1a1228',
    '--text':       '#ede9fe',
    '--text-dim':   '#5b4a8a',
    '--border':     '#1a1230',
    '--period':     'afternoon',
  },
  evening: {
    '--accent':     '#fb923c',
    '--accent-dim': '#7c2d12',
    '--bg':         '#0f0905',
    '--bg-panel':   '#1c1008',
    '--bg-hover':   '#261608',
    '--text':       '#ffedd5',
    '--text-dim':   '#9a3412',
    '--border':     '#2a1508',
    '--period':     'evening',
  },
  night: {
    '--accent':     '#818cf8',
    '--accent-dim': '#1e2050',
    '--bg':         '#05060f',
    '--bg-panel':   '#0c0e1e',
    '--bg-hover':   '#12142a',
    '--text':       '#e0e7ff',
    '--text-dim':   '#3730a3',
    '--border':     '#10122a',
    '--period':     'night',
  },
}

export function getPeriod(hour = new Date().getHours()): Period {
  if (hour >= 5  && hour < 8)  return 'dawn'
  if (hour >= 8  && hour < 12) return 'morning'
  if (hour >= 12 && hour < 17) return 'afternoon'
  if (hour >= 17 && hour < 21) return 'evening'
  return 'night'
}

export function getPeriodLabel(period: Period): string {
  const labels: Record<Period, string> = {
    dawn:      'Good morning',
    morning:   'Good morning',
    afternoon: 'Good afternoon',
    evening:   'Good evening',
    night:     'Still up?',
  }
  return labels[period]
}

export function applyTheme(period?: Period): Period {
  const p = period ?? getPeriod()
  const tokens = THEMES[p]
  const root = document.documentElement
  for (const [key, val] of Object.entries(tokens)) {
    root.style.setProperty(key, val)
  }
  return p
}
