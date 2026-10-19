import { describe, expect, it } from 'vitest'
import { fmtInt, fmtMult, fmtPct, fmtPeople, fmtRange, peopleText } from './format'

describe('숫자 표기', () => {
  it('천 단위 쉼표와 음수 기호', () => {
    expect(fmtInt(2672.45)).toBe('2,672')
    expect(fmtInt(-1234)).toBe('−1,234')
    expect(fmtInt(null)).toBe('–')
  })
  it('증감률은 부호를 붙인다', () => {
    expect(fmtPct(0.116)).toBe('+11.6%')
    expect(fmtPct(-0.1358)).toBe('−13.6%')
    expect(fmtPct(0.00001)).toBe('0%')
    expect(fmtPct(0.1, 0, false)).toBe('10%')
  })
  it('인원은 10명 미만이면 소수 첫째 자리, 아주 작으면 미만 표기', () => {
    expect(fmtPeople(0)).toBe('0')
    expect(fmtPeople(1.229)).toBe('1.2')
    expect(fmtPeople(12.4)).toBe('12')
    expect(peopleText(0.03)).toBe('0.1명 미만')
    expect(peopleText(0.7)).toBe('0.7명')
  })
  it('배수와 기간', () => {
    expect(fmtMult(1.1662)).toBe('1.17배')
    expect(fmtRange('2026-10-12', '2026-10-18')).toBe('10/12 ~ 10/18')
    expect(fmtRange('2026-12-28', '2027-01-03')).toBe('2026.12.28 ~ 2027.01.03')
  })
})
