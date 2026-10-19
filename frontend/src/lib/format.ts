import { format, parseISO } from 'date-fns'
import { ko } from 'date-fns/locale'

const nf = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 })
const MINUS = '−'

/** 정수(천 단위 쉼표). 값이 없으면 '–' */
export function fmtInt(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '–'
  const r = Math.round(v)
  return r < 0 ? MINUS + nf.format(-r) : nf.format(r)
}

/** 인원: 10명 미만은 소수 첫째 자리까지 */
export function fmtPeople(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '–'
  if (v >= 10) return nf.format(Math.round(v))
  const r = Math.round(v * 10) / 10
  return r === 0 ? '0' : r.toFixed(1)
}

/** 인원 문구(단위 포함): 0이면 '0명', 0.05명 미만이면 '0.1명 미만' */
export function peopleText(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '–'
  if (v > 0 && v < 0.05) return '0.1명 미만'
  return `${fmtPeople(v)}명`
}

/** 비율 0.123 → '+12.3%' (signed=false면 부호 없이) */
export function fmtPct(v: number | null | undefined, digits = 1, signed = true): string {
  if (v == null || !Number.isFinite(v)) return '–'
  const abs = (Math.abs(v) * 100).toFixed(digits)
  if (!signed) return `${abs}%`
  if (Number(abs) === 0) return '0%'
  return `${v > 0 ? '+' : MINUS}${abs}%`
}

/** 배수 1.234 → '1.23배' */
export function fmtMult(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '–'
  return `${v.toFixed(digits)}배`
}

const d = (s: string) => parseISO(s)

/** '2026.10.12' */
export const fmtDate = (s: string) => format(d(s), 'yyyy.MM.dd')
/** '2026.10.12 (월)' */
export const fmtDateW = (s: string) => format(d(s), 'yyyy.MM.dd (EEE)', { locale: ko })
/** '10/12' */
export const fmtMD = (s: string) => format(d(s), 'M/d')
/** '10/12(월)' */
export const fmtMDW = (s: string) => format(d(s), 'M/d(EEE)', { locale: ko })

/** 기간 표기: 같은 해면 '10/12 ~ 10/18', 해가 다르면 '2026.12.28 ~ 2027.01.03' */
export function fmtRange(start: string, end: string): string {
  if (start.slice(0, 4) !== end.slice(0, 4)) return `${fmtDate(start)} ~ ${fmtDate(end)}`
  return `${fmtMD(start)} ~ ${fmtMD(end)}`
}
