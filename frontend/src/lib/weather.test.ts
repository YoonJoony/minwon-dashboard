import { describe, expect, it } from 'vitest'
import type { WeatherAlert } from '../api/client'
import { fmtBase, fmtExcess, summarizeAlerts } from './weather'

const a = (kind: string, level: number, source: string, label: string): WeatherAlert => ({
  kind,
  kind_label: kind,
  level,
  label,
  source,
  issued: source === 'NWS' ? '6/20 14:10' : null,
})

describe('예보 띠 특보 묶기', () => {
  it('종류별로 가장 높은 단계와 NWS 발표 여부를 남기고, 폭염·대설·강풍·호우 순서로', () => {
    const s = summarizeAlerts([
      a('wind', 1, '예보', '강풍주의보 수준'),
      a('heat', 0, 'NWS', '극한 폭염 예비특보'),
      a('heat', 2, '예보', '폭염경보 수준'),
    ])
    expect(s.map((x) => x.kind)).toEqual(['heat', 'wind'])
    expect(s[0]).toMatchObject({ level: 2, nws: true })
    expect(s[0].labels).toContain('극한 폭염 예비특보 (NWS 발표)')
    expect(s[1]).toMatchObject({ level: 1, nws: false })
  })
  it('지난 7일 관측 판정은 예보 판정처럼 묶고 NWS 발표로 치지 않음', () => {
    const s = summarizeAlerts([a('heat', 2, '관측', '폭염경보 수준'), a('heat', 1, 'NWS', '폭염 주의보')])
    expect(s).toHaveLength(1)
    expect(s[0]).toMatchObject({ kind: 'heat', level: 2, nws: true })
    expect(s[0].labels).toEqual(['폭염경보 수준', '폭염 주의보 (NWS 발표)'])
    expect(summarizeAlerts([a('snow', 1, '관측', '대설주의보 수준')])[0].nws).toBe(false)
  })
  it('특보가 없으면 빈 목록', () => {
    expect(summarizeAlerts([])).toEqual([])
  })
})

describe('모달 숫자 표기', () => {
  it('평소 하루 건수', () => {
    expect(fmtBase(26.5)).toBe('27')
    expect(fmtBase(2)).toBe('2.0')
    expect(fmtBase(0)).toBe('0')
  })
  it('늘어난 건수는 줄었거나 같으면 늘지 않음', () => {
    expect(fmtExcess(1300)).toBe('+1,300')
    expect(fmtExcess(-268.5)).toBe('늘지 않음')
    expect(fmtExcess(0.2)).toBe('늘지 않음')
  })
})
