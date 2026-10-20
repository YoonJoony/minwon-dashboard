import { describe, expect, it } from 'vitest'
import type { SummaryOut } from '../api/client'
import { buildKpis } from './kpi'

const base: SummaryOut = {
  period: { asof: '2025-06-20', start: '2025-06-20', end: '2025-06-26', days: 7, source: 'short', has_actual: true },
  agency: null,
  kpis: {
    forecast: { pred: 3361.6, lo: 2775.5, hi: 4281.1, base: 3011.75, change: 0.116, actual: 9007 },
    alert_count: 3,
    alert_top: '폭염경보 6/22',
    alert_detail: '2일 전 발표 예보 기준',
    focus_count: 0,
    increase_count: 3,
    focus_names: [],
    agency_quadrant: null,
    backlog_open: 6199,
    backlog_normal: 7787,
    backlog_multiple: 0.796,
    need_people: 1.229,
    need_count: 61.46,
    support_count: 0,
    coverage: 0,
  },
}

describe('상단 핵심 지표', () => {
  it('폭염 시나리오 문구', () => {
    const k = buildKpis(base, { days: 7, ppd: 10, agencySelected: false })
    expect(k.map((x) => x.key)).toEqual(['forecast', 'alerts', 'focus', 'backlog', 'staff'])
    expect(k[0].value).toBe('3,362')
    expect(k[0].sub).toContain('실제 9,007건')
    expect(k[1].value).toBe('3')
    expect(k[1].chip).toEqual({ text: '폭염경보 6/22', tone: 'danger' })
    expect(k[2].note).toBe('해당 부서 없음')
    expect(k[3].chip?.tone).toBe('muted')
    expect(k[4].value).toBe('1.2')
    expect(k[4].sub).toContain('1인 하루 10건')
  })

  it('특보가 없으면 "없음", 부서를 고르면 판정을 보여 준다', () => {
    const s: SummaryOut = {
      ...base,
      agency: 'DEP',
      kpis: { ...base.kpis, alert_count: 0, alert_top: null, agency_quadrant: '집중관리', backlog_multiple: 1.4 },
    }
    const k = buildKpis(s, { days: 7, ppd: 10, agencySelected: true })
    expect(k[1].value).toBe('없음')
    expect(k[1].chip).toBeUndefined()
    expect(k[2].label).toBe('부서 판정')
    expect(k[2].value).toBe('집중관리')
    expect(k[3].chip?.tone).toBe('warning')
  })
})
