import type { WeatherAlert } from '../api/client'

const KIND_ORDER = ['heat', 'snow', 'wind', 'rain']

export type KindSummary = { kind: string; level: number; nws: boolean; labels: string[] }

/** 하루 칸의 특보를 종류별로 묶음: 가장 높은 단계, NWS 발표 여부, 문구 */
export function summarizeAlerts(alerts: WeatherAlert[]): KindSummary[] {
  const by = new Map<string, KindSummary>()
  for (const a of alerts) {
    const cur = by.get(a.kind) ?? { kind: a.kind, level: -1, nws: false, labels: [] }
    cur.level = Math.max(cur.level, a.level)
    cur.nws ||= a.source === 'NWS'
    cur.labels.push(a.source === 'NWS' ? `${a.label} (NWS 발표)` : a.label)
    by.set(a.kind, cur)
  }
  return KIND_ORDER.filter((k) => by.has(k)).map((k) => by.get(k)!)
}

/** 평소 하루 건수: 10건 미만은 소수 첫째 자리 */
export const fmtBase = (v: number) => {
  if (v >= 10) return `${Math.round(v)}`
  const r = Math.round(v * 10) / 10
  return r === 0 ? '0' : r.toFixed(1)
}

/** 늘어난 건수: 0 이하면 '늘지 않음' */
export const fmtExcess = (v: number) => (v > 0.5 ? `+${Math.round(v).toLocaleString('ko-KR')}` : '늘지 않음')
