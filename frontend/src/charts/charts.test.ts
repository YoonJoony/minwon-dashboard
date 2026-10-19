import { describe, expect, it } from 'vitest'
import { niceStep } from './forecastOption'
import { flagBadge, labelWidth, placeLabels } from './matrixOption'

describe('차트 보조 계산', () => {
  it('눈금 간격은 1·2·2.5·5 × 10^k', () => {
    expect(niceStep(180)).toBe(200)
    expect(niceStep(240)).toBe(250)
    expect(niceStep(0.3)).toBe(0.5)
    expect(niceStep(0)).toBe(1)
  })

  it('특보 표시 문구', () => {
    expect(flagBadge('기상 특보')).toBe('특보')
    expect(flagBadge('도로 파손 급증 예상')).toBe('도로 파손')
    expect(flagBadge('기상 특보 · 도로 파손 급증 예상')).toBe('특보')
  })

  it('붙어 있는 원의 이름표는 서로 다른 쪽에 놓는다', () => {
    const w = labelWidth('환경보호')
    const plot = { x0: 0, y0: 0, x1: 600, y1: 400 }
    const places = placeLabels(
      [
        { cx: 300, cy: 200, r: 18, w },
        { cx: 330, cy: 200, r: 12, w },
      ],
      plot,
    )
    const key = (p: (typeof places)[number]) => `${p.position}${p.offset.join(',')}`
    expect(key(places[0])).not.toBe(key(places[1]))
  })

  it('플롯 밖으로 나가는 쪽은 피한다', () => {
    const [p] = placeLabels([{ cx: 590, cy: 200, r: 10, w: labelWidth('교통') }], { x0: 0, y0: 0, x1: 600, y1: 400 })
    expect(p.position).not.toBe('right')
  })
})
