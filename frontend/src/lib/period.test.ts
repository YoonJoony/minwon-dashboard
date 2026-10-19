import { describe, expect, it } from 'vitest'
import { clampPeriod, daysBetween, detectPreset, isShortPeriod, presetRange } from './period'

describe('빠른 선택 기간', () => {
  it('7일·14일은 기준일 포함', () => {
    expect(presetRange('2026-10-12', '7d')).toEqual({ start: '2026-10-12', end: '2026-10-18' })
    expect(presetRange('2026-10-12', '14d')).toEqual({ start: '2026-10-12', end: '2026-10-25' })
  })

  it('한 달·분기는 달력 기준이라 시연 시나리오와 같다', () => {
    // S4 평상시 한 달, S3 봄철 도로 파손(분기)
    expect(presetRange('2025-10-01', 'month')).toEqual({ start: '2025-10-01', end: '2025-10-31' })
    expect(presetRange('2026-03-01', 'quarter')).toEqual({ start: '2026-03-01', end: '2026-05-31' })
  })

  it('분기는 어느 기준일이든 최대 92일을 넘지 않는다', () => {
    for (const d of ['2026-10-12', '2025-07-15', '2024-12-01', '2026-01-31', '2025-06-30']) {
      const r = presetRange(d, 'quarter')
      expect(daysBetween(r.start, r.end)).toBeLessThanOrEqual(92)
    }
  })

  it('현재 기간이 어느 빠른 선택인지 알아낸다', () => {
    expect(detectPreset('2026-10-12', '2026-10-12', '2026-10-18')).toBe('7d')
    expect(detectPreset('2025-10-01', '2025-10-01', '2025-10-31')).toBe('month')
    expect(detectPreset('2026-10-12', '2026-10-13', '2026-10-18')).toBe('custom')
  })
})

describe('기간 보정', () => {
  it('기준일 앞이나 92일 밖은 잘라낸다', () => {
    expect(clampPeriod('2026-10-12', '2026-10-01', '2027-03-01', 92)).toEqual({ start: '2026-10-12', end: '2027-01-11' })
  })
  it('끝이 시작보다 앞이면 시작에 맞춘다', () => {
    expect(clampPeriod('2026-10-12', '2026-10-20', '2026-10-15', 92)).toEqual({ start: '2026-10-20', end: '2026-10-20' })
  })
  it('날짜가 잘못되면 7일 기본값', () => {
    expect(clampPeriod('2026-10-12', 'abc', '2026-10-15', 92)).toEqual({ start: '2026-10-12', end: '2026-10-18' })
  })
  it('1~14일은 단기 모델', () => {
    expect(isShortPeriod('2026-10-12', '2026-10-25')).toBe(true)
    expect(isShortPeriod('2026-10-12', '2026-10-26')).toBe(false)
  })
})
