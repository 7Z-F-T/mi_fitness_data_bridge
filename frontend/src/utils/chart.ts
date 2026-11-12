export type ChartTheme = 'light' | 'dark'

export interface ChartPalette {
  text: string
  faint: string
  grid: string
  split: string
  surface: string
  tooltipBg: string
  tooltipText: string
  accent: string
  orange: string
  blue: string
  green: string
  violet: string
  red: string
  pink: string
  cyan: string
}

export const chartPalettes: Record<ChartTheme, ChartPalette> = {
  light: {
    text: '#5d6d7c',
    faint: '#8a99a7',
    grid: '#e2e8ee',
    split: '#edf1f5',
    surface: '#ffffff',
    tooltipBg: '#ffffff',
    tooltipText: '#13202b',
    accent: '#0d9488',
    orange: '#ea580c',
    blue: '#2563eb',
    green: '#16a34a',
    violet: '#7c3aed',
    red: '#dc2626',
    pink: '#db2777',
    cyan: '#0891b2',
  },
  dark: {
    text: '#9aa8b6',
    faint: '#6f7f8e',
    grid: '#24303c',
    split: '#1b2530',
    surface: '#121820',
    tooltipBg: '#161e27',
    tooltipText: '#eef3f7',
    accent: '#2dd4bf',
    orange: '#fb923c',
    blue: '#60a5fa',
    green: '#4ade80',
    violet: '#a78bfa',
    red: '#f87171',
    pink: '#f472b6',
    cyan: '#22d3ee',
  },
}

export function chartPalette(theme: ChartTheme): ChartPalette {
  return chartPalettes[theme]
}

export function axisTextStyle(theme: ChartTheme) {
  const palette = chartPalette(theme)
  return {
    color: palette.text,
    fontSize: 11,
    fontFamily:
      "Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif",
  }
}
