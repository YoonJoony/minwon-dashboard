import type { ForecastOut, SeriesPoint } from '../api/client'
import { fmtInt, fmtMD, fmtMDW } from '../lib/format'
import { C } from '../lib/theme'
import { FONT, tooltipBase, type EOption } from './useEChart'

/** 일 단위면 직전 14일 실적 + 기간 예측, 주 단위면 직전 8주 + 기간 */
export function forecastPoints(f: ForecastOut): SeriesPoint[] {
  const hist = f.series.filter((p) => p.kind === 'history')
  const fc = f.series.filter((p) => p.kind === 'forecast')
  return [...(f.granularity === 'day' ? hist.slice(-14) : hist), ...fc]
}

/** 1·2·2.5·5 × 10^k 단위로 올림한 눈금 간격 */
export function niceStep(raw: number): number {
  if (!(raw > 0)) return 1
  const exp = 10 ** Math.floor(Math.log10(raw))
  const m = raw / exp
  const s = m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10
  return s * exp
}

// 시안의 '빗금 용량 막대'를 80% 범위 상한으로 씁니다.
const HATCH = {
  symbol: 'rect',
  symbolSize: 1,
  color: 'rgba(91, 79, 224, 0.30)',
  dashArrayX: [1, 0],
  dashArrayY: [2, 5],
  rotation: -Math.PI / 4,
}

const alertShort = (a: string) => (a.includes('경보') || a.includes('매우') ? '경보' : '주의')

export function forecastOption(f: ForecastOut): EOption {
  const pts = forecastPoints(f)
  // 주 단위에서 7일이 안 되는 마지막 묶음은 일수를 붙여 갑자기 줄어든 것처럼 보이지 않게 합니다.
  const spanDays = (p: SeriesPoint) => Math.round((Date.parse(p.end) - Date.parse(p.start)) / 86_400_000) + 1
  const labels = pts.map((p) => (f.granularity === 'week' && spanDays(p) < 7 ? `${p.label}(${spanDays(p)}일)` : p.label))
  const byLabel = new Map(pts.map((p, i) => [labels[i], p]))
  const isF = (p: SeriesPoint) => p.kind === 'forecast'
  const firstF = labels[pts.findIndex(isF)]
  const lastF = labels[pts.length - 1 - [...pts].reverse().findIndex(isF)]
  const maxV = Math.max(1, ...pts.map((p) => Math.max(p.hi ?? 0, p.actual ?? 0, p.pred ?? 0)))
  const step = niceStep((maxV * 1.12) / 4)
  const day = f.granularity === 'day'
  const barWidth = pts.length > 30 ? '66%' : '58%'
  const radius = pts.length > 30 ? 4 : 8

  return {
    animationDuration: 450,
    textStyle: { fontFamily: FONT },
    grid: { left: 8, right: 8, top: 34, bottom: 4, containLabel: true },
    tooltip: {
      ...tooltipBase,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(91,79,224,0.06)' } },
      formatter: (params: unknown) => {
        const arr = (Array.isArray(params) ? params : [params]) as { axisValue?: string }[]
        const p = byLabel.get(arr[0]?.axisValue ?? '')
        if (!p) return ''
        const when = day ? fmtMDW(p.start) : `${fmtMD(p.start)} ~ ${fmtMD(p.end)} (${spanDays(p)}일)`
        if (!isF(p)) return `<b>${when}</b><br/>실적 <b>${fmtInt(p.actual)}</b>건`
        const rows = [
          `<b>${when}</b>`,
          `예측 <b>${fmtInt(p.pred)}</b>건`,
          `<span style="color:${C.mute}">80% 범위 ${fmtInt(p.lo)} ~ ${fmtInt(p.hi)}건</span>`,
        ]
        if (p.actual != null) rows.push(`실제 <b>${fmtInt(p.actual)}</b>건`)
        if (p.alert) rows.push(`<span style="color:#c2362d;font-weight:600">기상 특보 예보: ${p.alert}</span>`)
        return rows.join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8a8a9a', fontSize: 11, hideOverlap: true, margin: 12 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: step * 4,
      interval: step,
      axisLabel: { color: '#8a8a9a', fontSize: 11, formatter: (v: number) => fmtInt(v) },
      splitLine: { lineStyle: { color: C.grid, type: [4, 4] } },
    },
    series: [
      {
        name: '80% 범위 상한',
        type: 'bar',
        barGap: '-100%',
        barWidth,
        silent: true,
        z: 1,
        itemStyle: { color: '#f4f2fd', borderRadius: radius, decal: HATCH },
        labelLayout: { hideOverlap: true },
        data: pts.map((p) =>
          isF(p)
            ? {
                value: p.hi,
                label: p.alert
                  ? {
                      show: true,
                      position: 'top',
                      distance: 4,
                      formatter: `{a|${alertShort(p.alert)}}`,
                      rich: {
                        a: {
                          color: alertShort(p.alert) === '경보' ? '#c2362d' : '#a35a07',
                          backgroundColor: alertShort(p.alert) === '경보' ? '#fdecea' : '#fdf3e2',
                          borderRadius: 4,
                          padding: [2, 4],
                          fontSize: 10,
                          fontWeight: 700,
                        },
                      },
                    }
                  : undefined,
              }
            : null,
        ),
      },
      {
        name: '실적',
        type: 'bar',
        barGap: '-100%',
        barWidth,
        z: 2,
        itemStyle: { color: C.history, borderRadius: radius },
        emphasis: { itemStyle: { color: '#d6d4e2' } },
        data: pts.map((p) => (isF(p) ? null : p.actual)),
      },
      {
        name: '예측',
        type: 'bar',
        barGap: '-100%',
        barWidth,
        z: 3,
        itemStyle: { color: C.brandSoft, borderRadius: radius },
        emphasis: { itemStyle: { color: '#b3a8f3' } },
        data: pts.map((p) => (isF(p) ? { value: p.pred, itemStyle: p.alert ? { color: C.brandMid } : undefined } : null)),
        markArea:
          firstF && lastF
            ? {
                silent: true,
                itemStyle: { color: 'rgba(91,79,224,0.045)' },
                label: { show: true, position: 'insideTop', color: C.brand, fontSize: 11, fontWeight: 600, distance: 6 },
                data: [[{ xAxis: firstF, name: '예측 기간' }, { xAxis: lastF }]],
              }
            : undefined,
      },
      {
        name: '실제',
        type: 'custom',
        z: 4,
        silent: true,
        encode: { x: 0, y: 1 },
        data: pts.flatMap((p, i) => (isF(p) && p.actual != null ? [[i, p.actual]] : [])),
        renderItem: (_params: unknown, api: CustomApi) => {
          const [x, y] = api.coord([api.value(0), api.value(1)])
          const w = api.size([1, 0])[0] * (pts.length > 30 ? 0.66 : 0.58)
          return {
            type: 'group',
            children: [
              {
                type: 'line',
                shape: { x1: x - w / 2 - 2, y1: y, x2: x + w / 2 + 2, y2: y },
                style: { stroke: C.navy, lineWidth: 2.5, lineCap: 'round' },
              },
              { type: 'circle', shape: { cx: x, cy: y, r: 3 }, style: { fill: C.navy } },
            ],
          }
        },
      },
    ],
  }
}

type CustomApi = {
  value: (i: number) => number
  coord: (v: number[]) => number[]
  size: (v: number[]) => number[]
}
