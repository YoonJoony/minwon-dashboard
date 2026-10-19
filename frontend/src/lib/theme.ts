/** 화면 색. Tailwind 테마(index.css)와 같은 값을 차트(ECharts)에서도 씁니다. */
export const C = {
  ink: '#16161d',
  mute: '#6b6b7b',
  faint: '#a3a3b2',
  line: '#ebebf1',
  grid: '#f0f0f5',
  brand: '#5b4fe0',
  brandMid: '#8b7cf6',
  brandSoft: '#c9c1f7',
  brandTint: '#f0eefd',
  navy: '#1f1b4d',
  history: '#e4e3ec',
  up: '#e0483f',
  down: '#17955a',
} as const

export const QUADRANTS = ['집중관리', '처리지연 주의', '접수증가 주의', '안정', '지원 가능'] as const
export type Quadrant = (typeof QUADRANTS)[number]

export const QUADRANT_COLOR: Record<string, string> = {
  집중관리: '#e5484d',
  '처리지연 주의': '#e39b2d',
  '접수증가 주의': '#ef8354',
  안정: '#a3a3b5',
  '지원 가능': '#22a06b',
}

export const QUADRANT_TINT: Record<string, string> = {
  집중관리: '#fdecec',
  '처리지연 주의': '#fcf1df',
  '접수증가 주의': '#fdeee6',
  안정: '#f1f1f5',
  '지원 가능': '#e5f5ed',
}

export const QUADRANT_DESC: Record<string, string> = {
  집중관리: '접수 증가 + 적체 증가',
  '처리지연 주의': '적체 증가',
  '접수증가 주의': '접수 증가',
  안정: '평소 수준',
  '지원 가능': '접수 감소 · 적체 정상',
}

/** 경보·이슈 문구의 톤 */
export const TONE = {
  danger: { bg: '#fdf0ef', border: '#f6cfcb', fg: '#c2362d', icon: '#e0483f' },
  warning: { bg: '#fdf5e8', border: '#f3dcb2', fg: '#a35a07', icon: '#d97706' },
  info: { bg: '#f4f2fe', border: '#dcd6fb', fg: '#4a3fc7', icon: '#5b4fe0' },
} as const
export type Tone = keyof typeof TONE
export const toneOf = (t: string): Tone => (t === 'danger' || t === 'warning' ? t : 'info')
