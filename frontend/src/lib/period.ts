import { addDays, addMonths, differenceInCalendarDays, format, isValid, parseISO, subDays } from 'date-fns'

export type PresetKey = '7d' | '14d' | 'month' | 'quarter'
export const PRESET_KEYS: PresetKey[] = ['7d', '14d', 'month', 'quarter']

/** 1~14일은 단기 모델, 그 뒤는 월별 방식 (engine.dashboard.period_forecast와 같은 규칙) */
export const SHORT_DAYS = 14

export const toISO = (dt: Date) => format(dt, 'yyyy-MM-dd')
const parse = (s: string) => parseISO(s)

/** 빠른 선택 기간. 한 달·분기는 달력 기준(기준일 + 1개월/3개월 − 1일)이라 최대 92일을 넘지 않습니다. */
export function presetRange(asof: string, key: PresetKey): { start: string; end: string } {
  const a = parse(asof)
  const end =
    key === '7d' ? addDays(a, 6) : key === '14d' ? addDays(a, 13) : subDays(addMonths(a, key === 'month' ? 1 : 3), 1)
  return { start: asof, end: toISO(end) }
}

export function detectPreset(asof: string, start: string, end: string): PresetKey | 'custom' {
  for (const k of PRESET_KEYS) {
    const r = presetRange(asof, k)
    if (r.start === start && r.end === end) return k
  }
  return 'custom'
}

/** 양 끝 포함 일수 */
export const daysBetween = (start: string, end: string) => differenceInCalendarDays(parse(end), parse(start)) + 1

export const addDaysISO = (s: string, n: number) => toISO(addDays(parse(s), n))

/** 기간을 기준일 ~ 기준일 + (maxDays − 1) 안으로 맞춥니다. 잘못된 날짜면 7일 기본값. */
export function clampPeriod(asof: string, start: string, end: string, maxDays: number): { start: string; end: string } {
  const s = parse(start)
  const e = parse(end)
  if (!isValid(s) || !isValid(e)) return presetRange(asof, '7d')
  let st = toISO(s) < asof ? asof : toISO(s)
  const last = addDaysISO(asof, maxDays - 1)
  if (st > last) st = asof
  let en = toISO(e)
  if (en < st) en = st
  if (en > last) en = last
  return { start: st, end: en }
}

/** 단기 모델(1~14일) 범위 안의 기간인지 */
export const isShortPeriod = (asof: string, end: string) => daysBetween(asof, end) <= SHORT_DAYS
